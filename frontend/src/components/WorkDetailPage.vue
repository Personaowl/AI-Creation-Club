<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ArrowLeft, ArrowUpRight, Download, File, Files, Heart, Play, Trophy, Undo2 } from '@lucide/vue'
import { readWork, RequestError, startRevision, withdrawWork } from '../api'
import { brandName } from '../branding'
import { assetPath, fileSize, kindLabels, pdfReaderPath, statusLabels, workAttachments, workDetailPath } from '../works'
import type { Asset, Work } from '../works'
import GlassDialog from './GlassDialog.vue'
import WorkOverview from './WorkOverview.vue'

const AttachmentMedia = defineAsyncComponent(() => import('./AttachmentMedia.vue'))
const WorkComments = defineAsyncComponent(() => import('./WorkComments.vue'))
const props = defineProps<{ workId: string; favorite: boolean; backLabel: string; refreshKey: number }>()
const emit = defineEmits<{ back: []; favorite: []; edit: [work: Work]; withdrawn: [work: Work] }>()
const work = ref<Work>()
const selected = ref<Asset>()
const attachments = computed(() => workAttachments(work.value))
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)
const heading = ref<HTMLHeadingElement>()
let loadNumber = 0
const previousTitle = document.title

watch(() => props.refreshKey, async () => {
  const request = ++loadNumber
  try {
    const result = await readWork(props.workId)
    if (request !== loadNumber) return
    const firstLoad = !work.value
    work.value = result
    if (selected.value) selected.value = workAttachments(result).find(item => item.id === selected.value?.id)
    error.value = ''
    document.title = result.title + ' · ' + brandName
    if (firstLoad) {
      await nextTick()
      heading.value?.focus({ preventScroll: true })
    }
  } catch (reason) {
    if (request !== loadNumber) return
    if (reason instanceof RequestError && [403, 404].includes(reason.status)) {
      work.value = undefined
      selected.value = undefined
      error.value = '无法查看此作品。作品可能已下架，或当前账号没有查看权限。'
    } else if (!work.value) {
      error.value = '无法加载作品，请刷新后重试。'
    }
  }
}, { immediate: true })

onBeforeUnmount(() => {
  loadNumber += 1
  document.title = previousTitle
})

async function edit() {
  const current = work.value
  if (!current || busy.value) return
  if (current.can_edit) {
    emit('edit', current)
    return
  }
  if (!current.can_revise) return
  busy.value = true
  actionError.value = ''
  try {
    const revision = current.revision ? await readWork(current.revision.id) : await startRevision(current.id)
    if (revision.status === 'pending') window.location.hash = workDetailPath(revision.id)
    else emit('edit', revision)
  } catch (reason) {
    actionError.value = reason instanceof Error ? reason.message : '无法打开修改稿。'
  } finally {
    busy.value = false
  }
}

async function withdraw() {
  const current = work.value
  if (!current || busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    const withdrawn = await withdrawWork(current.id)
    loadNumber += 1
    work.value = withdrawn
    notice.value = withdrawn.revision_of ? '修改稿已撤回，可以继续编辑。' : '投稿已撤回，可以继续编辑或重新提交。'
    emit('withdrawn', withdrawn)
  } catch (reason) {
    actionError.value = reason instanceof Error ? reason.message : '无法撤回投稿。'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main id="work-detail" class="work-detail" tabindex="-1">
    <div class="work-detail-nav">
      <a class="glass-button" href="#gallery" @click.prevent="emit('back')">
        <ArrowLeft :size="17" aria-hidden="true" /> {{ backLabel }}
      </a>
    </div>
    <template v-if="work">
      <header class="work-detail-hero glass-panel">
        <div>
          <div v-if="work.competition_name" class="work-detail-competition">
            <Trophy :size="16" aria-hidden="true" /> <span>{{ work.competition_name }}</span>
            <span v-if="work.competition_year" class="work-edition">{{ work.competition_year }} 年</span>
          </div>
          <h1 ref="heading" tabindex="-1">{{ work.title }}</h1>
          <p v-if="work.description" class="work-detail-prose">{{ work.description }}</p>
        </div>
        <div v-if="work.is_visible || work.is_mine" class="work-detail-actions">
          <span v-if="work.is_mine" class="work-detail-status">
            {{ work.revision ? '修改稿 · ' + statusLabels[work.revision.status] : work.is_visible ? '已上架' : statusLabels[work.status] }}
          </span>
          <button v-if="work.is_visible" type="button" class="glass-button" :aria-pressed="favorite" @click="emit('favorite')">
            <Heart :size="17" :class="{ 'heart-filled': favorite }" aria-hidden="true" /> {{ favorite ? '已收藏' : '收藏' }}
          </button>
          <button v-if="work.is_mine && work.status === 'pending'" type="button" class="glass-button" :disabled="busy" @click="withdraw">
            <Undo2 :size="17" aria-hidden="true" /> {{ work.revision_of ? '撤回修改稿' : '撤回投稿' }}
          </button>
          <button v-if="work.can_edit || work.can_revise" type="button" class="primary-button" :disabled="busy" @click="edit">
            {{ work.revision?.status === 'pending' ? '查看修改稿' : work.revision || work.revision_of ? '编辑修改稿' : '编辑作品' }}
          </button>
        </div>
      </header>
      <p v-if="work.revision_of" class="work-detail-feedback work-detail-panel">这是作品修改稿。审核通过后，已展示的作品会更新。</p>
      <p v-if="work.review_note && work.is_mine" class="review-note">{{ work.review_note }}</p>
      <p v-if="actionError" class="work-detail-feedback work-detail-panel form-error" role="alert">{{ actionError }}</p>
      <p v-if="notice" class="work-detail-feedback work-detail-panel" role="status">{{ notice }}</p>

      <WorkOverview :work="work" />

      <section class="work-detail-panel" aria-labelledby="work-attachments-heading">
        <h2 id="work-attachments-heading" class="work-section-heading"><span><Files :size="19" aria-hidden="true" /></span> 作品附件</h2>
        <ul v-if="attachments.length" class="work-file-list">
          <li v-for="asset in attachments" :key="asset.id">
            <div class="work-file-title">
              <span class="work-file-icon"><File :size="19" aria-hidden="true" /></span>
              <div>
                <strong>{{ asset.original_name }}</strong>
                <small>{{ kindLabels[asset.kind] }} · {{ fileSize(asset.size) }}</small>
              </div>
            </div>
            <div class="work-file-actions">
              <a v-if="asset.kind === 'pdf'" class="glass-button" :href="pdfReaderPath(work.id, asset.id)" :aria-label="'阅读 PDF ' + asset.original_name">
                阅读 PDF <ArrowUpRight :size="16" aria-hidden="true" />
              </a>
              <a v-else-if="asset.kind === 'slides'" class="glass-button" :href="assetPath(work, asset, 'viewer')" target="_blank"
                rel="noopener" :aria-label="'打开演示文稿 ' + asset.original_name">
                打开演示 <ArrowUpRight :size="16" aria-hidden="true" />
              </a>
              <button v-else-if="asset.kind === 'video' || asset.kind === 'audio'" class="glass-button" type="button"
                :aria-label="'播放 ' + asset.original_name" @click="selected = asset">
                <Play :size="16" aria-hidden="true" /> 播放
              </button>
              <a v-if="work.can_download" class="glass-button" :href="assetPath(work, asset, 'download')" download :aria-label="'下载 ' + asset.original_name">
                <Download :size="16" aria-hidden="true" /> 下载
              </a>
              <small v-else-if="asset.kind === 'source'">仅展示附件信息</small>
            </div>
          </li>
        </ul>
        <p v-else class="work-detail-prose">还没有上传附件。</p>
      </section>

      <WorkComments v-if="work.is_visible" :work-id="work.id" class="work-detail-panel" />

      <GlassDialog v-if="selected" :title="selected.original_name" labelledby="work-media-heading" wide @close="selected = undefined">
        <AttachmentMedia :key="selected.id" :work="work" :asset="selected" />
      </GlassDialog>
    </template>
    <p v-else-if="error" class="work-detail-panel form-error" role="alert">{{ error }}</p>
    <p v-else class="work-detail-panel" role="status">正在加载作品…</p>
  </main>
</template>
