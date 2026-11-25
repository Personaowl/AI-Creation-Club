<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { ChevronDown, KeyRound, LogOut, UserRound } from '@lucide/vue'
import type { Account } from '../api'

defineProps<{ account: Account }>()
const emit = defineEmits<{ changePassword: []; logout: [] }>()
const panelId = useId()
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const open = ref(false)

function dismissOutside(event: Event) {
  if (open.value && event.target instanceof Node && !root.value?.contains(event.target)) {
    open.value = false
  }
}

function dismiss() {
  open.value = false
  trigger.value?.focus()
}

function onEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !open.value || event.defaultPrevented) return
  event.preventDefault()
  dismiss()
}

function changePassword() {
  dismiss()
  emit('changePassword')
}

function logout() {
  dismiss()
  emit('logout')
}

onMounted(() => {
  document.addEventListener('pointerdown', dismissOutside, true)
  document.addEventListener('focusin', dismissOutside)
  document.addEventListener('keydown', onEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', dismissOutside, true)
  document.removeEventListener('focusin', dismissOutside)
  document.removeEventListener('keydown', onEscape)
})
</script>

<template>
  <div ref="root" class="account-menu">
    <button ref="trigger" class="account-trigger glass-button" type="button"
      :aria-label="`账号菜单 · ${account.username}`" :aria-expanded="open" :aria-controls="panelId" @click="open = !open">
      <span class="account-avatar" aria-hidden="true"><UserRound :size="16" /></span>
      <span class="account-trigger-name">{{ account.username }}</span>
      <span class="account-trigger-compact">账号</span>
      <ChevronDown class="account-chevron" :size="14" aria-hidden="true" />
    </button>

    <div v-show="open" :id="panelId" class="account-panel glass-panel">
      <div class="account-identity">
        <span class="account-avatar" aria-hidden="true"><UserRound :size="19" /></span>
        <div class="account-identity-text">
          <strong>{{ account.username }}</strong>
          <span>{{ account.is_admin ? '管理员' : '成员' }}</span>
        </div>
      </div>
      <div class="account-actions">
        <button class="account-action" type="button" @click="changePassword">
          <KeyRound :size="18" aria-hidden="true" /> 修改密码
        </button>
      </div>
      <div class="account-exit">
        <button class="account-action" type="button" @click="logout">
          <LogOut :size="18" aria-hidden="true" /> 退出登录
        </button>
      </div>
    </div>
  </div>
</template>
