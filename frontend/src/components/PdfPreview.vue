<script setup lang="ts">
import { ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Maximize2, ZoomIn } from '@lucide/vue'

const props = defineProps<{ source: string }>()
const expanded = defineModel<boolean>('expanded', { required: true })
const page = ref(1)
const pageCount = ref(0)
const image = ref('')
const loading = ref(false)
const failed = ref(false)
const magnified = ref(false)
const opener = ref<HTMLButtonElement>()
const pageArea = ref<HTMLDivElement>()

watch(expanded, value => {
  if (value) pageArea.value?.focus()
  else {
    magnified.value = false
    opener.value?.focus()
  }
}, { flush: 'post' })

watch(page, async (number, _, onCleanup) => {
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
    const count = Number(response.headers.get('X-Page-Count'))
    if (!response.ok || !Number.isSafeInteger(count) || count < number) throw new Error()
    const bitmap = await response.blob()
    if (controller.signal.aborted) return
    imageUrl = URL.createObjectURL(bitmap)
    image.value = imageUrl
    pageCount.value = count
  } catch {
    if (!controller.signal.aborted) failed.value = true
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <div class="pdf-preview">
    <div ref="pageArea" class="pdf-page" :class="{ 'pdf-page-expanded': expanded }" :aria-busy="loading"
      :tabindex="expanded ? 0 : undefined" :role="expanded ? 'region' : undefined" :aria-label="expanded ? 'PDF 阅读区' : undefined">
      <button v-if="image && !expanded" ref="opener" class="pdf-open" type="button" :aria-label="`放大预览 PDF 第 ${page} 页`" @click="expanded = true">
        <img :src="image" :alt="`PDF 第 ${page} 页`">
        <span class="pdf-open-label"><Maximize2 :size="15" aria-hidden="true" /> 放大预览</span>
      </button>
      <img v-else-if="image" :class="{ 'pdf-page-zoomed': magnified }" :src="image" :alt="`PDF 第 ${page} 页`">
      <p v-else-if="failed" class="form-error" role="alert">无法预览此页 PDF。</p>
      <p v-else role="status">正在加载 PDF…</p>
    </div>
    <div v-if="expanded || pageCount > 1" class="slide-controls pdf-controls">
      <template v-if="pageCount > 1">
        <button type="button" class="glass-button icon-button" aria-label="上一页" :disabled="page <= 1 || loading" @click="page -= 1">
          <ChevronLeft :size="20" aria-hidden="true" />
        </button>
        <span aria-live="polite">{{ page }} / {{ pageCount }}</span>
        <button type="button" class="glass-button icon-button" aria-label="下一页" :disabled="page >= pageCount || loading" @click="page += 1">
          <ChevronRight :size="20" aria-hidden="true" />
        </button>
      </template>
      <button v-if="expanded" type="button" class="glass-button pdf-zoom" :aria-pressed="magnified" @click="magnified = !magnified">
        <ZoomIn :size="17" aria-hidden="true" /> 放大
      </button>
    </div>
  </div>
</template>
