<script setup lang="ts">
import { ref } from 'vue'
import { Pencil, Plus, Trash2 } from '@lucide/vue'
import { createCompetition, deleteCompetition, renameCompetition } from '../api'
import type { Competition } from '../works'
import GlassDialog from './GlassDialog.vue'

defineProps<{ competitions: Competition[] }>()
const emit = defineEmits<{ changed: [id: number, updated?: Competition] }>()
const name = ref('')
const saving = ref(false)
const error = ref('')
const message = ref('')
const action = ref<{ type: 'rename' | 'delete'; competition: Competition }>()
const editName = ref('')
const actionError = ref('')

async function create() {
  if (saving.value || !name.value.trim()) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const competition = await createCompetition(name.value.trim())
    emit('changed', competition.id, competition)
    name.value = ''
    message.value = '已创建比赛分类「' + competition.name + '」。'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法创建比赛分类。'
  } finally {
    saving.value = false
  }
}

function openAction(type: 'rename' | 'delete', competition: Competition) {
  editName.value = competition.name
  actionError.value = ''
  action.value = { type, competition }
}

async function runAction() {
  const current = action.value
  if (!current || saving.value || (current.type === 'rename' && !editName.value.trim())) return
  saving.value = true
  actionError.value = ''
  message.value = ''
  try {
    const { id, name } = current.competition
    if (current.type === 'rename') {
      const renamed = await renameCompetition(id, editName.value.trim())
      emit('changed', id, renamed)
      message.value = '已将比赛分类改名为「' + renamed.name + '」。'
    } else {
      await deleteCompetition(id)
      emit('changed', id)
      message.value = '已删除比赛分类「' + name + '」。'
    }
    action.value = undefined
  } catch (reason) {
    actionError.value = reason instanceof Error ? reason.message : '操作失败，请稍后重试。'
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
        <Plus :size="18" aria-hidden="true" /> {{ saving && !action ? '正在创建…' : '创建分类' }}
      </button>
      <p v-if="error" id="competition-form-error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="message" class="manage-hint" role="status">{{ message }}</p>
    </form>
    <div class="manage-panel-heading">
      <h2 id="competition-list-title">现有分类</h2>
    </div>
    <ul v-if="competitions.length" class="manage-rows">
      <li v-for="competition in competitions" :key="competition.id" class="competition-row">
        <span>{{ competition.name }}</span>
        <div class="competition-actions">
          <button class="glass-button" type="button" :aria-label="'编辑分类 ' + competition.name" :disabled="saving" @click="openAction('rename', competition)">
            <Pencil :size="16" aria-hidden="true" /> 编辑
          </button>
          <button class="glass-button manage-danger" type="button" :aria-label="'删除分类 ' + competition.name" :disabled="saving" @click="openAction('delete', competition)">
            <Trash2 :size="16" aria-hidden="true" /> 删除
          </button>
        </div>
      </li>
    </ul>
    <p v-else class="manage-empty">还没有比赛分类。</p>
  </section>
  <GlassDialog v-if="action" :title="action.type === 'rename' ? '编辑比赛分类' : '删除比赛分类'" labelledby="competition-action-title"
    :description="action.type === 'delete' ? '删除「' + action.competition.name + '」后，该分类下的作品会移到「未分类」。' : undefined"
    @close="!saving && (action = undefined)">
    <form class="competition-action-form" @submit.prevent="runAction">
      <label v-if="action.type === 'rename'" class="form-field">
        <span>比赛名称</span>
        <input v-model="editName" maxlength="120" required autofocus :readonly="saving"
          :aria-invalid="actionError ? 'true' : undefined" :aria-describedby="actionError ? 'competition-action-error' : undefined">
      </label>
      <p v-if="actionError" id="competition-action-error" class="form-error" role="alert">{{ actionError }}</p>
      <footer class="dialog-actions">
        <button class="glass-button" type="button" :disabled="saving" @click="action = undefined">取消</button>
        <button v-if="action.type === 'rename'" class="primary-button" type="submit" :disabled="saving || !editName.trim()">
          {{ saving ? '正在保存…' : '保存修改' }}
        </button>
        <button v-else class="glass-button manage-danger" type="button" :disabled="saving" @click="runAction">
          {{ saving ? '正在删除…' : '确认删除' }}
        </button>
      </footer>
    </form>
  </GlassDialog>
</template>
