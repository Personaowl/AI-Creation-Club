<script setup lang="ts">
import { ref } from 'vue'
import { Aperture } from '@lucide/vue'
import { signIn } from '../api'
import type { Account } from '../api'
import { platformName } from '../branding'

const props = defineProps<{ connectionError: string }>()
const emit = defineEmits<{ signedIn: [user: Account]; retry: [] }>()
const username = ref('')
const password = ref('')
const waiting = ref(false)
const message = ref('')

async function logIn() {
  waiting.value = true
  message.value = ''
  try {
    const account = await signIn(username.value.trim(), password.value)
    password.value = ''
    if (account) emit('signedIn', account)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '暂时无法登录。'
  } finally {
    waiting.value = false
  }
}
</script>

<template>
  <main class="login-layout">
    <section class="login-card glass-panel">
      <div class="brand">
        <span class="brand-mark glass-panel"><Aperture :size="21" /></span>
        <span>{{ platformName }}</span>
      </div>
      <h1>登录作品平台</h1>
      <p>使用管理员发放的账号登录。</p>
      <form class="upload-form" @submit.prevent="logIn">
        <label class="form-field">
          <span>账号</span>
          <input v-model="username" autocomplete="username" maxlength="150" required autofocus>
        </label>
        <label class="form-field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" maxlength="256" required>
        </label>
        <p v-if="props.connectionError || message" class="form-error" role="alert">{{ props.connectionError || message }}</p>
        <button v-if="props.connectionError" class="glass-button" type="button" @click="emit('retry')">重新连接</button>
        <button v-else class="primary-button" type="submit" :disabled="waiting">{{ waiting ? '登录中…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>
