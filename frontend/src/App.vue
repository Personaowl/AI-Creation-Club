<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch, watchEffect } from 'vue'
import {
  Aperture, CalendarDays, ChevronDown, ChevronRight, Compass, FolderOpen, Heart,
  LayoutGrid, Moon, Paperclip, Plus, Search, ShieldCheck, Sun, Trophy, X,
} from '@lucide/vue'
import { readCompetitions, readSession, readWorks, signOut } from './api'
import type { Account } from './api'
import { brandName, platformName } from './branding'
import AccountMenu from './components/AccountMenu.vue'
import GlassFilter from './components/GlassFilter.vue'
import LoginPage from './components/LoginPage.vue'
import PasswordDialog from './components/PasswordDialog.vue'
import UploadDialog from './components/UploadDialog.vue'
import { statusLabels, workAttachments, workDetailPath } from './works'
import type { Competition, FilterValue, Work } from './works'
const dateFormat = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', timeZone: 'Asia/Shanghai' })
const ManagementWorkspace = defineAsyncComponent(() => import('./components/ManagementWorkspace.vue'))
const PdfReader = defineAsyncComponent(() => import('./components/PdfReader.vue'))
const WorkDetailPage = defineAsyncComponent(() => import('./components/WorkDetailPage.vue'))

type View = 'library' | 'mine' | 'favorites'

const account = ref<Account | null>(null)
const starting = ref(true)
const connectionError = ref('')
const loading = ref(false)
const feedback = ref('')
const records = ref<Work[]>([])
const mine = ref<Work[]>([])
const competitions = ref<Competition[]>([])
const favorites = ref<string[]>([])
const view = ref<View>('library')
const competitionFilter = ref<FilterValue>('all')
const yearFilter = ref<FilterValue>('all')
const search = ref('')
const sort = ref<'recent' | 'oldest' | 'title'>('recent')
const draft = ref<Work>()
const uploadOpen = ref(false)
const passwordOpen = ref(false)
const searchInput = ref<HTMLInputElement>()
const managementMain = ref<HTMLElement>()
const fragment = ref(window.location.hash)
const detailWorkId = computed(() => fragment.value.match(/^#work\/([0-9a-f-]{36})$/i)?.[1])
const detailRefresh = ref(0)
const detailBackLabel = computed(() => ({ library: '返回作品库', mine: '返回我的投稿', favorites: '返回我的收藏' })[view.value])
const pdfLocation = computed(() => {
  const match = fragment.value.match(/^#pdf\/([0-9a-f-]{36})\/([0-9a-f-]{36})(?:\/(\d+))?$/i)
  if (!match) return
  const page = Number(match[3] ?? 1)
  return { workId: match[1], assetId: match[2], initialPage: Number.isSafeInteger(page) && page > 0 ? page : 1 }
})
const managementSection = computed(() => {
  if (fragment.value === '#manage') return 'overview'
  if (fragment.value === '#manage/works') return 'works'
  if (fragment.value === '#manage/display') return 'display'
  if (fragment.value === '#manage/competitions') return 'competitions'
  if (fragment.value === '#manage/accounts') return 'accounts'
})
const inManagement = computed(() => Boolean(account.value?.is_admin && managementSection.value))
const darkTheme = ref(false)
let themeTransition: ViewTransition | undefined
try {
  darkTheme.value = (localStorage.getItem('club-theme')
    ?? localStorage.getItem('club-management-theme')
    ?? localStorage.getItem('theme')) === 'dark'
} catch {
  // The default theme does not require browser storage.
}
watchEffect(() => {
  if (account.value && darkTheme.value) document.documentElement.dataset.theme = 'dark'
  else delete document.documentElement.dataset.theme
})
const galleryTitle = computed(() => ({ library: '全部作品', mine: '我的投稿', favorites: '我的收藏' })[view.value])
const hasFilters = computed(() => Boolean(search.value.trim() || competitionFilter.value !== 'all' || yearFilter.value !== 'all'))
const competitionOptions = computed(() => [
  { value: 'all' as const, label: '全部比赛' },
  ...competitions.value.map(item => ({ value: item.id, label: item.name })),
  { value: 'unset' as const, label: '未分类' },
])
const yearOptions = computed(() => {
  const id = competitionFilter.value
  const groups = id === 'all' ? competitions.value : competitions.value.filter(item => item.id === id)
  const years = [...new Set(groups.flatMap(item => item.years))].sort((a, b) => b - a)
  return [
    { value: 'all' as const, label: '全部年份' },
    ...years.map(year => ({ value: year, label: year + ' 年' })),
    { value: 'unset' as const, label: '未标注年份' },
  ]
})
watch(yearOptions, options => {
  if (competitionFilter.value === 'unset' || !options.some(option => option.value === yearFilter.value)) yearFilter.value = 'all'
})
let refreshNumber = 0

function favoriteKey(id: number) {
  return 'entrystage-favorites-' + id
}

function loadFavorites(id: number) {
  try {
    const values: unknown = JSON.parse(localStorage.getItem(favoriteKey(id)) ?? '[]')
    return Array.isArray(values) ? values.filter((item): item is string => typeof item === 'string') : []
  } catch {
    return []
  }
}

const shownWorks = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase()
  const source = view.value === 'mine' ? mine.value : records.value
  return source.filter(work =>
    (view.value !== 'favorites' || favorites.value.includes(work.id)) &&
    (competitionFilter.value === 'all' || work.competition === (competitionFilter.value === 'unset' ? null : competitionFilter.value)) &&
    (yearFilter.value === 'all' || work.competition_year === (yearFilter.value === 'unset' ? null : yearFilter.value)) &&
    (!keyword || [work.title, work.description, work.competition_name, work.team_name, ...work.assets.map(asset => asset.original_name)]
      .some(value => value?.toLocaleLowerCase().includes(keyword))),
  ).sort((a, b) => {
    if (sort.value === 'title') return a.title.localeCompare(b.title, 'zh-CN')
    return sort.value === 'recent' ? b.updated_at.localeCompare(a.updated_at) : a.updated_at.localeCompare(b.updated_at)
  })
})

async function refresh() {
  const number = ++refreshNumber
  loading.value = true
  try {
    const [gallery, submissions, groups] = await Promise.all([readWorks('gallery'), readWorks('mine'), readCompetitions()])
    if (number !== refreshNumber) return
    records.value = gallery
    mine.value = submissions
    competitions.value = groups
    if (typeof competitionFilter.value === 'number' && !groups.some(group => group.id === competitionFilter.value)) {
      competitionFilter.value = 'all'
    }
  } catch (error) {
    if (number === refreshNumber) feedback.value = error instanceof Error ? error.message : '无法加载作品。'
  } finally {
    if (number === refreshNumber) loading.value = false
  }
}

function acceptAccount(user: Account) {
  if (account.value?.id !== user.id) {
    records.value = []
    mine.value = []
    competitions.value = []
    favorites.value = loadFavorites(user.id)
    view.value = 'library'
    clearFilters()
  }
  account.value = user
  if (!pdfLocation.value) void refresh()
}

function clearAccount() {
  refreshNumber += 1
  account.value = null
  records.value = []
  mine.value = []
  competitions.value = []
  favorites.value = []
  draft.value = undefined
  uploadOpen.value = false
  passwordOpen.value = false
  loading.value = false
  feedback.value = ''
}

async function initialize() {
  starting.value = true
  connectionError.value = ''
  try {
    const user = await readSession()
    if (user) acceptAccount(user)
    else clearAccount()
  } catch (error) {
    connectionError.value = error instanceof Error ? error.message : '无法连接后端。'
  } finally {
    starting.value = false
  }
}

async function onFocus() {
  if (!account.value) return
  try {
    const user = await readSession()
    if (!user) clearAccount()
    else if (user.id !== account.value?.id) acceptAccount(user)
    else {
      account.value = user
      if (!pdfLocation.value) {
        detailRefresh.value += 1
        void refresh()
      }
    }
  } catch {
    // Keep the current view during a temporary network interruption.
  }
}

async function onHashChange() {
  const wasReading = Boolean(pdfLocation.value)
  const wasInDetail = Boolean(detailWorkId.value)
  fragment.value = window.location.hash
  if (wasReading && !pdfLocation.value && account.value) void refresh()
  await nextTick()
  if (inManagement.value || detailWorkId.value || pdfLocation.value) window.scrollTo({ top: 0, behavior: 'instant' })
  if (wasInDetail && fragment.value === '#gallery') {
    const list = document.getElementById('gallery')
    list?.scrollIntoView({ behavior: 'instant' })
    list?.focus({ preventScroll: true })
  }
}

function applyThemeToggle() {
  darkTheme.value = !darkTheme.value
  try {
    localStorage.setItem('club-theme', darkTheme.value ? 'dark' : 'light')
  } catch {
    // The theme still works for the current visit.
  }
}

function toggleTheme() {
  if (themeTransition) {
    themeTransition.skipTransition()
    void themeTransition.updateCallbackDone.then(applyThemeToggle, applyThemeToggle)
    return
  }
  if (!document.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    applyThemeToggle()
    return
  }
  themeTransition = document.startViewTransition(async () => {
    applyThemeToggle()
    await nextTick()
  })
  void themeTransition.finished.then(clearThemeTransition, clearThemeTransition)
}

function clearThemeTransition() {
  themeTransition = undefined
}

onMounted(() => {
  void initialize()
  window.addEventListener('focus', onFocus)
  window.addEventListener('hashchange', onHashChange)
})
onBeforeUnmount(() => {
  window.removeEventListener('focus', onFocus)
  window.removeEventListener('hashchange', onHashChange)
  delete document.documentElement.dataset.theme
})

function showView(nextView: View) {
  if (inManagement.value || detailWorkId.value) {
    window.history.pushState(null, '', window.location.pathname + window.location.search)
    fragment.value = ''
  }
  view.value = nextView
  clearFilters()
  window.scrollTo({ top: 0, behavior: 'instant' })
}

function returnToGallery() {
  window.location.hash = 'gallery'
}

function focusWorkDetails() {
  document.getElementById('work-detail')?.focus()
}

function clearFilters() {
  competitionFilter.value = 'all'
  yearFilter.value = 'all'
  search.value = ''
}

function onCompetitionChanged(id: number, updated?: Competition) {
  const groups = competitions.value.filter(group => group.id !== id)
  if (updated) groups.push(updated)
  else if (competitionFilter.value === id) competitionFilter.value = 'all'
  competitions.value = groups.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  void refresh()
}

async function logout() {
  try {
    await signOut()
    clearAccount()
  } catch (error) {
    feedback.value = error instanceof Error ? error.message : '无法退出登录。'
  }
}

function toggleFavorite(id: string) {
  if (!account.value) return
  favorites.value = favorites.value.includes(id) ? favorites.value.filter(item => item !== id) : [...favorites.value, id]
  try {
    localStorage.setItem(favoriteKey(account.value.id), JSON.stringify(favorites.value))
  } catch {
    feedback.value = '浏览器无法保存收藏。'
  }
}

function openUpload(work?: Work) {
  draft.value = work
  uploadOpen.value = true
}

function closeUpload() {
  uploadOpen.value = false
  draft.value = undefined
  detailRefresh.value += 1
  void refresh()
}

function updateMyWork(work: Work) {
  if (work.revision_of) {
    mine.value = mine.value.map(item => item.id === work.revision_of
      ? { ...item, revision: { id: work.id, status: work.status } }
      : item)
  } else {
    mine.value = [work, ...mine.value.filter(item => item.id !== work.id)]
  }
}

function onSaved(work: Work) {
  uploadOpen.value = false
  draft.value = undefined
  updateMyWork(work)
  showView('mine')
  sort.value = 'recent'
  const subject = work.revision_of ? '修改稿' : '作品'
  feedback.value = subject + (work.status === 'pending' ? '已提交审核。' : '已保存为草稿。')
  void refresh()
}

function onWithdrawn(work: Work) {
  updateMyWork(work)
  void refresh()
}
</script>

<template>
  <main v-if="starting" class="login-layout">
    <p class="glass-button" role="status">正在连接 {{ brandName }}…</p>
  </main>
  <LoginPage v-else-if="!account" :connection-error="connectionError" @signed-in="acceptAccount" @retry="initialize" />
  <PdfReader v-else-if="pdfLocation" :key="account.id + ':' + fragment" v-bind="pdfLocation" />

  <template v-else>
    <a v-if="inManagement" href="#manage-area" class="skip-link" @click.prevent="managementMain?.focus()">跳到管理内容</a>
    <a v-else-if="detailWorkId" href="#work-detail" class="skip-link" @click.prevent="focusWorkDetails">跳到作品详情</a>
    <a v-else href="#gallery" class="skip-link">跳到作品列表</a>
    <div class="site-shell">
      <header class="site-header glass-panel glass-refractive" :class="{ 'site-header-admin': account.is_admin }">
        <a class="brand" href="#" :aria-label="platformName + '首页'" @click.prevent="showView('library')">
          <span class="brand-mark glass-panel"><Aperture :size="21" :stroke-width="1.7" /></span>
          <span class="brand-name">{{ brandName }}</span>
        </a>
        <nav class="main-nav" aria-label="主要导航">
          <button class="nav-item" :class="{ active: !inManagement && view === 'library' }" type="button" :aria-current="!inManagement && view === 'library' ? 'page' : undefined" @click="showView('library')">
            <Compass :size="17" /> <span>作品库</span>
          </button>
          <button class="nav-item" :class="{ active: !inManagement && view === 'favorites' }" type="button" :aria-current="!inManagement && view === 'favorites' ? 'page' : undefined" @click="showView('favorites')">
            <Heart :size="17" /> <span>我的收藏</span>
          </button>
          <button class="nav-item" :class="{ active: !inManagement && view === 'mine' }" type="button" :aria-current="!inManagement && view === 'mine' ? 'page' : undefined" @click="showView('mine')">
            <FolderOpen :size="17" /> <span>我的投稿</span>
          </button>
          <a v-if="account.is_admin" href="#manage" class="nav-item" :class="{ active: inManagement }" :aria-current="inManagement ? 'page' : undefined">
            <ShieldCheck :size="17" aria-hidden="true" /> <span>管理后台</span>
          </a>
        </nav>
        <div class="header-end">
          <button v-if="!inManagement" class="primary-button header-action" type="button" aria-label="上传作品" @click="openUpload()">
            <Plus :size="19" aria-hidden="true" />
            <span class="header-action-label">上传作品</span>
            <span class="header-action-compact">上传</span>
          </button>
          <button class="glass-button icon-button theme-toggle" type="button"
            :aria-label="darkTheme ? '切换浅色模式' : '切换深色模式'" @click="toggleTheme">
            <Sun v-if="darkTheme" :size="19" aria-hidden="true" />
            <Moon v-else :size="19" aria-hidden="true" />
          </button>
          <AccountMenu :account="account" @change-password="passwordOpen = true" @logout="logout" />
        </div>
      </header>

      <main v-if="inManagement && managementSection" id="manage-area" ref="managementMain" tabindex="-1">
        <p v-if="feedback" class="site-feedback glass-panel" role="status">{{ feedback }}</p>
        <ManagementWorkspace :section="managementSection" :competitions="competitions"
          @work-updated="refresh" @competition-changed="onCompetitionChanged" />
      </main>
      <WorkDetailPage v-else-if="detailWorkId" :key="account.id + ':' + detailWorkId" :work-id="detailWorkId"
        :favorite="favorites.includes(detailWorkId)" :back-label="detailBackLabel" :refresh-key="detailRefresh"
        @back="returnToGallery" @favorite="toggleFavorite(detailWorkId)" @edit="openUpload" @withdrawn="onWithdrawn" />
      <main v-else>
        <p v-if="feedback" class="site-feedback glass-panel" role="status">{{ feedback }}</p>
        <section v-if="view === 'library'" class="hero" aria-labelledby="hero-title">
          <div class="hero-copy">
            <h1 id="hero-title" :aria-label="platformName">
              <span class="hero-brand-name">{{ brandName }}</span>
              <span class="hero-platform-type">作品平台</span>
            </h1>
            <a class="glass-button hero-action" href="#gallery"><LayoutGrid :size="16" aria-hidden="true" /> 浏览作品</a>
          </div>
          <div class="hero-art" aria-hidden="true">
            <div class="hero-glass-back"></div>
            <div class="hero-glass-front">
              <Aperture :size="76" :stroke-width="1.1" focusable="false" />
            </div>
            <div class="hero-glass-drop"></div>
          </div>
        </section>

        <section id="gallery" class="gallery" aria-labelledby="gallery-heading" tabindex="-1">
          <div class="gallery-heading">
            <div class="gallery-title">
              <h2 id="gallery-heading">{{ galleryTitle }}</h2>
              <span class="work-count" aria-live="polite">{{ shownWorks.length }} 件</span>
            </div>
            <div class="search-field glass-panel" role="search">
              <Search :size="18" aria-hidden="true" />
              <input ref="searchInput" v-model="search" aria-label="搜索作品" placeholder="搜索作品…">
              <button v-if="search" class="clear-search" aria-label="清除搜索" type="button" @click="search = ''; searchInput?.focus()">
                <X :size="16" />
              </button>
            </div>
          </div>
          <div class="gallery-toolbar">
            <div class="gallery-classification" role="group" aria-label="比赛筛选">
              <GlassFilter v-model="competitionFilter" class="competition-filter" label="按比赛分类筛选" :options="competitionOptions" searchable>
                <template #icon><Trophy :size="17" aria-hidden="true" /></template>
              </GlassFilter>
              <GlassFilter v-model="yearFilter" label="按年份筛选" :options="yearOptions" :disabled="competitionFilter === 'unset'">
                <template #icon><CalendarDays :size="17" aria-hidden="true" /></template>
              </GlassFilter>
            </div>
            <div class="gallery-selects">
              <div class="sort-field glass-panel">
                <select v-model="sort" aria-label="作品排序">
                  <option value="recent">最近更新</option>
                  <option value="oldest">最早更新</option>
                  <option value="title">按名称</option>
                </select>
                <ChevronDown :size="16" aria-hidden="true" />
              </div>
            </div>
          </div>

          <div v-if="shownWorks.length" class="work-grid">
            <article v-for="work in shownWorks" :key="work.id" class="work-card glass-panel" :class="{ 'work-card-with-favorite': work.is_visible }">
              <a class="work-open" :href="workDetailPath(work.id)" :aria-label="'查看作品 ' + work.title">
                <div class="work-copy">
                  <div class="work-card-heading">
                    <h3>{{ work.title }}</h3>
                    <div v-if="work.competition_name" class="work-competition">
                      <Trophy :size="15" aria-hidden="true" />
                      <span>{{ work.competition_name }}</span>
                      <span v-if="work.competition_year" class="work-edition">{{ work.competition_year }} 年</span>
                    </div>
                  </div>
                  <p v-if="work.description">{{ work.description }}</p>
                </div>
                <div class="work-meta">
                  <span class="work-meta-files">
                    <Paperclip :size="15" aria-hidden="true" /> {{ workAttachments(work).length }} 个附件
                  </span>
                  <span class="work-meta-end">
                    <span v-if="view === 'mine'">{{ work.revision ? '修改稿 · ' + statusLabels[work.revision.status] : work.is_visible ? '已上架' : statusLabels[work.status] }}</span>
                    <time v-else :datetime="work.updated_at">{{ dateFormat.format(new Date(work.updated_at)) }}</time>
                    <ChevronRight :size="17" aria-hidden="true" />
                  </span>
                </div>
              </a>
              <button v-if="work.is_visible" class="card-favorite" type="button" :aria-label="(favorites.includes(work.id) ? '取消收藏' : '收藏') + work.title"
                :aria-pressed="favorites.includes(work.id)" @click="toggleFavorite(work.id)">
                <Heart :size="19" :class="{ 'heart-filled': favorites.includes(work.id) }" aria-hidden="true" />
              </button>
            </article>
          </div>
          <div v-else class="empty-state glass-panel" :aria-busy="loading">
            <component :is="view === 'favorites' ? Heart : Search" :size="28" :stroke-width="1.5" />
            <h3>{{ loading ? '正在加载作品…' : hasFilters ? '没有符合条件的作品' : view === 'favorites' ? '还没有收藏作品' : view === 'mine' ? '还没有投稿' : '暂无已上架作品' }}</h3>
            <button v-if="hasFilters" class="glass-button" type="button" @click="clearFilters">清除筛选</button>
          </div>
        </section>
      </main>
    </div>

    <UploadDialog v-if="uploadOpen" :work="draft" :competitions="competitions" @close="closeUpload" @saved="onSaved" />
    <PasswordDialog v-if="passwordOpen" @close="passwordOpen = false" @saved="passwordOpen = false; feedback = '密码已更新。'" />
  </template>
</template>
