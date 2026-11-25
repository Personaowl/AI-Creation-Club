<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight, Eye, EyeOff } from '@lucide/vue'
import { signIn } from '../api'
import type { Account } from '../api'
import { platformName } from '../branding'

const props = defineProps<{ connectionError: string }>()
const emit = defineEmits<{ signedIn: [user: Account]; retry: [] }>()
const username = ref('')
const password = ref('')
const passwordVisible = ref(false)
const waiting = ref(false)
const message = ref('')

async function logIn() {
  if (waiting.value || props.connectionError) return
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
  <main class="login-layout login-page">
    <header class="login-editorial">
      <h1 class="login-wordmark" :aria-label="platformName">
        <span class="login-wordmark-main">AI Creation</span>
        <em class="login-wordmark-accent">Club</em>
      </h1>
    </header>

    <section class="login-entry" aria-labelledby="login-heading">
      <div class="login-intro">
        <h2 id="login-heading">登录作品平台</h2>
        <p>使用管理员发放的账号登录。</p>
      </div>
      <form class="login-form" @submit.prevent="logIn">
        <div class="form-field login-field">
          <label for="login-username">账号</label>
          <input id="login-username" v-model="username" autocomplete="username" maxlength="150" :disabled="waiting" required>
        </div>
        <div class="form-field login-field">
          <label for="login-password">密码</label>
          <div class="login-password">
            <input id="login-password" v-model="password" :type="passwordVisible ? 'text' : 'password'"
              autocomplete="current-password" maxlength="256" :disabled="waiting" required>
            <button type="button" class="login-password-toggle" :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
              @click="passwordVisible = !passwordVisible">
              <EyeOff v-if="passwordVisible" :size="19" aria-hidden="true" />
              <Eye v-else :size="19" aria-hidden="true" />
            </button>
          </div>
        </div>
        <button v-if="props.connectionError" class="primary-button login-submit" type="button" @click="emit('retry')">
          重新连接 <ArrowRight :size="18" aria-hidden="true" />
        </button>
        <button v-else class="primary-button login-submit" type="submit" :disabled="waiting">
          {{ waiting ? '登录中…' : '登录' }} <ArrowRight :size="18" aria-hidden="true" />
        </button>
        <p v-if="props.connectionError || message" class="form-error login-feedback" role="alert">{{ props.connectionError || message }}</p>
      </form>
    </section>
  </main>
</template>
