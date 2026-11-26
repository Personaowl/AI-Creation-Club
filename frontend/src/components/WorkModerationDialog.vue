<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ArrowDownToLine, ArrowUpFromLine, Check, Trash2, Undo2 } from '@lucide/vue'
import { changeWorkAccess, deleteManagedWork, RequestError, reviewWork } from '../api'
import { statusLabels } from '../works'
import type { Competition, ManagedWork } from '../works'
import CompetitionAssignment from './CompetitionAssignment.vue'
import PreviewDialog from './PreviewDialog.vue'

const props = defineProps<{ work: ManagedWork; competitions: Competition[]; mode: 'review' | 'display' }>()
const emit = defineEmits<{ close: []; updated: [work: ManagedWork]; deleted: [work: ManagedWork]; refresh: []; openDisplay: [] }>()
const noteField = ref<HTMLTextAreaElement>()
const note = ref('')
const downloadable = ref(props.work.allow_download)
const competition = ref(props.work.competition)
const competitionYear = ref(props.work.competition_year)
const saving = ref(false)
const error = ref('')
const feedback = ref('')
const confirmingDelete = ref(false)
const deleteButton = ref<HTMLButtonElement>()
const cancelDeleteButton = ref<HTMLButtonElement>()

watch(() => props.work.allow_download, value => { downloadable.value = value })
watch(() => props.work.competition, value => { competition.value = value })
watch(() => props.work.competition_year, value => { competitionYear.value = value })

async function save(request: () => Promise<ManagedWork>, message: string) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  feedback.value = ''
  try {
    emit('updated', await request())
    feedback.value = message
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '操作失败，请重试。'
    if (reason instanceof RequestError && [400, 404].includes(reason.status)) emit('refresh')
  } finally {
    saving.value = false
  }
}

function review(decision: 'approved' | 'rejected') {
  if (decision === 'rejected' && !note.value.trim()) {
    error.value = '退回时请填写审核意见。'
    noteField.value?.focus()
    return
  }
  void save(() => reviewWork(props.work.id, decision, note.value.trim()), decision === 'approved' ? '作品已通过审核。' : '作品已退回给作者。')
}

function saveAccess() {
  const changes: Partial<Pick<ManagedWork, 'allow_download' | 'competition' | 'competition_year'>> = {}
  if (downloadable.value !== props.work.allow_download) changes.allow_download = downloadable.value
  if (competition.value !== props.work.competition) changes.competition = competition.value
  if (competitionYear.value !== props.work.competition_year) changes.competition_year = competitionYear.value
  void save(() => changeWorkAccess(props.work.id, changes), '展示设置已保存。')
}

function togglePublication() {
  const isVisible = !props.work.is_visible
  void save(() => changeWorkAccess(props.work.id, { is_visible: isVisible }), isVisible ? '作品已上架。' : '作品已下架。')
}

async function confirmDelete() {
  error.value = ''
  feedback.value = ''
  confirmingDelete.value = true
  await nextTick()
  cancelDeleteButton.value?.focus()
}

async function cancelDelete() {
  confirmingDelete.value = false
  error.value = ''
  await nextTick()
  deleteButton.value?.focus()
}

async function removeWork() {
  if (saving.value || !confirmingDelete.value) return
  saving.value = true
  error.value = ''
  try {
    await deleteManagedWork(props.work.id)
    emit('deleted', props.work)
  } catch (reason) {
    if (reason instanceof RequestError && reason.status === 404) {
      emit('deleted', props.work)
    } else {
      error.value = reason instanceof Error ? reason.message : '删除失败，请重试。'
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <PreviewDialog :work="work" :busy="saving" @close="confirmingDelete ? cancelDelete() : emit('close')">
    <template #context>
      <div class="manage-work-context">
        <span>投稿人 {{ work.owner_username }}</span>
        <span v-if="work.revision_of" class="manage-status">修改稿</span>
        <span class="manage-status" :data-status="work.status">{{ statusLabels[work.status] }}</span>
      </div>
      <section v-if="mode === 'display' && work.status === 'approved'" class="manage-review manage-publication">
        <div class="manage-publication-heading">
          <div>
            <h3>展示设置</h3>
            <p class="manage-hint">{{ work.is_visible ? '已上架' : '未上架' }}</p>
          </div>
          <div class="manage-publication-actions">
            <button class="glass-button" type="button" :disabled="saving || confirmingDelete" @click="togglePublication">
              <ArrowDownToLine v-if="work.is_visible" :size="17" aria-hidden="true" />
              <ArrowUpFromLine v-else :size="17" aria-hidden="true" />
              {{ work.is_visible ? '下架作品' : '上架作品' }}
            </button>
            <button v-if="!confirmingDelete" ref="deleteButton" class="glass-button manage-danger" type="button" :disabled="saving" @click="confirmDelete">
              <Trash2 :size="17" aria-hidden="true" /> 删除作品
            </button>
          </div>
        </div>
        <div v-if="confirmingDelete" class="manage-delete-confirmation" role="group" aria-label="确认删除作品">
          <p>删除后，作品、附件、评论和修改稿将永久移除。</p>
          <div class="dialog-actions">
            <button ref="cancelDeleteButton" class="glass-button" type="button" :disabled="saving" @click="cancelDelete">取消</button>
            <button class="glass-button manage-danger" type="button" :disabled="saving" @click="removeWork">{{ saving ? '正在删除…' : '确认删除' }}</button>
          </div>
        </div>
        <form v-else class="manage-display-form" @submit.prevent="saveAccess">
          <CompetitionAssignment v-model:competition="competition" v-model:year="competitionYear" :competitions="competitions" :disabled="saving" />
          <div class="manage-access">
            <label><input v-model="downloadable" type="checkbox" :disabled="saving"> 允许成员下载原件</label>
            <button class="primary-button" type="submit"
              :disabled="saving || (downloadable === work.allow_download && competition === work.competition && competitionYear === work.competition_year)">保存设置</button>
          </div>
        </form>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <p v-if="feedback" class="manage-hint" role="status">{{ feedback }}</p>
      </section>
    </template>
    <template #management>
      <section v-if="mode === 'review' && (work.status === 'pending' || work.status === 'approved' || error || feedback)" class="manage-review">
        <template v-if="work.status === 'pending'">
          <h3>审核作品</h3>
          <label class="form-field">
            <span>审核意见 <small>退回时必填</small></span>
            <textarea ref="noteField" v-model="note" rows="2" maxlength="1000" :disabled="saving" />
          </label>
          <div class="dialog-actions">
            <button class="glass-button manage-danger" type="button" :disabled="saving" @click="review('rejected')"><Undo2 :size="17" aria-hidden="true" /> 退回作品</button>
            <button class="primary-button" type="button" :disabled="saving" @click="review('approved')"><Check :size="17" aria-hidden="true" /> 审核通过</button>
          </div>
        </template>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <p v-if="feedback" class="manage-hint" role="status">{{ feedback }}</p>
        <div v-if="work.status === 'approved'" class="dialog-actions">
          <button class="primary-button" type="button" @click="emit('openDisplay')">前往展示管理</button>
        </div>
      </section>
    </template>
  </PreviewDialog>
</template>
