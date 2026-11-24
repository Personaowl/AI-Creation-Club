<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Download, FileArchive, Heart } from '@lucide/vue'
import GlassDialog from './GlassDialog.vue'
import { assetPath, fileSize, kindLabels, statusLabels } from '../works'
import type { Work } from '../works'

const props = defineProps<{ work: Work; favorite: boolean }>()
const emit = defineEmits<{ close: []; toggleFavorite: []; edit: [] }>()
const selected = ref(props.work.assets[0]?.id)
const videoError = ref(false)
const asset = computed(() => props.work.assets.find(item => item.id === selected.value))
watch(selected, () => { videoError.value = false })
</script>

<template>
  <GlassDialog :title="work.title" labelledby="preview-heading" :description="work.description" wide @close="emit('close')">
    <p v-if="work.review_note && work.is_mine" class="review-note">{{ work.review_note }}</p>
    <label v-if="work.assets.length > 1" class="form-field attachment-choice">
      <span>作品附件</span>
      <select v-model="selected">
        <option v-for="item in work.assets" :key="item.id" :value="item.id">{{ item.original_name }}</option>
      </select>
    </label>
    <div class="preview-stage">
      <template v-if="asset">
        <iframe v-if="asset.kind === 'slides'" :key="asset.id" :src="assetPath(work, asset, 'viewer')" title="PPT 在线预览" allowfullscreen />
        <video v-else-if="asset.kind === 'video' && !videoError" :key="asset.id" :src="assetPath(work, asset, 'video')" controls playsinline preload="metadata" @error="videoError = true" />
        <div v-else class="file-preview">
          <FileArchive :size="36" :stroke-width="1.4" />
          <strong>{{ asset.original_name }}</strong>
          <p v-if="videoError">浏览器无法播放此视频。</p>
          <p v-else>{{ work.can_download ? '下载压缩包以查看源码。' : '此作品目前仅展示附件信息。' }}</p>
        </div>
      </template>
      <div v-else class="file-preview">还没有上传附件。</div>
    </div>
    <footer class="preview-footer">
      <div class="preview-meta">
        <span v-if="work.is_mine">{{ statusLabels[work.status] }}</span>
        <span v-if="asset">{{ kindLabels[asset.kind] }} · {{ fileSize(asset.size) }}</span>
      </div>
      <div class="preview-actions">
        <button v-if="work.can_edit" type="button" class="glass-button" @click="emit('edit')">编辑作品</button>
        <button v-if="work.is_visible" type="button" class="glass-button" :aria-pressed="favorite" @click="emit('toggleFavorite')">
          <Heart :size="17" :class="{ 'heart-filled': favorite }" /> {{ favorite ? '已收藏' : '收藏' }}
        </button>
        <a v-if="work.can_download && asset" class="primary-button" :href="assetPath(work, asset, 'download')" download>
          <Download :size="17" /> 下载原件
        </a>
      </div>
    </footer>
  </GlassDialog>
</template>
