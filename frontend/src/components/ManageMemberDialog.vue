<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { Copy, UserRound } from '@lucide/vue'
import { issueMember, readIssuedPassword, reclaimMember, reissueMember, resetMemberPassword } from '../api'
import type { IssuedMember, MemberAccount } from '../api'
import GlassDialog from './GlassDialog.vue'

const props = defineProps<{ member?: MemberAccount }>()
const emit = defineEmits<{ close: []; updated: [member: MemberAccount] }>()
const member = ref(props.member)
const username = ref('')
const initialPassword = ref('')
const credentialInput = ref<HTMLInputElement>()
const issuedNow = ref(false)
const loadingPassword = ref(false)
const passwordError = ref('')
const resetOpen = ref(false)
const resetButton = ref<HTMLButtonElement>()
const confirmResetButton = ref<HTMLButtonElement>()
const busy = ref(false)
const error = ref('')
const feedback = ref('')
const dateFormat = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' })

async function loadPassword() {
  const current = member.value
  if (!current?.is_active || loadingPassword.value || busy.value) return
  loadingPassword.value = true
  passwordError.value = ''
  try {
    const result = await readIssuedPassword(current.id)
    initialPassword.value = result.initial_password ?? ''
  } catch (reason) {
    passwordError.value = reason instanceof Error ? reason.message : '无法读取发放密码。'
  } finally {
    loadingPassword.value = false
  }
}

onMounted(loadPassword)

async function save(request: () => Promise<MemberAccount | IssuedMember>, message: string, freshIssue = false) {
  if (busy.value || loadingPassword.value) return
  busy.value = true
  error.value = ''
  feedback.value = ''
  try {
    const result = await request()
    const { initial_password, ...updated } = result as IssuedMember
    member.value = updated
    initialPassword.value = initial_password ?? ''
    issuedNow.value = freshIssue
    resetOpen.value = false
    passwordError.value = ''
    feedback.value = message
    emit('updated', updated)
    if (initial_password) {
      await nextTick()
      credentialInput.value?.focus()
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法更新成员账号。'
  } finally {
    busy.value = false
  }
}

function issue() {
  if (username.value.trim()) void save(() => issueMember(username.value.trim()), '', true)
}

function changeState() {
  const current = member.value
  if (!current) return
  if (current.is_active) void save(() => reclaimMember(current.id), '账号已回收。')
  else void save(() => reissueMember(current.id), '', true)
}

async function toggleReset(open: boolean) {
  resetOpen.value = open
  error.value = ''
  await nextTick()
  if (open) confirmResetButton.value?.focus()
  else resetButton.value?.focus()
}

function resetPassword() {
  const current = member.value
  if (current?.is_active && resetOpen.value) {
    void save(() => resetMemberPassword(current.id), '已生成新的 8 位密码。')
  }
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
  <GlassDialog :title="issuedNow ? '账号已发放' : member ? '成员账号' : '发放账号'"
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
      <div v-if="member.is_active" class="manage-member-credential" :aria-busy="loadingPassword">
        <template v-if="initialPassword">
          <label class="form-field" for="manage-initial-password">初始密码</label>
          <div class="manage-password">
            <input id="manage-initial-password" ref="credentialInput" type="text" :value="initialPassword" readonly autocomplete="off"
              spellcheck="false" autocapitalize="none">
            <button class="glass-button" type="button" :disabled="busy" @click="copyPassword"><Copy :size="17" aria-hidden="true" /> 复制密码</button>
          </div>
        </template>
        <p v-else-if="loadingPassword" class="manage-hint" role="status">正在读取发放密码…</p>
        <div v-else-if="passwordError" class="manage-credential-error">
          <p class="form-error" role="alert">{{ passwordError }}</p>
          <button class="glass-button" type="button" :disabled="busy" @click="loadPassword">重试</button>
        </div>
        <p v-else class="manage-hint">暂无可查看的发放密码。可为该成员生成新密码。</p>
      </div>
      <dl class="manage-member-times">
        <div><dt>发放时间</dt><dd>{{ dateFormat.format(new Date(member.date_joined)) }}</dd></div>
        <div><dt>最近登录</dt><dd>{{ member.last_login ? dateFormat.format(new Date(member.last_login)) : '尚未登录' }}</dd></div>
      </dl>
      <p v-if="!member.is_active" class="manage-hint">重新发放会启用账号，并生成新的 8 位密码。</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="feedback" class="manage-hint" role="status">{{ feedback }}</p>
      <div v-if="resetOpen" class="manage-member-credential">
        <p class="manage-hint">将生成新的 8 位密码，旧密码和成员当前的登录会话会失效。</p>
        <div class="dialog-actions">
          <button class="glass-button" type="button" :disabled="busy" @click="toggleReset(false)">取消</button>
          <button ref="confirmResetButton" class="primary-button" type="button" :disabled="busy" @click="resetPassword">
            {{ busy ? '正在重置…' : '确认重置' }}
          </button>
        </div>
      </div>
      <div v-else class="dialog-actions manage-member-actions">
        <button v-if="issuedNow" class="primary-button" type="button" @click="emit('close')">完成</button>
        <button v-if="member.is_active && !issuedNow" ref="resetButton" class="glass-button" type="button"
          :disabled="busy || loadingPassword" @click="toggleReset(true)">重置密码</button>
        <button v-if="!issuedNow" type="button" class="glass-button" :class="{ 'manage-danger': member.is_active }"
          :disabled="busy || loadingPassword" @click="changeState">
          {{ busy ? '正在处理…' : member.is_active ? '回收账号' : '重新发放账号' }}
        </button>
      </div>
    </div>
  </GlassDialog>
</template>
