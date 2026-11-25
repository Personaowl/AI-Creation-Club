<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Copy, UserRound } from '@lucide/vue'
import { issueMember, reclaimMember, reissueMember } from '../api'
import type { IssuedMember, MemberAccount } from '../api'
import GlassDialog from './GlassDialog.vue'

const props = defineProps<{ member?: MemberAccount }>()
const emit = defineEmits<{ close: []; updated: [member: MemberAccount] }>()
const member = ref(props.member)
const username = ref('')
const initialPassword = ref('')
const credentialInput = ref<HTMLInputElement>()
const busy = ref(false)
const error = ref('')
const feedback = ref('')
const dateFormat = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' })

async function save(request: () => Promise<MemberAccount | IssuedMember>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  feedback.value = ''
  try {
    const result = await request()
    const { initial_password, ...updated } = result as IssuedMember
    member.value = updated
    initialPassword.value = initial_password ?? ''
    emit('updated', updated)
    if (initial_password) {
      await nextTick()
      credentialInput.value?.focus()
    } else {
      feedback.value = '账号已回收。'
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法更新成员账号。'
  } finally {
    busy.value = false
  }
}

function issue() {
  if (username.value.trim()) void save(() => issueMember(username.value.trim()))
}

function changeState() {
  const current = member.value
  if (!current) return
  void save(() => current.is_active ? reclaimMember(current.id) : reissueMember(current.id))
}

async function copyPassword() {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(initialPassword.value)
      feedback.value = '密码已复制。'
      return
    }
  } catch {
    // Fall back to selecting the password on browsers that deny clipboard access.
  }
  credentialInput.value?.focus()
  credentialInput.value?.select()
  feedback.value = document.execCommand('copy') ? '密码已复制。' : '密码已选中，可按 Ctrl+C 复制。'
}
</script>

<template>
  <GlassDialog :title="initialPassword ? '账号已发放' : member ? '成员账号' : '发放账号'"
    labelledby="manage-member-heading" @close="!busy && emit('close')">
    <form v-if="!member" class="upload-form" @submit.prevent="issue">
      <label class="form-field">
        <span>用户名</span>
        <input v-model="username" autocomplete="off" maxlength="150" :disabled="busy" required>
      </label>
      <p class="manage-hint">保存后生成随机 8 位初始密码。</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="dialog-actions">
        <button class="primary-button" type="submit" :disabled="busy || !username.trim()">{{ busy ? '正在发放…' : '生成并发放' }}</button>
      </div>
    </form>
    <div v-else class="manage-member-detail">
      <div class="manage-identity">
        <span class="manage-symbol" aria-hidden="true"><UserRound :size="21" /></span>
        <strong>{{ member.username }}</strong>
        <span class="manage-status" :data-status="member.is_active ? 'approved' : 'draft'">{{ member.is_active ? '可登录' : '已回收' }}</span>
      </div>
      <template v-if="initialPassword">
        <label class="form-field" for="manage-initial-password">初始密码</label>
        <div class="manage-password">
          <input id="manage-initial-password" ref="credentialInput" :value="initialPassword" readonly autocomplete="off">
          <button class="glass-button" type="button" @click="copyPassword"><Copy :size="17" aria-hidden="true" /> 复制密码</button>
        </div>
        <p class="manage-hint">密码仅在此处显示，请复制后交给成员。</p>
      </template>
      <template v-else>
        <dl class="manage-member-times">
          <div><dt>发放时间</dt><dd>{{ dateFormat.format(new Date(member.date_joined)) }}</dd></div>
          <div><dt>最近登录</dt><dd>{{ member.last_login ? dateFormat.format(new Date(member.last_login)) : '尚未登录' }}</dd></div>
        </dl>
        <p class="manage-hint">{{ member.is_active ? '回收会停用账号和已有会话，成员原有作品会保留。' : '重新发放会启用账号，并生成新的 8 位密码。' }}</p>
      </template>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="feedback" class="manage-hint" role="status">{{ feedback }}</p>
      <div class="dialog-actions">
        <button v-if="initialPassword" class="primary-button" type="button" @click="emit('close')">完成</button>
        <button v-else type="button" class="glass-button" :class="{ 'manage-danger': member.is_active }" :disabled="busy" @click="changeState">
          {{ busy ? '正在处理…' : member.is_active ? '回收账号' : '重新发放账号' }}
        </button>
      </div>
    </div>
  </GlassDialog>
</template>
