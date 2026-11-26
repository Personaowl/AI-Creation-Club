<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'
import { ChevronLeft, ChevronRight, Maximize2 } from '@lucide/vue'
import { assetPath } from '../works'
import type { Asset, Work } from '../works'
import GlassDialog from './GlassDialog.vue'

const props = defineProps<{ work: Work; photos: Asset[] }>()
const titleId = useId()
const selected = ref<string>()
const failed = ref<string>()
const index = computed(() => props.photos.findIndex(photo => photo.id === selected.value))
const photo = computed(() => props.photos[index.value])
let opener: HTMLButtonElement | undefined
let swipeOrigin: { id: number; x: number; y: number } | undefined

function open(id: string, event: MouseEvent) {
  opener = event.currentTarget as HTMLButtonElement
  failed.value = undefined
  selected.value = id
}

async function close() {
  selected.value = undefined
  swipeOrigin = undefined
  await nextTick()
  opener?.focus({ preventScroll: true })
  opener = undefined
}

function step(direction: number) {
  const length = props.photos.length
  if (length < 2 || index.value < 0) return
  failed.value = undefined
  selected.value = props.photos[(index.value + length + direction) % length].id
}

function navigate(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || props.photos.length < 2) return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    step(event.key === 'ArrowLeft' ? -1 : 1)
  }
}

function startSwipe(event: PointerEvent) {
  if (event.pointerType === 'touch' && event.isPrimary) swipeOrigin = { id: event.pointerId, x: event.clientX, y: event.clientY }
}

function finishSwipe(event: PointerEvent) {
  if (!swipeOrigin || swipeOrigin.id !== event.pointerId) return
  const x = event.clientX - swipeOrigin.x
  const y = event.clientY - swipeOrigin.y
  swipeOrigin = undefined
  if (Math.abs(x) > 36 && Math.abs(x) > Math.abs(y) * 1.5) step(x < 0 ? 1 : -1)
}
</script>

<template>
  <ul class="team-photos">
    <li v-for="(item, position) in photos" :key="item.id">
      <button type="button" class="photo-thumbnail" :aria-label="'放大照片 ' + (position + 1) + ' · ' + item.original_name"
        @click="open(item.id, $event)">
        <img :src="assetPath(work, item, 'photo')" :alt="'比赛照片 ' + (position + 1) + ' · ' + item.original_name"
          loading="lazy" decoding="async">
        <span class="photo-expand" aria-hidden="true"><Maximize2 :size="15" /></span>
      </button>
    </li>
  </ul>

  <GlassDialog v-if="photo" class="photo-dialog" title="团队风采" :labelledby="titleId" @close="close" @keydown="navigate">
    <figure class="photo-viewer">
      <div class="photo-viewer-stage" @pointerdown="startSwipe" @pointerup="finishSwipe" @pointercancel="swipeOrigin = undefined">
        <p v-if="failed === photo.id" class="form-error" role="alert">这张照片暂时无法加载。</p>
        <img v-else :key="photo.id" :src="assetPath(work, photo, 'photo')" :alt="'比赛照片 ' + (index + 1) + ' · ' + photo.original_name"
          decoding="async" draggable="false" @error="failed = photo.id">
      </div>
      <figcaption v-if="photos.length > 1" class="photo-viewer-controls">
        <button class="glass-button icon-button" type="button" aria-label="上一张照片" @click="step(-1)">
          <ChevronLeft :size="22" aria-hidden="true" />
        </button>
        <span aria-live="polite"><span class="sr-only">当前照片 </span>{{ index + 1 }} / {{ photos.length }}</span>
        <button class="glass-button icon-button" type="button" aria-label="下一张照片" @click="step(1)">
          <ChevronRight :size="22" aria-hidden="true" />
        </button>
      </figcaption>
    </figure>
  </GlassDialog>
</template>
