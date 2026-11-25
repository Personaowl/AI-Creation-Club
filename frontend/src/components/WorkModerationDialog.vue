<script setup lang="ts">
import { ref, watch } from 'vue'
import { Check, Undo2 } from '@lucide/vue'
import { changeWorkAccess, RequestError, reviewWork } from '../api'
import { statusLabels } from '../works'
import type { Competition, ManagedWork } from '../works'
import PreviewDialog from './PreviewDialog.vue'

const props = defineProps<{ work: ManagedWork; competitions: Competition[]; mode: 'review' | 'display' }>()
const emit = defineEmits<{ close: []; updated: [work: ManagedWork]; refresh: []; openDisplay: [] }>()
const noteField = ref<HTMLTextAreaElement>()
const note = ref('')
const visible = ref(props.work.is_visible)
const downloadable = ref(props.work.allow_download)
const competition = ref(props.work.competition)
const saving = ref(false)
const error = ref('')
const feedback = ref('')

watch(() => [props.work.is_visible, props.work.allow_download, props.work.competition] as const, ([nextVisible, nextDownloadable, nextCompetition]) => {
  visible.value = nextVisible
  downloadable.value = nextDownloadable
  competition.value = nextCompetition
})

async function save(request: () => Promise<ManagedWork>, message: string) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  feedback.value = ''
  try {
    emit('updated', await request())
    feedback.value = message
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法保存审核结果。'
    if (reason instanceof RequestError && reason.status === 400) emit('refresh')
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
  const changes: Partial<Pick<ManagedWork, 'is_visible' | 'allow_download' | 'competition'>> = {}
  if (visible.value !== props.work.is_visible) changes.is_visible = visible.value
  if (downloadable.value !== props.work.allow_download) changes.allow_download = downloadable.value
  if (competition.value !== props.work.competition) changes.competition = competition.value
  void save(() => changeWorkAccess(props.work.id, changes), '展示设置已保存。')
}
</script>

<template>
  <PreviewDialog :work="work" moderating :busy="saving" @close="emit('close')">
    <template #context>
      <div class="manage-work-context">
        <span>投稿人 {{ work.owner_username }}</span>
        <span v-if="work.revision_of" class="manage-status">修改稿</span>
        <span class="manage-status" :data-status="work.status">{{ statusLabels[work.status] }}</span>
      </div>
    </template>
    <template #management>
      <section v-if="work.status === 'pending' || work.status === 'approved' || error || feedback" class="manage-review">
        <template v-if="mode === 'review' && work.status === 'pending'">
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
        <template v-else-if="mode === 'display' && work.status === 'approved'">
          <h3>展示设置</h3>
          <form class="manage-display-form" @submit.prevent="saveAccess">
            <label class="form-field">
              <span>比赛分类</span>
              <select v-model="competition" :disabled="saving">
                <option :value="null">未分类</option>
                <option v-for="item in competitions" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
            </label>
            <div class="manage-access">
              <label><input v-model="visible" type="checkbox" :disabled="saving"> 上架展示</label>
              <label><input v-model="downloadable" type="checkbox" :disabled="saving"> 允许成员下载原件</label>
              <button class="primary-button" type="submit" :disabled="saving || (visible === work.is_visible && downloadable === work.allow_download && competition === work.competition)">保存设置</button>
            </div>
          </form>
        </template>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <p v-if="feedback" class="manage-hint" role="status">{{ feedback }}</p>
        <div v-if="mode === 'review' && work.status === 'approved'" class="dialog-actions">
          <button class="primary-button" type="button" @click="emit('openDisplay')">前往展示管理</button>
        </div>
      </section>
    </template>
  </PreviewDialog>
</template>
