<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Maximize2, ZoomIn } from '@lucide/vue'

const props = defineProps<{ source: string; readerUrl?: string; initialPage?: number }>()
const emit = defineEmits<{ pageChanged: [page: number] }>()
const page = ref(props.initialPage ?? 1)
const pageInput = ref(String(page.value))
const pageCount = ref(0)
const image = ref('')
const loading = ref(false)
const failed = ref(false)
const magnified = ref(false)
const pageArea = ref<HTMLDivElement>()
const retry = ref(0)

function goTo(value: number | string) {
  const next = Number(value)
  if (pageCount.value && Number.isSafeInteger(next) && String(value).trim()) {
    page.value = Math.min(Math.max(1, next), pageCount.value)
  }
  pageInput.value = String(page.value)
}

function onKeydown(event: KeyboardEvent) {
  if (!pageCount.value || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.target instanceof HTMLElement && (event.target.isContentEditable || event.target.closest('input, textarea, select'))) return

  const targets: Record<string, number> = {
    ArrowLeft: page.value - 1, PageUp: page.value - 1,
    ArrowRight: page.value + 1, PageDown: page.value + 1,
    Home: 1, End: pageCount.value,
  }
  if (!Object.hasOwn(targets, event.key)) return
  event.preventDefault()
  goTo(targets[event.key])
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  if (!props.readerUrl) pageArea.value?.focus({ preventScroll: true })
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

watch([page, retry], async ([number], _, onCleanup) => {
  pageArea.value?.scrollTo(0, 0)
  const controller = new AbortController()
  let imageUrl = ''
  onCleanup(() => {
    controller.abort()
    if (imageUrl) URL.revokeObjectURL(imageUrl)
  })
  loading.value = true
  failed.value = false
  image.value = ''
  try {
    const response = await fetch(`${props.source}${number}/`, { signal: controller.signal })
    if (!controller.signal.aborted && response.status === 404 && pageCount.value === 0 && number !== 1) {
      page.value = 1
      pageInput.value = '1'
      return
    }
    const count = Number(response.headers.get('X-Page-Count'))
    if (!response.ok || !Number.isSafeInteger(count) || count < number) throw new Error()
    const bitmap = await response.blob()
    if (controller.signal.aborted) return
    imageUrl = URL.createObjectURL(bitmap)
    image.value = imageUrl
    pageCount.value = count
    emit('pageChanged', number)
  } catch {
    if (!controller.signal.aborted) failed.value = true
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <div class="pdf-preview" :class="{ 'pdf-preview-standalone': !readerUrl }">
    <div v-if="pageCount > 1 || !readerUrl" class="pdf-controls" :class="{ 'glass-panel': !readerUrl }">
      <template v-if="pageCount > 1">
        <button type="button" class="glass-button icon-button" aria-label="上一页" :disabled="page <= 1" @click="goTo(page - 1)">
          <ChevronLeft :size="20" aria-hidden="true" />
        </button>
        <form class="pdf-jump" @submit.prevent="goTo(pageInput)">
          <input v-model="pageInput" type="text" inputmode="numeric" autocomplete="off" aria-label="页码" :size="String(pageCount).length + 1"
            @focus="($event.target as HTMLInputElement).select()">
          <span>/ {{ pageCount }}</span>
          <button type="submit" class="glass-button">跳转</button>
        </form>
        <button type="button" class="glass-button icon-button" aria-label="下一页" :disabled="page >= pageCount" @click="goTo(page + 1)">
          <ChevronRight :size="20" aria-hidden="true" />
        </button>
      </template>
      <span v-else-if="pageCount === 1">1 / 1</span>
      <button v-if="!readerUrl" type="button" class="glass-button pdf-zoom" :aria-pressed="magnified" :disabled="!image" @click="magnified = !magnified">
        <ZoomIn :size="17" aria-hidden="true" /> {{ magnified ? '适合页面' : '放大' }}
      </button>
    </div>
    <div ref="pageArea" class="pdf-page" :class="{ 'pdf-page-zoomed': magnified }" :aria-busy="loading"
      :tabindex="readerUrl ? undefined : 0" :role="readerUrl ? undefined : 'region'" :aria-label="readerUrl ? undefined : 'PDF 阅读区'">
      <a v-if="image && readerUrl" class="pdf-open" :href="`${readerUrl}/${page}`" target="_blank" rel="noopener"
        :aria-label="`在新标签页放大预览 PDF 第 ${page} 页`">
        <img :src="image" :alt="`PDF 第 ${page} 页`">
        <span class="pdf-open-label"><Maximize2 :size="15" aria-hidden="true" /> 放大预览</span>
      </a>
      <img v-else-if="image" :src="image" :alt="`PDF 第 ${page} 页`">
      <div v-else-if="failed" class="pdf-load-error">
        <p class="form-error" role="alert">无法预览此页 PDF。</p>
        <button class="glass-button" type="button" @click="retry += 1">重试</button>
      </div>
      <p v-else role="status">正在加载 PDF…</p>
    </div>
    <span class="sr-only" aria-live="polite">{{ image ? `第 ${page} 页，共 ${pageCount} 页` : '' }}</span>
  </div>
</template>
