<script setup lang="ts">
import { ref } from 'vue'
import { changePassword } from '../api'
import GlassDialog from './GlassDialog.vue'

const emit = defineEmits<{ close: []; saved: [] }>()
const current = ref('')
const nextPassword = ref('')
const saving = ref(false)
const message = ref('')

async function submit() {
  message.value = ''
  saving.value = true
  try {
    await changePassword(current.value, nextPassword.value)
    emit('saved')
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法保存密码。'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <GlassDialog title="修改密码" labelledby="password-heading" @close="!saving && emit('close')">
    <form class="upload-form" @submit.prevent="submit">
      <label class="form-field">
        <span>当前密码</span>
        <input v-model="current" type="password" autocomplete="current-password" maxlength="256" required>
      </label>
      <label class="form-field">
        <span>新密码</span>
        <input v-model="nextPassword" type="password" autocomplete="new-password" minlength="8" maxlength="256" required>
      </label>
      <p v-if="message" class="form-error" role="alert">{{ message }}</p>
      <button class="primary-button" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存密码' }}</button>
    </form>
  </GlassDialog>
</template>
