<script setup lang="ts">
import { ref } from 'vue'
import { FileArchive, Music2 } from '@lucide/vue'
import { assetPath, kindLabels, pdfReaderPath } from '../works'
import type { Asset, Work } from '../works'
import PdfPreview from './PdfPreview.vue'

defineProps<{ work: Work; asset: Asset }>()
const mediaError = ref(false)
</script>

<template>
  <div class="preview-stage">
    <iframe v-if="asset.kind === 'slides'" :src="assetPath(work, asset, 'viewer')" title="PPT 在线预览" allowfullscreen />
    <PdfPreview v-else-if="asset.kind === 'pdf'" :source="assetPath(work, asset, 'pdf')" :reader-url="pdfReaderPath(work.id, asset.id)" />
    <video v-else-if="asset.kind === 'video' && !mediaError" :src="assetPath(work, asset, 'video')" controls playsinline
      :controlslist="work.can_download ? undefined : 'nodownload'" preload="metadata" @error="mediaError = true" />
    <div v-else-if="asset.kind === 'audio' && !mediaError" class="audio-preview">
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
  </div>
</template>
