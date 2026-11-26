<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, Download } from '@lucide/vue'
import { assetPath, fileSize, kindLabels, workAttachments } from '../works'
import type { Work } from '../works'
import AttachmentMedia from './AttachmentMedia.vue'
import GlassDialog from './GlassDialog.vue'
import WorkOverview from './WorkOverview.vue'

const props = defineProps<{ work: Work; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const attachments = computed(() => workAttachments(props.work))
const selected = ref(attachments.value[0]?.id)
const asset = computed(() => attachments.value.find(item => item.id === selected.value))

watch(attachments, items => {
  if (!items.some(item => item.id === selected.value)) selected.value = items[0]?.id
})
</script>

<template>
  <GlassDialog :title="work.title" labelledby="preview-heading" :description="work.description" wide @close="!busy && emit('close')">
    <slot name="context" />
    <p v-if="work.review_note" class="review-note">{{ work.review_note }}</p>
    <p v-if="work.competition_name" class="manage-work-context">比赛名称 {{ work.competition_name }}</p>
    <WorkOverview :work="work" class="moderation-overview" />
    <label v-if="attachments.length > 1" class="form-field attachment-choice">
      <span>作品附件</span>
      <span class="attachment-select">
        <select v-model="selected">
          <option v-for="item in attachments" :key="item.id" :value="item.id">{{ item.original_name }}</option>
        </select>
        <ChevronDown :size="16" aria-hidden="true" />
      </span>
    </label>
    <AttachmentMedia v-if="asset" :key="asset.id" :work="work" :asset="asset" />
    <div v-else class="file-preview preview-stage">还没有上传附件。</div>
    <footer v-if="asset" class="preview-footer">
      <span class="preview-meta">{{ kindLabels[asset.kind] }} · {{ fileSize(asset.size) }}</span>
      <a v-if="work.can_download" class="primary-button" :href="assetPath(work, asset, 'download')" download>
        <Download :size="17" aria-hidden="true" /> 下载原件
      </a>
    </footer>
    <slot name="management" />
  </GlassDialog>
</template>
