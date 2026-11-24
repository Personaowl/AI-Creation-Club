<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { X } from '@lucide/vue'

defineProps<{ title: string; labelledby: string; description?: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()

onMounted(async () => {
  await nextTick()
  dialog.value?.showModal()
})

onBeforeUnmount(() => dialog.value?.close())

function closeOnBackdrop(event: PointerEvent) {
  if (event.target !== dialog.value || !dialog.value) return
  const bounds = dialog.value.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right ||
      event.clientY < bounds.top || event.clientY > bounds.bottom) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="glass-dialog"
      :class="{ 'dialog-wide': wide }"
      :aria-labelledby="labelledby"
      @cancel.prevent="emit('close')"
      @pointerdown="closeOnBackdrop"
    >
      <header class="dialog-heading">
        <div>
          <h2 :id="labelledby">{{ title }}</h2>
          <p v-if="description">{{ description }}</p>
        </div>
        <button class="glass-button icon-button" type="button" aria-label="关闭弹窗" @click="emit('close')">
          <X :size="21" />
        </button>
      </header>
      <slot />
    </dialog>
  </Teleport>
</template>
