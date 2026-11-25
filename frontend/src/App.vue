<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watchEffect } from 'vue'
import {
  Aperture, ChevronDown, Clapperboard, Code2, Compass, FileText, FolderOpen, Heart,
  LayoutGrid, Moon, Music2, Plus, Presentation, Search, ShieldCheck, Sun, X,
} from '@lucide/vue'
import { readCompetitions, readSession, readWork, readWorks, RequestError, signOut } from './api'
import type { Account } from './api'
import { brandName, platformName } from './branding'
import AccountMenu from './components/AccountMenu.vue'
import LoginPage from './components/LoginPage.vue'
import PasswordDialog from './components/PasswordDialog.vue'
import PreviewDialog from './components/PreviewDialog.vue'
import UploadDialog from './components/UploadDialog.vue'
import WorkCover from './components/WorkCover.vue'
import { kindLabels, statusLabels } from './works'
import type { Competition, Cover, Work, WorkKind } from './works'

const categories = [
  { id: 'all', label: '全部', icon: LayoutGrid },
  { id: 'slides', label: kindLabels.slides, icon: Presentation },
  { id: 'pdf', label: kindLabels.pdf, icon: FileText },
  { id: 'video', label: kindLabels.video, icon: Clapperboard },
  { id: 'audio', label: kindLabels.audio, icon: Music2 },
  { id: 'source', label: kindLabels.source, icon: Code2 },
] as const
const icons = { slides: Presentation, pdf: FileText, video: Clapperboard, audio: Music2, source: Code2 }
const covers: Partial<Record<WorkKind, Cover>> = { slides: 'form', video: 'lake', source: 'code' }
const dateFormat = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', timeZone: 'Asia/Shanghai' })
const ManagementWorkspace = defineAsyncComponent(() => import('./components/ManagementWorkspace.vue'))

type View = 'library' | 'mine' | 'favorites'
type Category = 'all' | WorkKind

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
const category = ref<Category>('all')
const competitionFilter = ref<'all' | 'unclassified' | number>('all')
const search = ref('')
const sort = ref<'recent' | 'oldest' | 'title'>('recent')
const preview = ref<Work>()
const draft = ref<Work>()
const uploadOpen = ref(false)
const passwordOpen = ref(false)
const searchInput = ref<HTMLInputElement>()
const managementMain = ref<HTMLElement>()
const fragment = ref(window.location.hash)
const managementSection = computed(() => {
  if (fragment.value === '#manage') return 'overview'
  if (fragment.value === '#manage/works') return 'works'
  if (fragment.value === '#manage/display') return 'display'
  if (fragment.value === '#manage/competitions') return 'competitions'
  if (fragment.value === '#manage/accounts') return 'accounts'
})
const inManagement = computed(() => Boolean(account.value?.is_admin && managementSection.value))
const darkManagement = ref(false)
try {
  darkManagement.value = (localStorage.getItem('club-management-theme') ?? localStorage.getItem('theme')) === 'dark'
} catch {
  // The default theme does not require browser storage.
}
watchEffect(() => {
  if (inManagement.value && darkManagement.value) document.documentElement.dataset.managementTheme = 'dark'
  else delete document.documentElement.dataset.managementTheme
})
const galleryTitle = computed(() => ({ library: '全部作品', mine: '我的投稿', favorites: '我的收藏' })[view.value])
const hasFilters = computed(() => Boolean(search.value.trim() || category.value !== 'all' || competitionFilter.value !== 'all'))
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
    (category.value === 'all' || work.assets.some(asset => asset.kind === category.value)) &&
    (competitionFilter.value === 'all' || work.competition === (competitionFilter.value === 'unclassified' ? null : competitionFilter.value)) &&
    (!keyword || [work.title, work.description, work.competition_name, work.team_name, ...work.assets.map(asset => asset.original_name)]
      .some(value => value?.toLocaleLowerCase().includes(keyword))),
  ).sort((a, b) => {
    if (sort.value === 'title') return a.title.localeCompare(b.title, 'zh-CN')
    return sort.value === 'recent' ? b.updated_at.localeCompare(a.updated_at) : a.updated_at.localeCompare(b.updated_at)
  })
})

function firstKind(work: Work): WorkKind {
  return work.assets[0]?.kind ?? 'slides'
}

async function refresh() {
  const number = ++refreshNumber
  loading.value = true
  try {
    const [gallery, submissions, groups] = await Promise.all([readWorks('gallery'), readWorks('mine'), readCompetitions()])
    if (number !== refreshNumber) return
    records.value = gallery
    mine.value = submissions
    competitions.value = groups
    const current = preview.value
    if (current?.revision_of) {
      const parent = submissions.find(work => work.id === current.revision_of)
      if (parent?.revision?.id !== current.id) {
        preview.value = parent
      } else {
        let updated
        try {
          updated = await readWork(current.id)
        } catch (error) {
          if (!(error instanceof RequestError) || error.status !== 404) throw error
          updated = await readWork(parent.id)
        }
        if (number === refreshNumber && preview.value?.id === current.id) preview.value = updated
      }
    } else if (current) {
      preview.value = [...gallery, ...submissions].find(work => work.id === current.id)
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
    showView('library')
  }
  account.value = user
  void refresh()
}

function clearAccount() {
  refreshNumber += 1
  account.value = null
  records.value = []
  mine.value = []
  competitions.value = []
  favorites.value = []
  preview.value = undefined
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
      void refresh()
    }
  } catch {
    // Keep the current view during a temporary network interruption.
  }
}

function onHashChange() {
  fragment.value = window.location.hash
  if (inManagement.value) window.scrollTo({ top: 0, behavior: 'instant' })
}

function toggleManagementTheme() {
  darkManagement.value = !darkManagement.value
  try {
    localStorage.setItem('club-management-theme', darkManagement.value ? 'dark' : 'light')
  } catch {
    // The theme still works for the current visit.
  }
}

onMounted(() => {
  void initialize()
  window.addEventListener('focus', onFocus)
  window.addEventListener('hashchange', onHashChange)
})
onBeforeUnmount(() => {
  window.removeEventListener('focus', onFocus)
  window.removeEventListener('hashchange', onHashChange)
  delete document.documentElement.dataset.managementTheme
})

function showView(nextView: View) {
  if (inManagement.value) {
    window.history.pushState(null, '', window.location.pathname + window.location.search)
    fragment.value = ''
  }
  view.value = nextView
  clearFilters()
  window.scrollTo({ top: 0, behavior: 'instant' })
}

function clearFilters() {
  category.value = 'all'
  competitionFilter.value = 'all'
  search.value = ''
}

function onCompetitionCreated(item: Competition) {
  competitions.value = [...competitions.value.filter(group => group.id !== item.id), item]
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
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
  preview.value = undefined
  draft.value = work
  uploadOpen.value = true
}

function closeUpload() {
  uploadOpen.value = false
  draft.value = undefined
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
  if (preview.value?.id === work.id) preview.value = work
  feedback.value = work.revision_of ? '修改稿已撤回。' : '投稿已撤回，作品已回到草稿。'
  void refresh()
}
</script>

<template>
  <main v-if="starting" class="login-layout">
    <p class="glass-button" role="status">正在连接 {{ brandName }}…</p>
  </main>
  <LoginPage v-else-if="!account" :connection-error="connectionError" @signed-in="acceptAccount" @retry="initialize" />

  <template v-else>
    <a v-if="inManagement" href="#manage-area" class="skip-link" @click.prevent="managementMain?.focus()">跳到管理内容</a>
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
          <button v-if="inManagement" class="glass-button icon-button manage-theme-toggle" type="button"
            :aria-label="darkManagement ? '切换浅色模式' : '切换深色模式'" @click="toggleManagementTheme">
            <Sun v-if="darkManagement" :size="19" aria-hidden="true" />
            <Moon v-else :size="19" aria-hidden="true" />
          </button>
          <button v-else class="primary-button header-action" type="button" aria-label="上传作品" @click="openUpload()">
            <Plus :size="19" aria-hidden="true" />
            <span class="header-action-label">上传作品</span>
            <span class="header-action-compact">上传</span>
          </button>
          <AccountMenu :account="account" @change-password="passwordOpen = true" @logout="logout" />
        </div>
      </header>

      <main v-if="inManagement && managementSection" id="manage-area" ref="managementMain" tabindex="-1">
        <p v-if="feedback" class="site-feedback glass-panel" role="status">{{ feedback }}</p>
        <ManagementWorkspace :section="managementSection" :competitions="competitions"
          @work-updated="refresh" @competition-created="onCompetitionCreated" />
      </main>
      <main v-else>
        <p v-if="feedback" class="site-feedback glass-panel" role="status">{{ feedback }}</p>
        <section v-if="view === 'library'" class="hero" aria-labelledby="hero-title">
          <div class="hero-copy">
            <h1 id="hero-title" :aria-label="platformName">
              <span class="hero-brand-name">{{ brandName }}</span>
              <span class="hero-platform-type">作品平台</span>
            </h1>
            <p>浏览竞赛演示文稿、文档、音视频与源码项目。</p>
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
            <div class="filters glass-panel" role="group" aria-label="按作品类型筛选">
              <button v-for="item in categories" :key="item.id" class="filter-button" :class="{ active: category === item.id }"
                :aria-pressed="category === item.id" type="button" @click="category = item.id">
                <component :is="item.icon" :size="16" :stroke-width="1.9" /> {{ item.label }}
              </button>
            </div>
            <div class="gallery-selects">
              <div class="sort-field glass-panel">
                <select v-model="competitionFilter" aria-label="按比赛分类筛选">
                  <option value="all">全部比赛</option>
                  <option v-for="item in competitions" :key="item.id" :value="item.id">{{ item.name }}</option>
                  <option value="unclassified">未分类</option>
                </select>
                <ChevronDown :size="16" aria-hidden="true" />
              </div>
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
            <article v-for="work in shownWorks" :key="work.id" class="work-card glass-panel">
              <button class="work-open" type="button" :aria-label="'预览 ' + work.title" @click="preview = work">
                <div class="work-cover">
                  <WorkCover :cover="covers[firstKind(work)]" :kind="firstKind(work)" />
                  <span class="media-chip">
                    <component :is="icons[firstKind(work)]" :size="15" /> {{ work.assets.length > 1 ? '多种附件' : work.assets.length ? kindLabels[firstKind(work)] : '待补充附件' }}
                  </span>
                </div>
                <div class="work-copy">
                  <h3>{{ work.title }}</h3>
                  <span v-if="work.competition_name" class="work-competition">{{ work.competition_name }}</span>
                  <p>{{ work.description || '暂无简介' }}</p>
                  <div class="work-meta">
                    <span>{{ work.assets.length }} 个附件</span>
                    <span v-if="view === 'mine'">{{ work.revision ? '修改稿 · ' + statusLabels[work.revision.status] : work.is_visible ? '已上架' : statusLabels[work.status] }}</span>
                    <time v-else :datetime="work.updated_at">{{ dateFormat.format(new Date(work.updated_at)) }}</time>
                  </div>
                </div>
              </button>
              <button v-if="work.is_visible" class="card-favorite" type="button" :aria-label="(favorites.includes(work.id) ? '取消收藏' : '收藏') + work.title"
                :aria-pressed="favorites.includes(work.id)" @click="toggleFavorite(work.id)">
                <Heart :size="19" :class="{ 'heart-filled': favorites.includes(work.id) }" />
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
    <PreviewDialog
      v-if="preview" :key="preview.id" :work="preview" :favorite="favorites.includes(preview.id)"
      @close="preview = undefined" @toggle-favorite="toggleFavorite(preview.id)" @edit="openUpload"
      @view-revision="preview = $event" @withdrawn="onWithdrawn" @refresh="refresh"
    />
  </template>
</template>
