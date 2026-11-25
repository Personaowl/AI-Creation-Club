<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { addComment, deleteComment, readComments } from '../api'
import type { WorkComment } from '../works'

const props = defineProps<{ workId: string }>()
const date = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' })
const items = ref<WorkComment[]>([])
const next = ref<number | null>()
const body = ref('')
const loading = ref(false)
const posting = ref(false)
const confirming = ref<number>()
const deleting = ref<number>()
const loadError = ref('')
const actionError = ref('')
const notice = ref('')

async function loadMore() {
  if (loading.value || next.value === null) return
  loading.value = true
  loadError.value = ''
  try {
    const page = await readComments(props.workId, next.value)
    const existing = new Set(items.value.map(item => item.id))
    items.value.push(...page.items.filter(item => !existing.has(item.id)))
    next.value = page.next_before
  } catch (reason) {
    loadError.value = reason instanceof Error ? reason.message : '暂时无法读取评论。'
  } finally {
    loading.value = false
  }
}

async function post() {
  if (posting.value || loading.value || !body.value.trim()) return
  posting.value = true
  actionError.value = ''
  notice.value = ''
  try {
    items.value.unshift(await addComment(props.workId, body.value.trim()))
    body.value = ''
    notice.value = '评论已发布。'
  } catch (reason) {
    actionError.value = reason instanceof Error ? reason.message : '暂时无法发布评论。'
  } finally {
    posting.value = false
  }
}

async function remove(id: number) {
  if (deleting.value !== undefined) return
  deleting.value = id
  actionError.value = ''
  notice.value = ''
  try {
    await deleteComment(props.workId, id)
    items.value = items.value.filter(item => item.id !== id)
    confirming.value = undefined
    notice.value = '评论已删除。'
  } catch (reason) {
    actionError.value = reason instanceof Error ? reason.message : '暂时无法删除评论。'
  } finally {
    deleting.value = undefined
  }
}

onMounted(loadMore)
</script>

<template>
  <section class="work-comments" aria-label="作品评论">
    <h3>评论</h3>
    <form class="comment-form" @submit.prevent="post">
      <label class="form-field">
        <span>写评论</span>
        <textarea v-model="body" rows="2" maxlength="500" required :readonly="posting" />
      </label>
      <button class="primary-button" type="submit" :disabled="loading || posting || !body.trim()">
        {{ posting ? '正在发布…' : '发布评论' }}
      </button>
    </form>
    <p v-if="notice" class="comment-hint" role="status">{{ notice }}</p>
    <p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p>
    <ul v-if="items.length" class="comment-list">
      <li v-for="item in items" :key="item.id">
        <div class="comment-meta">
          <strong>{{ item.author }}</strong>
          <time :datetime="item.created_at">{{ date.format(new Date(item.created_at)) }}</time>
        </div>
        <p>{{ item.body }}</p>
        <div v-if="confirming === item.id" class="comment-actions" role="group" aria-label="确认删除评论">
          <button class="glass-button" type="button" :disabled="deleting !== undefined" @click="remove(item.id)">确认删除</button>
          <button class="glass-button" type="button" :disabled="deleting !== undefined" @click="confirming = undefined">取消</button>
        </div>
        <button v-else-if="item.can_delete" class="glass-button comment-delete" type="button"
          :aria-label="'删除 ' + item.author + ' 的评论'" :disabled="deleting !== undefined" @click="confirming = item.id">
          删除
        </button>
      </li>
    </ul>
    <p v-else-if="!loading && !loadError" class="comment-hint">还没有评论。</p>
    <p v-if="loadError" class="form-error" role="alert">{{ loadError }}</p>
    <p v-if="loading" class="comment-hint" role="status">正在加载评论…</p>
    <button v-else-if="loadError || next" class="glass-button" type="button" @click="loadMore">{{ loadError ? '重试加载' : '加载更多评论' }}</button>
  </section>
</template>
