<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowRight, ChevronRight, ClipboardCheck, Layers, LayoutDashboard, Search, Trophy, UserPlus, UsersRound } from '@lucide/vue'
import { readManagedWorks, readMembers } from '../api'
import type { MemberAccount } from '../api'
import { statusLabels } from '../works'
import type { Competition, ManagedWork } from '../works'
import CompetitionManager from './CompetitionManager.vue'
import ManageMemberDialog from './ManageMemberDialog.vue'
import WorkModerationDialog from './WorkModerationDialog.vue'
import '../management.css'

type Section = 'overview' | 'works' | 'display' | 'competitions' | 'accounts'
type WorkFilter = 'pending' | 'rejected' | 'unlisted' | 'published'

const props = defineProps<{ section: Section; competitions: Competition[] }>()
const emit = defineEmits<{ workUpdated: []; competitionCreated: [competition: Competition] }>()
const sections = [
  { id: 'overview', title: '概览', href: '#manage', icon: LayoutDashboard },
  { id: 'works', title: '作品审核', href: '#manage/works', icon: ClipboardCheck },
  { id: 'display', title: '展示管理', href: '#manage/display', icon: Layers },
  { id: 'competitions', title: '比赛分类', href: '#manage/competitions', icon: Trophy },
  { id: 'accounts', title: '成员账号', href: '#manage/accounts', icon: UsersRound },
] as const
const reviewFilters = [
  { id: 'pending', title: '待审核' },
  { id: 'rejected', title: '已退回' },
] as const
const displayFilters = [
  { id: 'unlisted', title: '待上架' },
  { id: 'published', title: '已上架' },
] as const
const works = ref<ManagedWork[]>([])
const members = ref<MemberAccount[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const reviewFilter = ref<'pending' | 'rejected'>('pending')
const displayFilter = ref<'unlisted' | 'published'>('unlisted')
const reviewSearch = ref('')
const displaySearch = ref('')
const memberSearch = ref('')
const selectedWork = ref<{ id: string; section: Section }>()
const selectedMember = ref<MemberAccount>()
const memberOpen = ref(false)
let refreshNumber = 0
const currentWork = computed(() => selectedWork.value?.section === props.section
  ? works.value.find(work => work.id === selectedWork.value?.id)
  : undefined)
const title = computed(() => ({ overview: '管理后台', works: '作品审核', display: '展示管理', competitions: '比赛分类', accounts: '成员账号' })[props.section])
const displaying = computed(() => props.section === 'display')
const filters = computed(() => displaying.value ? displayFilters : reviewFilters)
const selectedFilter = computed(() => displaying.value ? displayFilter.value : reviewFilter.value)
const workSearch = computed({
  get: () => displaying.value ? displaySearch.value : reviewSearch.value,
  set: value => {
    if (displaying.value) displaySearch.value = value
    else reviewSearch.value = value
  },
})
const pending = computed(() => works.value.filter(work => work.status === 'pending'))
const published = computed(() => works.value.filter(work => work.is_visible))
const activeMembers = computed(() => members.value.filter(member => member.is_active).length)
const filteredWorks = computed(() => {
  const source = displaying.value
    ? works.value.filter(work => work.status === 'approved' && work.is_visible === (displayFilter.value === 'published'))
    : works.value.filter(work => work.status === reviewFilter.value)
  const search = workSearch.value.trim().toLocaleLowerCase()
  return source.filter(work => [work.title, work.owner_username, work.competition_name].some(value => value.toLocaleLowerCase().includes(search)))
})
const filteredMembers = computed(() => members.value.filter(member => member.username.toLocaleLowerCase().includes(memberSearch.value.trim().toLocaleLowerCase())))
const date = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeZone: 'Asia/Shanghai' })
const metrics = computed(() => [
  { title: '待审核作品', count: pending.value.length, icon: ClipboardCheck, target: '#manage/works', filter: 'pending' },
  { title: '已上架作品', count: published.value.length, icon: Layers, target: '#manage/display', filter: 'published' },
  { title: '有效成员账号', count: activeMembers.value, icon: UsersRound, target: '#manage/accounts' },
] as const)

async function refresh(background = false) {
  if (background && loading.value) return
  const number = ++refreshNumber
  if (!background) {
    loading.value = true
    error.value = ''
  }
  try {
    const result = await Promise.all([readManagedWorks(), readMembers()])
    if (number !== refreshNumber) return
    works.value = result[0]
    members.value = result[1]
    error.value = ''
  } catch (reason) {
    if (number === refreshNumber && !background) {
      error.value = reason instanceof Error ? reason.message : '无法加载管理数据。'
    }
  } finally {
    if (number === refreshNumber) loading.value = false
  }
}

function refreshOnFocus() {
  void refresh(true)
}

function openMember(member?: MemberAccount) {
  selectedMember.value = member
  memberOpen.value = true
}

function updateMember(member: MemberAccount) {
  refreshNumber += 1
  loading.value = false
  members.value = [...members.value.filter(item => item.id !== member.id), member].sort((a, b) => a.username.localeCompare(b.username, 'zh-CN'))
}

function updateWork(work: ManagedWork) {
  refreshNumber += 1
  loading.value = false
  const submitted = currentWork.value
  const appliedRevision = submitted?.revision_of === work.id ? submitted.id : undefined
  works.value = [work, ...works.value.filter(item => item.id !== work.id && item.id !== appliedRevision)]
  if (appliedRevision) {
    selectedWork.value = undefined
    notice.value = '修改已通过，作品内容已更新。'
  }
  emit('workUpdated')
}

function selectFilter(filter: WorkFilter) {
  if (filter === 'pending' || filter === 'rejected') reviewFilter.value = filter
  else displayFilter.value = filter
}

function openWork(id: string) {
  notice.value = ''
  selectedWork.value = { id, section: props.section }
}

function openDisplay() {
  if (selectedWork.value) selectedWork.value = { id: selectedWork.value.id, section: 'display' }
  displaySearch.value = ''
  displayFilter.value = 'unlisted'
  window.location.hash = '#manage/display'
}

onMounted(() => {
  void refresh()
  window.addEventListener('focus', refreshOnFocus)
})
onBeforeUnmount(() => {
  refreshNumber += 1
  window.removeEventListener('focus', refreshOnFocus)
})
</script>

<template>
  <section class="management" aria-labelledby="manage-heading">
    <nav class="manage-tabs" aria-label="管理导航">
      <a v-for="tab in sections" :key="tab.id" :href="tab.href" :aria-current="section === tab.id ? 'page' : undefined">
        <component :is="tab.icon" :size="17" aria-hidden="true" /> {{ tab.title }}
      </a>
    </nav>
    <header class="manage-heading">
      <h1 id="manage-heading">{{ title }}</h1>
      <button v-if="section === 'overview' || section === 'accounts'" class="primary-button manage-primary" type="button" @click="openMember()">
        <UserPlus :size="18" aria-hidden="true" /> 发放账号
      </button>
    </header>
    <p v-if="notice" class="site-feedback glass-panel" role="status">{{ notice }}</p>

    <CompetitionManager v-if="section === 'competitions'" :competitions="competitions" @created="emit('competitionCreated', $event)" />
    <div v-else-if="error" class="manage-empty glass-panel" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="glass-button" @click="refresh()">重试</button>
    </div>
    <p v-else-if="loading" class="manage-empty glass-panel" role="status">正在加载管理数据…</p>

    <template v-else-if="section === 'overview'">
      <div class="manage-metrics">
        <a v-for="(metric, index) in metrics" :key="metric.title" class="manage-metric glass-panel" :data-metric="index"
          :href="metric.target" @click="'filter' in metric && selectFilter(metric.filter)">
          <span class="manage-symbol" aria-hidden="true"><component :is="metric.icon" :size="21" /></span>
          <span class="manage-metric-number">{{ metric.count }}</span>
          <span class="manage-metric-label">{{ metric.title }}</span>
          <ArrowRight class="manage-metric-arrow" :size="19" aria-hidden="true" />
        </a>
      </div>
      <section class="manage-panel glass-panel" aria-labelledby="manage-queue-title">
        <div class="manage-panel-heading">
          <h2 id="manage-queue-title">最近待审核作品</h2>
          <a v-if="pending.length" class="glass-button" href="#manage/works" @click="selectFilter('pending')">查看队列 <ArrowRight :size="16" aria-hidden="true" /></a>
        </div>
        <ul v-if="pending.length" class="manage-rows">
          <li v-for="work in pending.slice(0, 5)" :key="work.id">
            <button class="manage-row" type="button" @click="openWork(work.id)">
              <span class="manage-row-title"><strong>{{ work.title }}</strong><small>{{ work.revision_of ? '修改稿 · ' : '' }}{{ work.owner_username }} · {{ work.assets.length }} 个附件</small></span>
              <time :datetime="work.updated_at">{{ date.format(new Date(work.updated_at)) }}</time>
              <ChevronRight :size="18" aria-hidden="true" />
            </button>
          </li>
        </ul>
        <p v-else class="manage-empty">目前没有待审核作品。</p>
      </section>
    </template>

    <section v-else-if="section === 'works' || displaying" class="manage-panel glass-panel" :aria-label="displaying ? '展示管理列表' : '作品审核列表'">
      <div class="manage-panel-heading">
        <div class="manage-filters" role="group" aria-label="作品状态">
          <button v-for="item in filters" :key="item.id" type="button" :aria-pressed="selectedFilter === item.id" @click="selectFilter(item.id)">{{ item.title }}</button>
        </div>
        <label class="manage-search"><Search :size="17" aria-hidden="true" /><input v-model="workSearch" :aria-label="displaying ? '搜索展示作品' : '搜索审核作品'" placeholder="搜索作品或投稿人"></label>
      </div>
      <ul v-if="filteredWorks.length" class="manage-rows">
        <li v-for="work in filteredWorks" :key="work.id">
          <button class="manage-row" type="button" @click="openWork(work.id)">
            <span class="manage-row-title"><strong>{{ work.title }}</strong><small>{{ work.revision_of ? '修改稿 · ' : '' }}{{ work.owner_username }} · {{ work.assets.length }} 个附件</small></span>
            <span class="manage-status" :data-status="work.status">{{ work.is_visible ? '已上架' : work.status === 'approved' ? '待上架' : statusLabels[work.status] }}</span>
            <ChevronRight :size="18" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <p v-else class="manage-empty">{{ workSearch.trim() ? '没有符合条件的作品。' : '这个列表暂时没有作品。' }}</p>
    </section>

    <section v-else class="manage-panel glass-panel" aria-label="成员账号列表">
      <div class="manage-panel-heading">
        <p class="manage-hint">{{ activeMembers }} 个有效账号 · {{ members.length - activeMembers }} 个已回收</p>
        <label class="manage-search"><Search :size="17" aria-hidden="true" /><input v-model="memberSearch" aria-label="搜索成员账号" placeholder="搜索用户名"></label>
      </div>
      <ul v-if="filteredMembers.length" class="manage-rows">
        <li v-for="member in filteredMembers" :key="member.id">
          <button class="manage-row" type="button" @click="openMember(member)">
            <span class="manage-row-title"><strong>{{ member.username }}</strong><small>{{ member.last_login ? '最近登录 ' + date.format(new Date(member.last_login)) : '尚未登录' }}</small></span>
            <span class="manage-status" :data-status="member.is_active ? 'approved' : 'draft'">{{ member.is_active ? '可登录' : '已回收' }}</span>
            <ChevronRight :size="18" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <p v-else class="manage-empty">{{ memberSearch.trim() ? '没有符合条件的账号。' : '还没有发放成员账号。' }}</p>
    </section>

    <WorkModerationDialog v-if="currentWork" :key="`${section}-${currentWork.id}`" :work="currentWork" :competitions="competitions" :mode="displaying ? 'display' : 'review'"
      @close="selectedWork = undefined" @updated="updateWork" @refresh="refresh()" @open-display="openDisplay" />
    <ManageMemberDialog v-if="memberOpen" :member="selectedMember" @close="memberOpen = false" @updated="updateMember" />
  </section>
</template>
