<script setup lang="ts">
import { ref } from 'vue'
import { Trash2, UploadCloud } from '@lucide/vue'
import GlassDialog from './GlassDialog.vue'
import { createWork, deleteAsset, submitWork, updateWork, uploadAsset } from '../api'
import { fileExtension, fileKinds, fileSize } from '../works'
import type { Asset, Work } from '../works'

const props = defineProps<{ work?: Work }>()
const emit = defineEmits<{ close: []; saved: [work: Work] }>()
const title = ref(props.work?.title ?? '')
const description = ref(props.work?.description ?? '')
const draft = ref(props.work)
const files = ref<File[]>([])
const dragDepth = ref(0)
const saving = ref(false)
const errorMessage = ref('')

function pick(selection?: FileList | null) {
  if (!selection?.length) return
  errorMessage.value = ''
  const picked = Array.from(selection)
  if (picked.some(file => !Object.hasOwn(fileKinds, fileExtension(file.name)) || file.size === 0)) {
    errorMessage.value = '请选择有效的 PPT、PPTX、MP4、WebM 或 ZIP 文件。'
    return
  }
  files.value.push(...picked)
  if (!title.value.trim() && picked.length === 1) title.value = picked[0].name.replace(/\.[^.]+$/, '').slice(0, 120)
}

function onInput(event: Event) {
  const input = event.target as HTMLInputElement
  pick(input.files)
  input.value = ''
}

async function remove(asset: Asset) {
  if (!draft.value) return
  saving.value = true
  errorMessage.value = ''
  try {
    await deleteAsset(draft.value.id, asset.id)
    draft.value.assets = draft.value.assets.filter(item => item.id !== asset.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法移除附件。'
  } finally {
    saving.value = false
  }
}

async function save(sendForReview: boolean) {
  errorMessage.value = ''
  if (saving.value || !title.value.trim()) return
  if (sendForReview && !files.value.length && !draft.value?.assets.length) {
    errorMessage.value = '提交审核前请添加至少一个附件。'
    return
  }
  saving.value = true
  try {
    draft.value = draft.value
      ? await updateWork(draft.value.id, title.value.trim(), description.value.trim())
      : await createWork(title.value.trim(), description.value.trim())
    while (files.value.length) {
      const asset = await uploadAsset(draft.value.id, files.value[0])
      draft.value.assets.push(asset)
      files.value.shift()
    }
    if (sendForReview) draft.value = await submitWork(draft.value.id)
    emit('saved', draft.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法保存作品。'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <GlassDialog
    :title="props.work ? '编辑作品' : '上传作品'"
    labelledby="upload-heading"
    description="把同一件作品的演示文稿、视频和源码添加为附件，然后提交审核。"
    @close="!saving && emit('close')"
  >
    <form class="upload-form" @submit.prevent="save(true)">
      <label class="form-field">
        <span>作品名称</span>
        <input v-model="title" maxlength="120" required :disabled="saving" placeholder="输入竞赛作品名称">
      </label>
      <label class="form-field">
        <span>作品简介 <small>选填</small></span>
        <textarea v-model="description" maxlength="3000" rows="3" :disabled="saving" placeholder="简单介绍作品" />
      </label>
      <div
        class="drop-zone"
        :class="{ 'drop-active': dragDepth > 0 }"
        @dragenter.prevent="dragDepth += 1"
        @dragover.prevent
        @dragleave.prevent="dragDepth = Math.max(0, dragDepth - 1)"
        @drop.prevent="dragDepth = 0; if (!saving) pick($event.dataTransfer?.files)"
      >
        <input type="file" accept=".ppt,.pptx,.mp4,.webm,.zip" multiple aria-label="选择作品附件" :disabled="saving" @change="onInput">
        <span class="upload-icon"><UploadCloud :size="24" /></span>
        <strong>拖入文件，或点击选择</strong>
        <small>PPT、PPTX、MP4、WebM、ZIP</small>
      </div>
      <ul v-if="draft?.assets.length || files.length" class="upload-attachments">
        <li v-for="asset in draft?.assets" :key="asset.id">
          <span>{{ asset.original_name }} <small>{{ fileSize(asset.size) }}</small></span>
          <button class="glass-button icon-button" type="button" :aria-label="'移除 ' + asset.original_name" :disabled="saving" @click="remove(asset)"><Trash2 :size="16" /></button>
        </li>
        <li v-for="(file, index) in files" :key="index">
          <span>{{ file.name }} <small>{{ fileSize(file.size) }}</small></span>
          <button class="glass-button icon-button" type="button" :aria-label="'移除 ' + file.name" :disabled="saving" @click="files.splice(index, 1)"><Trash2 :size="16" /></button>
        </li>
      </ul>
      <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
      <footer class="dialog-actions">
        <button type="button" class="glass-button" :disabled="saving || !title.trim()" @click="save(false)">保存草稿</button>
        <button type="submit" class="primary-button" :disabled="saving">{{ saving ? '正在保存…' : '提交审核' }}</button>
      </footer>
    </form>
  </GlassDialog>
</template>
