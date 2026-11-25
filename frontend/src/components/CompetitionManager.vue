<script setup lang="ts">
import { ref } from 'vue'
import { Plus } from '@lucide/vue'
import { createCompetition } from '../api'
import type { Competition } from '../works'

defineProps<{ competitions: Competition[] }>()
const emit = defineEmits<{ created: [competition: Competition] }>()
const name = ref('')
const saving = ref(false)
const error = ref('')
const message = ref('')

async function create() {
  if (saving.value || !name.value.trim()) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const competition = await createCompetition(name.value.trim())
    emit('created', competition)
    name.value = ''
    message.value = '已创建比赛分类「' + competition.name + '」。'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法创建比赛分类。'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="manage-panel glass-panel" aria-labelledby="competition-list-title">
    <form class="competition-form" @submit.prevent="create">
      <label class="form-field">
        <span>比赛名称</span>
        <input v-model="name" maxlength="120" required :readonly="saving"
          :aria-invalid="error ? 'true' : undefined" :aria-describedby="error ? 'competition-form-error' : undefined">
      </label>
      <button class="primary-button manage-primary" type="submit" :disabled="saving || !name.trim()">
        <Plus :size="18" aria-hidden="true" /> {{ saving ? '正在创建…' : '创建分类' }}
      </button>
      <p v-if="error" id="competition-form-error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="message" class="manage-hint" role="status">{{ message }}</p>
    </form>
    <div class="manage-panel-heading">
      <h2 id="competition-list-title">现有分类</h2>
    </div>
    <ul v-if="competitions.length" class="manage-rows">
      <li v-for="competition in competitions" :key="competition.id" class="competition-row">{{ competition.name }}</li>
    </ul>
    <p v-else class="manage-empty">还没有比赛分类。</p>
  </section>
</template>
