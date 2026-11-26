<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watchEffect } from 'vue'
import { ArrowLeft, Download } from '@lucide/vue'
import { readWork, RequestError } from '../api'
import { brandName } from '../branding'
import { assetPath, pdfReaderPath, workDetailPath } from '../works'
import type { Work } from '../works'
import PdfPreview from './PdfPreview.vue'

const props = defineProps<{ workId: string; assetId: string; initialPage: number }>()
const work = ref<Work>()
const asset = computed(() => work.value?.assets.find(item => item.id === props.assetId && item.kind === 'pdf'))
const error = ref('')
const previousTitle = document.title

watchEffect(() => {
  document.title = (asset.value?.original_name ?? 'PDF 阅读') + ' · ' + brandName
})
onBeforeUnmount(() => { document.title = previousTitle })

onMounted(async () => {
  try {
    work.value = await readWork(props.workId)
    if (!asset.value) error.value = '无法查看此 PDF。'
  } catch (reason) {
    error.value = reason instanceof RequestError && [403, 404].includes(reason.status)
      ? '无法查看此 PDF。作品可能已下架，或当前账号没有查看权限。'
      : '无法加载 PDF，请刷新后重试。'
  }
})

function rememberPage(page: number) {
  window.history.replaceState(window.history.state, '', pdfReaderPath(props.workId, props.assetId) + '/' + page)
}
</script>

<template>
  <main class="pdf-reader" aria-labelledby="pdf-reader-heading">
    <header class="pdf-reader-header glass-panel">
      <a class="glass-button" :href="workDetailPath(workId)"><ArrowLeft :size="17" aria-hidden="true" /> 返回作品详情</a>
      <h1 id="pdf-reader-heading">{{ asset?.original_name || 'PDF 阅读' }}</h1>
      <a v-if="work?.can_download && asset" class="glass-button" :href="assetPath(work, asset, 'download')" download>
        <Download :size="17" aria-hidden="true" /> 下载原件
      </a>
    </header>
    <PdfPreview v-if="work && asset" :source="assetPath(work, asset, 'pdf')" :initial-page="initialPage" @page-changed="rememberPage" />
    <p v-else-if="error" class="pdf-reader-status glass-panel form-error" role="alert">{{ error }}</p>
    <p v-else class="pdf-reader-status glass-panel" role="status">正在加载 PDF…</p>
  </main>
</template>
