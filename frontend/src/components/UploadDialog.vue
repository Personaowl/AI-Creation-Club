<script setup lang="ts">
import { computed, ref } from 'vue'
import { ImagePlus, Trash2, UploadCloud } from '@lucide/vue'
import GlassDialog from './GlassDialog.vue'
import CompetitionAssignment from './CompetitionAssignment.vue'
import { createWork, deleteAsset, submitWork, updateWork, uploadAsset } from '../api'
import { fileExtension, fileExtensions, fileFormatLabels, fileKinds, fileSize, photoExtensions, photoMaxBytes, photoMaxCount, workAttachments } from '../works'
import type { Asset, Competition, Work, WorkDetails } from '../works'

const props = defineProps<{ work?: Work; competitions: Competition[] }>()
const emit = defineEmits<{ close: []; saved: [work: Work] }>()
const title = ref(props.work?.title ?? '')
const description = ref(props.work?.description ?? '')
const competition = ref<number | null>(props.work?.competition ?? null)
const competitionYear = ref<number | null>(props.work?.competition_year ?? null)
const teamName = ref(props.work?.team_name ?? '')
const teamMembers = ref(props.work?.team_members ?? '')
const teamIntro = ref(props.work?.team_intro ?? '')
const awardInfo = ref(props.work?.award_info ?? '')
const ipDetails = ref(props.work?.ip_details ?? '')
const draft = ref(props.work)
const files = ref<File[]>([])
const photos = ref<File[]>([])
const attachments = computed(() => workAttachments(draft.value))
const savedPhotos = computed(() => draft.value?.assets.filter(asset => asset.kind === 'photo') ?? [])
const photoCount = computed(() => savedPhotos.value.length + photos.value.length)
const dragDepth = ref(0)
const saving = ref(false)
const errorMessage = ref('')
const photoError = ref('')
const awardInput = ref<HTMLInputElement>()

function workDetails(): WorkDetails {
  return {
    title: title.value.trim(),
    description: description.value.trim(),
    competition: competition.value,
    competition_year: competitionYear.value,
    team_name: teamName.value.trim(),
    team_members: teamMembers.value.trim(),
    team_intro: teamIntro.value.trim(),
    award_info: awardInfo.value.trim(),
    ip_details: ipDetails.value.trim(),
  }
}

function close() {
  if (saving.value) return
  const details = workDetails()
  const dirty = files.value.length || photos.value.length || Object.entries(details).some(([key, value]) =>
    value !== (draft.value?.[key as keyof WorkDetails] ?? (key === 'competition' || key === 'competition_year' ? null : '')),
  )
  if (dirty && !window.confirm('关闭后，未保存的填写内容和待上传文件会丢失。确定关闭？')) return
  emit('close')
}

function pick(selection?: FileList | null) {
  if (!selection?.length) return
  errorMessage.value = ''
  const picked = Array.from(selection)
  if (picked.some(file => !Object.hasOwn(fileKinds, fileExtension(file.name)) || file.size === 0)) {
    errorMessage.value = `请选择非空且受支持的文件（${fileFormatLabels}）。`
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

function onPhotoInput(event: Event) {
  const input = event.target as HTMLInputElement
  const picked = Array.from(input.files ?? [])
  input.value = ''
  if (!picked.length) return
  if (photoCount.value + picked.length > photoMaxCount) {
    photoError.value = `最多添加 ${photoMaxCount} 张团队照片。`
    return
  }
  if (picked.some(file => !photoExtensions.includes(fileExtension(file.name)) || !file.size || file.size > photoMaxBytes)) {
    photoError.value = '请选择非空的 JPG、PNG 或 WebP 图片，单张不超过 10 MB。'
    return
  }
  photoError.value = ''
  photos.value.push(...picked)
}

async function remove(asset: Asset) {
  if (!draft.value) return
  saving.value = true
  errorMessage.value = ''
  try {
    await deleteAsset(draft.value.id, asset.id)
    draft.value.assets = draft.value.assets.filter(item => item.id !== asset.id)
    if (asset.kind === 'photo') photoError.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法移除附件。'
  } finally {
    saving.value = false
  }
}

async function save(sendForReview: boolean) {
  errorMessage.value = ''
  if (saving.value || !title.value.trim()) return
  if (sendForReview && !awardInfo.value.trim()) {
    errorMessage.value = '请填写获奖情况，未获奖或评审中也可以填写。'
    awardInput.value?.focus()
    return
  }
  if (sendForReview && !files.value.length && !attachments.value.length) {
    errorMessage.value = '提交审核前请添加至少一个附件。'
    return
  }
  saving.value = true
  try {
    const details = workDetails()
    draft.value = draft.value
      ? await updateWork(draft.value.id, details)
      : await createWork(details)
    while (files.value.length) {
      const asset = await uploadAsset(draft.value.id, files.value[0])
      draft.value.assets.push(asset)
      files.value.shift()
    }
    while (photos.value.length) {
      const asset = await uploadAsset(draft.value.id, photos.value[0])
      draft.value.assets.push(asset)
      photos.value.shift()
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
    :title="props.work?.revision_of ? '编辑修改稿' : props.work ? '编辑作品' : '上传作品'"
    labelledby="upload-heading"
    :description="props.work?.revision_of ? '审核通过后更新原作品。' : undefined"
    wide
    keep-open-on-backdrop
    @close="close"
  >
    <form class="upload-form" @submit.prevent="save(true)">
      <label class="form-field">
        <span>作品名称 <small>必填</small></span>
        <input v-model="title" maxlength="120" required :disabled="saving">
      </label>
      <label class="form-field">
        <span>作品简介</span>
        <textarea v-model="description" maxlength="3000" rows="3" :disabled="saving" />
      </label>
      <CompetitionAssignment v-model:competition="competition" v-model:year="competitionYear" :competitions="competitions" :disabled="saving" />
      <label class="form-field">
        <span>获奖情况 <small>审核必填</small></span>
        <input ref="awardInput" v-model="awardInfo" maxlength="200" required :disabled="saving" placeholder="未获奖或评审中也可填写">
      </label>
      <label class="form-field">
        <span>知识产权情况</span>
        <textarea v-model="ipDetails" maxlength="1200" rows="2" :disabled="saving" placeholder="论文、专利、软著" />
      </label>
      <fieldset class="upload-team">
        <legend>团队风采</legend>
        <div class="upload-work-details">
          <label class="form-field">
            <span>团队名称</span>
            <input v-model="teamName" maxlength="120" :disabled="saving">
          </label>
          <label class="form-field">
            <span>团队成员</span>
            <textarea v-model="teamMembers" maxlength="600" rows="1" :disabled="saving" />
          </label>
        </div>
        <label class="form-field">
          <span>团队简介</span>
          <textarea v-model="teamIntro" maxlength="1200" rows="2" :disabled="saving" />
        </label>
        <div class="photo-picker">
          <label class="glass-button photo-pick" :class="{ 'photo-pick-disabled': saving || photoCount >= photoMaxCount }">
            <ImagePlus :size="17" aria-hidden="true" /> 添加比赛照片
            <input type="file" :accept="photoExtensions.map(ext => '.' + ext).join(',')" multiple aria-label="添加比赛照片"
              :disabled="saving || photoCount >= photoMaxCount" aria-describedby="upload-photo-hint" @change="onPhotoInput">
          </label>
          <small id="upload-photo-hint">{{ photoCount }}/{{ photoMaxCount }} 张 · JPG、PNG、WebP · 单张最多 10 MB</small>
        </div>
        <p v-if="photoError" class="form-error" role="alert">{{ photoError }}</p>
        <ul v-if="photoCount" class="upload-attachments">
          <li v-for="photo in savedPhotos" :key="photo.id">
            <span>{{ photo.original_name }} <small>{{ fileSize(photo.size) }}</small></span>
            <button class="glass-button icon-button" type="button" :aria-label="'移除 ' + photo.original_name" :disabled="saving" @click="remove(photo)"><Trash2 :size="16" /></button>
          </li>
          <li v-for="(photo, index) in photos" :key="index">
            <span>{{ photo.name }} <small>{{ fileSize(photo.size) }}</small></span>
            <button class="glass-button icon-button" type="button" :aria-label="'移除 ' + photo.name" :disabled="saving"
              @click="photos.splice(index, 1); photoError = ''"><Trash2 :size="16" /></button>
          </li>
        </ul>
      </fieldset>
      <div
        class="drop-zone"
        :class="{ 'drop-active': dragDepth > 0 }"
        @dragenter.prevent="dragDepth += 1"
        @dragover.prevent
        @dragleave.prevent="dragDepth = Math.max(0, dragDepth - 1)"
        @drop.prevent="dragDepth = 0; if (!saving) pick($event.dataTransfer?.files)"
      >
        <input type="file" :accept="fileExtensions.map(ext => '.' + ext).join(',')" multiple aria-label="选择作品附件" :disabled="saving" @change="onInput">
        <span class="upload-icon"><UploadCloud :size="24" /></span>
        <strong>添加作品附件</strong>
        <small>{{ fileFormatLabels }}</small>
      </div>
      <ul v-if="attachments.length || files.length" class="upload-attachments">
        <li v-for="asset in attachments" :key="asset.id">
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
