<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref, watch } from 'vue'
import { ChevronDown, Download, FileArchive, Heart, Music2, Undo2 } from '@lucide/vue'
import { readWork, RequestError, startRevision, withdrawWork } from '../api'
import GlassDialog from './GlassDialog.vue'
import PdfPreview from './PdfPreview.vue'
import { assetPath, fileSize, kindLabels, statusLabels } from '../works'
import type { Work } from '../works'

const WorkComments = defineAsyncComponent(() => import('./WorkComments.vue'))
const props = defineProps<{ work: Work; favorite?: boolean; moderating?: boolean; busy?: boolean }>()
const emit = defineEmits<{ close: []; toggleFavorite: []; edit: [work: Work]; viewRevision: [work: Work]; withdrawn: [work: Work]; refresh: [] }>()
const selected = ref(props.work.assets[0]?.id)
const mediaError = ref(false)
const pdfExpanded = ref(false)
const withdrawing = ref(false)
const withdrawError = ref('')
const withdrawn = ref(false)
const openingRevision = ref(false)
const revisionError = ref('')
const editButton = ref<HTMLButtonElement>()
const asset = computed(() => props.work.assets.find(item => item.id === selected.value))
const canWithdraw = computed(() => !props.moderating && props.work.is_mine && props.work.status === 'pending')

watch(selected, () => {
  mediaError.value = false
  pdfExpanded.value = false
})
watch(() => props.work.assets, assets => {
  if (!assets.some(item => item.id === selected.value)) selected.value = assets[0]?.id
})

function close() {
  if (pdfExpanded.value) pdfExpanded.value = false
  else if (!withdrawing.value && !openingRevision.value && !props.busy) emit('close')
}

async function edit() {
  const work = props.work
  if (work.can_edit) {
    emit('edit', work)
    return
  }
  if (!work.can_revise || openingRevision.value) return
  openingRevision.value = true
  revisionError.value = ''
  try {
    const revision = work.revision ? await readWork(work.revision.id) : await startRevision(work.id)
    if (revision.status === 'pending') emit('viewRevision', revision)
    else emit('edit', revision)
  } catch (error) {
    revisionError.value = error instanceof Error ? error.message : '无法打开修改稿。'
    if (error instanceof RequestError && error.status === 404) emit('refresh')
  } finally {
    openingRevision.value = false
  }
}

async function withdraw() {
  if (withdrawing.value || !canWithdraw.value) return
  withdrawing.value = true
  withdrawError.value = ''
  try {
    const work = await withdrawWork(props.work.id)
    withdrawn.value = true
    emit('withdrawn', work)
    await nextTick()
    editButton.value?.focus()
  } catch (error) {
    withdrawError.value = error instanceof Error ? error.message : '无法撤回投稿。'
    if (error instanceof RequestError && error.status === 400) emit('refresh')
  } finally {
    withdrawing.value = false
  }
}
</script>

<template>
  <GlassDialog :title="pdfExpanded && asset ? asset.original_name : work.title" labelledby="preview-heading"
    :description="pdfExpanded ? undefined : work.description" :close-label="pdfExpanded ? '返回作品详情' : undefined"
    :expanded="pdfExpanded" wide @close="close">
    <template v-if="!pdfExpanded">
      <slot name="context" />
      <p v-if="work.revision_of && !moderating" class="preview-feedback">这是作品修改稿。审核通过后，已展示的作品会更新。</p>
      <p v-if="work.review_note && (work.is_mine || moderating)" class="review-note">{{ work.review_note }}</p>
      <dl v-if="work.competition_name || work.team_name || work.team_members" class="preview-work-details">
        <div v-if="work.competition_name"><dt>比赛名称</dt><dd>{{ work.competition_name }}</dd></div>
        <div v-if="work.team_name"><dt>团队名称</dt><dd>{{ work.team_name }}</dd></div>
        <div v-if="work.team_members"><dt>团队成员</dt><dd>{{ work.team_members }}</dd></div>
      </dl>
      <label v-if="work.assets.length > 1" class="form-field attachment-choice">
        <span>作品附件</span>
        <span class="attachment-select">
          <select v-model="selected">
            <option v-for="item in work.assets" :key="item.id" :value="item.id">{{ item.original_name }}</option>
          </select>
          <ChevronDown :size="16" aria-hidden="true" />
        </span>
      </label>
    </template>
    <div class="preview-stage">
      <template v-if="asset">
        <iframe v-if="asset.kind === 'slides'" :key="asset.id" :src="assetPath(work, asset, 'viewer')" title="PPT 在线预览" allowfullscreen />
        <PdfPreview v-else-if="asset.kind === 'pdf'" :key="asset.id" v-model:expanded="pdfExpanded" :source="assetPath(work, asset, 'pdf')" />
        <video v-else-if="asset.kind === 'video' && !mediaError" :key="asset.id" :src="assetPath(work, asset, 'video')" controls playsinline preload="metadata" @error="mediaError = true" />
        <div v-else-if="asset.kind === 'audio' && !mediaError" :key="asset.id" class="audio-preview">
          <Music2 :size="34" :stroke-width="1.5" aria-hidden="true" />
          <strong>{{ asset.original_name }}</strong>
          <audio :src="assetPath(work, asset, 'audio')" :aria-label="asset.original_name" controls
            :controlslist="work.can_download ? undefined : 'nodownload'" preload="metadata" @error="mediaError = true" />
        </div>
        <div v-else class="file-preview">
          <FileArchive :size="36" :stroke-width="1.4" aria-hidden="true" />
          <strong>{{ asset.original_name }}</strong>
          <p v-if="mediaError">浏览器无法播放此{{ kindLabels[asset.kind] }}。</p>
          <p v-else>{{ work.can_download ? '下载压缩包以查看源码。' : '此作品目前仅展示附件信息。' }}</p>
        </div>
      </template>
      <div v-else class="file-preview">还没有上传附件。</div>
    </div>
    <p v-if="!pdfExpanded && withdrawError" class="form-error preview-feedback" role="alert">{{ withdrawError }}</p>
    <p v-if="!pdfExpanded && revisionError" class="form-error preview-feedback" role="alert">{{ revisionError }}</p>
    <p v-if="!pdfExpanded && withdrawn" class="preview-feedback" role="status">{{ work.revision_of ? '修改稿已撤回，可以继续编辑。' : '投稿已撤回，可以继续编辑或重新提交。' }}</p>
    <footer v-if="!pdfExpanded" class="preview-footer">
      <div class="preview-meta">
        <span v-if="work.is_mine && !moderating">{{ statusLabels[work.status] }}</span>
        <span v-if="work.revision && !moderating">修改稿 · {{ statusLabels[work.revision.status] }}</span>
        <span v-if="asset">{{ kindLabels[asset.kind] }} · {{ fileSize(asset.size) }}</span>
      </div>
      <div class="preview-actions">
        <button v-if="canWithdraw" type="button" class="glass-button" :disabled="withdrawing" @click="withdraw">
          <Undo2 :size="17" aria-hidden="true" /> {{ withdrawing ? '正在撤回…' : work.revision_of ? '撤回修改稿' : '撤回投稿' }}
        </button>
        <button v-if="(work.can_edit || work.can_revise) && !moderating" ref="editButton" type="button" class="glass-button"
          :disabled="openingRevision || withdrawing" @click="edit">
          {{ openingRevision ? '正在打开…' : work.revision?.status === 'pending' ? '查看修改稿' : work.revision || work.revision_of ? '编辑修改稿' : '编辑作品' }}
        </button>
        <button v-if="work.is_visible && !moderating" type="button" class="glass-button" :aria-pressed="favorite" @click="emit('toggleFavorite')">
          <Heart :size="17" :class="{ 'heart-filled': favorite }" /> {{ favorite ? '已收藏' : '收藏' }}
        </button>
        <a v-if="work.can_download && asset" class="primary-button" :href="assetPath(work, asset, 'download')" download>
          <Download :size="17" /> 下载原件
        </a>
      </div>
    </footer>
    <WorkComments v-if="work.is_visible && !moderating" v-show="!pdfExpanded" :work-id="work.id" />
    <slot v-if="!pdfExpanded" name="management" />
  </GlassDialog>
</template>
