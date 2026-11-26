<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { ChevronLeft, ChevronRight, Maximize2, ZoomIn } from '@lucide/vue'

const props = defineProps<{ source: string; readerUrl?: string; initialPage?: number }>()
const emit = defineEmits<{ pageChanged: [page: number] }>()
const gap = 12
const sizes = shallowRef<[number, number][]>([])
const page = ref(props.initialPage ?? 1)
const pageInput = ref(String(page.value))
const viewport = ref<HTMLDivElement>()
const viewportSize = shallowRef({ width: 0, height: 0 })
const scrollTop = ref(0)
const magnified = ref(false)
const loading = ref(true)
const ready = ref(false)
const error = ref('')
const retry = ref(0)
const failedPages = ref(new Set<number>())
let observer: ResizeObserver | undefined
let frame = 0

const layout = computed(() => {
  const { width, height } = viewportSize.value
  let top = gap
  let canvasWidth = width
  const pages = sizes.value.map(([originalWidth, originalHeight], index) => {
    const fit = Math.min(Math.max(width - gap * 2, 1) / originalWidth, Math.max(height - gap * 2, 1) / originalHeight)
    const scale = fit * (magnified.value ? 1.5 : 1)
    const pageWidth = originalWidth * scale
    const pageHeight = originalHeight * scale
    const entry = { number: index + 1, top, width: pageWidth, height: pageHeight }
    top += pageHeight + gap
    canvasWidth = Math.max(canvasWidth, pageWidth + gap * 2)
    return entry
  })
  return { pages, width: canvasWidth, height: top }
})

function pageIndexAt(offset: number) {
  const pages = layout.value.pages
  let first = 0
  let last = pages.length - 1
  while (first < last) {
    const middle = Math.floor((first + last + 1) / 2)
    if (pages[middle].top > offset) last = middle - 1
    else first = middle
  }
  return first
}

const visiblePages = computed(() => {
  if (!ready.value) return []
  const first = pageIndexAt(scrollTop.value)
  const last = pageIndexAt(scrollTop.value + viewportSize.value.height + 140)
  return layout.value.pages.slice(first, last + 1)
})

function setPage(next: number) {
  page.value = next
  pageInput.value = String(next)
  emit('pageChanged', next)
}

function syncScroll() {
  if (!viewport.value || !ready.value) return
  const element = viewport.value
  scrollTop.value = element.scrollTop
  const last = element.scrollHeight - element.clientHeight
  const current = last > 0 && last - element.scrollTop <= 1
    ? sizes.value.length : pageIndexAt(element.scrollTop + gap + 1) + 1
  if (current !== page.value) setPage(current)
}

function onScroll() {
  if (frame) return
  frame = requestAnimationFrame(() => {
    frame = 0
    syncScroll()
  })
}

function goTo(value: number | string) {
  const next = Number(value)
  if (viewport.value && sizes.value.length && Number.isSafeInteger(next) && String(value).trim()) {
    const requested = Math.min(Math.max(1, next), sizes.value.length)
    viewport.value.scrollTop = layout.value.pages[requested - 1].top - gap
    scrollTop.value = viewport.value.scrollTop
    setPage(requested)
  } else {
    pageInput.value = String(page.value)
  }
}

function onKeydown(event: KeyboardEvent) {
  if (!ready.value || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  if (event.target instanceof HTMLElement && event.target.closest('input, textarea, select, [contenteditable="true"]')) return
  const targets: Record<string, number> = {
    ArrowLeft: page.value - 1, PageUp: page.value - 1,
    ArrowRight: page.value + 1, PageDown: page.value + 1,
    Home: 1, End: sizes.value.length,
  }
  if (!Object.hasOwn(targets, event.key)) return
  event.preventDefault()
  goTo(targets[event.key])
}

watch([() => props.source, retry], async ([source], _, onCleanup) => {
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  loading.value = true
  ready.value = false
  error.value = ''
  sizes.value = []
  failedPages.value = new Set()
  try {
    const response = await fetch(source + 'layout/', { signal: controller.signal })
    if (!response.ok) throw new Error()
    const { pages } = await response.json()
    if (!Array.isArray(pages) || !pages.length || !pages.every(size =>
      Array.isArray(size) && size.length === 2 && size.every(n => Number.isFinite(n) && n > 0),
    )) throw new Error()
    if (!controller.signal.aborted) sizes.value = pages
  } catch {
    if (!controller.signal.aborted) error.value = '无法加载 PDF。请确认作品仍可访问后重试。'
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}, { immediate: true })

watch(layout, () => {
  if (!viewport.value || !sizes.value.length || !viewportSize.value.height) return
  goTo(page.value)
  viewport.value.scrollLeft = (viewport.value.scrollWidth - viewport.value.clientWidth) / 2
  ready.value = true
}, { flush: 'post' })

onMounted(() => {
  const element = viewport.value
  if (!element) return
  observer = new ResizeObserver(() => {
    const { clientWidth: width, clientHeight: height } = element
    if (width !== viewportSize.value.width || height !== viewportSize.value.height) viewportSize.value = { width, height }
  })
  observer.observe(element)
  if (!props.readerUrl) element.focus({ preventScroll: true })
})

onBeforeUnmount(() => {
  observer?.disconnect()
  if (frame) cancelAnimationFrame(frame)
})
</script>

<template>
  <div class="pdf-preview" :class="{ 'pdf-preview-standalone': !readerUrl }" @keydown="onKeydown">
    <div class="pdf-controls" :class="{ 'glass-panel': !readerUrl }">
      <template v-if="sizes.length > 1">
        <button type="button" class="glass-button icon-button" aria-label="上一页" :disabled="page <= 1" @click="goTo(page - 1)">
          <ChevronLeft :size="20" aria-hidden="true" />
        </button>
        <form class="pdf-jump" @submit.prevent="goTo(pageInput)">
          <input v-model="pageInput" type="text" inputmode="numeric" autocomplete="off" aria-label="页码"
            @focus="($event.target as HTMLInputElement).select()">
          <span>/ {{ sizes.length }}</span>
          <button type="submit" class="glass-button">跳转</button>
        </form>
        <button type="button" class="glass-button icon-button" aria-label="下一页" :disabled="page >= sizes.length" @click="goTo(page + 1)">
          <ChevronRight :size="20" aria-hidden="true" />
        </button>
      </template>
      <span v-else-if="sizes.length === 1">1 / 1</span>
      <a v-if="readerUrl" class="glass-button" :href="`${readerUrl}/${page}`" target="_blank" rel="noopener">
        <Maximize2 :size="16" aria-hidden="true" /> 独立阅读
      </a>
      <button v-else type="button" class="glass-button pdf-zoom" :aria-pressed="magnified" :disabled="!ready" @click="magnified = !magnified">
        <ZoomIn :size="17" aria-hidden="true" /> {{ magnified ? '适合页面' : '放大' }}
      </button>
    </div>
    <div ref="viewport" class="pdf-scroll" role="region" aria-label="PDF 阅读区" tabindex="0" :aria-busy="loading" @scroll.passive="onScroll">
      <div v-if="sizes.length" class="pdf-document" :style="{ width: layout.width + 'px', height: layout.height + 'px' }">
        <div v-for="sheet in visiblePages" :key="sheet.number" class="pdf-sheet"
          :style="{ top: sheet.top + 'px', width: sheet.width + 'px', height: sheet.height + 'px' }">
          <div v-if="failedPages.has(sheet.number)" class="pdf-load-error">
            <p class="form-error">无法预览第 {{ sheet.number }} 页。</p>
            <button class="glass-button" type="button" @click="failedPages.delete(sheet.number)">重试此页</button>
          </div>
          <img v-else :src="`${source}${sheet.number}/`" :alt="`PDF 第 ${sheet.number} 页`" decoding="async" draggable="false"
            @error="failedPages.add(sheet.number)">
        </div>
      </div>
      <div v-else class="pdf-scroll-status">
        <div v-if="error" class="pdf-load-error">
          <p class="form-error" role="alert">{{ error }}</p>
          <button class="glass-button" type="button" @click="retry += 1">重试</button>
        </div>
        <p v-else role="status">正在加载 PDF…</p>
      </div>
    </div>
    <span class="sr-only" aria-live="polite">{{ ready ? `第 ${page} 页，共 ${sizes.length} 页` : '' }}</span>
  </div>
</template>
