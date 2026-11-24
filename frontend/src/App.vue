<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Aperture, ChevronDown, Clapperboard, Code2, Compass, Heart, LayoutGrid, Plus,
  Presentation, Search, Sparkle, UserRound, X,
} from '@lucide/vue'
import { readSession, readWorks, signOut } from './api'
import type { Account } from './api'
import { brandName, platformName } from './branding'
import LoginPage from './components/LoginPage.vue'
import PasswordDialog from './components/PasswordDialog.vue'
import PreviewDialog from './components/PreviewDialog.vue'
import UploadDialog from './components/UploadDialog.vue'
import WorkCover from './components/WorkCover.vue'
import { kindLabels, statusLabels } from './works'
import type { Cover, Work, WorkKind } from './works'

const categories = [
  { id: 'all', label: '全部', icon: LayoutGrid },
  { id: 'slides', label: '演示文稿', icon: Presentation },
  { id: 'video', label: '视频', icon: Clapperboard },
  { id: 'source', label: '源码', icon: Code2 },
] as const
const icons = { slides: Presentation, video: Clapperboard, source: Code2 }
const covers: Record<WorkKind, Cover> = { slides: 'form', video: 'lake', source: 'code' }
const dateFormat = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', timeZone: 'Asia/Shanghai' })

type View = 'library' | 'mine' | 'favorites'
type Category = 'all' | WorkKind

const account = ref<Account | null>(null)
const starting = ref(true)
const connectionError = ref('')
const loading = ref(false)
const feedback = ref('')
const records = ref<Work[]>([])
const mine = ref<Work[]>([])
const favorites = ref<string[]>([])
const view = ref<View>('library')
const category = ref<Category>('all')
const search = ref('')
const sort = ref<'recent' | 'oldest' | 'title'>('recent')
const preview = ref<Work>()
const draft = ref<Work>()
const uploadOpen = ref(false)
const passwordOpen = ref(false)
const searchInput = ref<HTMLInputElement>()
const menu = ref<HTMLDetailsElement>()
const featured = computed(() => records.value[0])
const galleryTitle = computed(() => ({ library: '全部作品', mine: '我的投稿', favorites: '我的收藏' })[view.value])
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
    (!keyword || [work.title, work.description, ...work.assets.map(asset => asset.original_name)].some(value => value.toLocaleLowerCase().includes(keyword))),
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
    const [gallery, submissions] = await Promise.all([readWorks('gallery'), readWorks('mine')])
    if (number !== refreshNumber) return
    records.value = gallery
    mine.value = submissions
    if (preview.value) {
      preview.value = [...gallery, ...submissions].find(work => work.id === preview.value?.id)
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
    else void refresh()
  } catch {
    // Keep the current view during a temporary network interruption.
  }
}

onMounted(() => {
  void initialize()
  window.addEventListener('focus', onFocus)
})
onBeforeUnmount(() => window.removeEventListener('focus', onFocus))

function closeMenu() {
  if (menu.value) menu.value.open = false
}

function showView(nextView: View) {
  view.value = nextView
  category.value = 'all'
  search.value = ''
  closeMenu()
  window.scrollTo({ top: 0, behavior: 'instant' })
}

async function logout() {
  closeMenu()
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

function onSaved(work: Work) {
  uploadOpen.value = false
  draft.value = undefined
  mine.value = [work, ...mine.value.filter(item => item.id !== work.id)]
  showView('mine')
  sort.value = 'recent'
  feedback.value = work.status === 'pending' ? '作品已提交审核。' : '作品已保存为草稿。'
  void refresh()
}
</script>

<template>
  <main v-if="starting" class="login-layout">
    <p class="glass-button" role="status">正在连接 {{ brandName }}…</p>
  </main>
  <LoginPage v-else-if="!account" :connection-error="connectionError" @signed-in="acceptAccount" @retry="initialize" />

  <template v-else>
    <a href="#gallery" class="skip-link">跳到作品列表</a>
    <div class="site-shell">
      <header class="site-header glass-panel glass-refractive">
        <a class="brand" href="#" :aria-label="platformName + '首页'" @click.prevent="showView('library')">
          <span class="brand-mark glass-panel"><Aperture :size="21" :stroke-width="1.7" /></span>
          <span class="brand-name">{{ brandName }}</span>
        </a>
        <nav class="main-nav" aria-label="主要导航">
          <button class="nav-item" :class="{ active: view === 'library' }" type="button" :aria-current="view === 'library' ? 'page' : undefined" @click="showView('library')">
            <Compass :size="17" /> <span>作品库</span>
          </button>
          <button class="nav-item" :class="{ active: view === 'favorites' }" type="button" :aria-current="view === 'favorites' ? 'page' : undefined" @click="showView('favorites')">
            <Heart :size="17" /> <span>我的收藏</span>
          </button>
        </nav>
        <div class="header-end">
          <button class="primary-button header-action" type="button" aria-label="上传作品" @click="openUpload()">
            <Plus :size="19" /> <span>上传作品</span>
          </button>
          <details ref="menu" class="account-menu">
            <summary class="glass-button icon-button" aria-label="账号菜单"><UserRound :size="19" /></summary>
            <div class="account-actions glass-panel">
              <span class="account-name">{{ account.username }}</span>
              <button type="button" @click="showView('mine')">我的投稿</button>
              <a v-if="account.is_admin" href="/admin/">管理后台</a>
              <button type="button" @click="closeMenu(); passwordOpen = true">修改密码</button>
              <button type="button" @click="logout">退出登录</button>
            </div>
          </details>
        </div>
      </header>

      <main>
        <p v-if="feedback" class="site-feedback glass-panel" role="status">{{ feedback }}</p>
        <section v-if="view === 'library'" class="hero" aria-labelledby="hero-title">
          <div class="hero-copy">
            <h1 id="hero-title" :aria-label="platformName">
              <span class="hero-brand-name">{{ brandName }}</span>
              <span class="hero-platform-type">作品平台</span>
            </h1>
            <p>浏览竞赛演示文稿、视频与源码项目。</p>
            <a class="glass-button hero-action" href="#gallery"><LayoutGrid :size="16" aria-hidden="true" /> 浏览作品</a>
          </div>
          <div class="hero-art">
            <button v-if="featured" class="hero-feature glass-panel glass-refractive" type="button" @click="preview = featured">
              <Sparkle :size="53" :stroke-width="1.45" aria-hidden="true" />
              <strong>{{ featured.title }}</strong>
              <span>最新上架</span>
            </button>
            <div v-else class="hero-feature glass-panel glass-refractive">
              <Sparkle :size="53" :stroke-width="1.45" aria-hidden="true" />
              <span>{{ loading ? '正在加载作品' : '待作品上架' }}</span>
            </div>
            <button v-if="featured" type="button" class="floating-favorite glass-panel"
              :aria-label="(favorites.includes(featured.id) ? '取消收藏' : '收藏') + featured.title"
              :aria-pressed="favorites.includes(featured.id)" @click="toggleFavorite(featured.id)">
              <Heart :size="24" :stroke-width="1.65" :class="{ 'heart-filled': favorites.includes(featured.id) }" />
            </button>
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
            <div class="sort-field glass-panel">
              <select v-model="sort" aria-label="作品排序">
                <option value="recent">最近更新</option>
                <option value="oldest">最早更新</option>
                <option value="title">按名称</option>
              </select>
              <ChevronDown :size="16" aria-hidden="true" />
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
                  <p>{{ work.description || '暂无简介' }}</p>
                  <div class="work-meta">
                    <span>{{ work.assets.length }} 个附件</span>
                    <span v-if="view === 'mine'">{{ statusLabels[work.status] }}</span>
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
            <h3>{{ loading ? '正在加载作品…' : search || category !== 'all' ? '没有符合条件的作品' : view === 'favorites' ? '还没有收藏作品' : view === 'mine' ? '还没有投稿' : '暂无已上架作品' }}</h3>
            <button v-if="search || category !== 'all'" class="glass-button" type="button" @click="category = 'all'; search = ''">清除筛选</button>
          </div>
        </section>
      </main>
    </div>

    <UploadDialog v-if="uploadOpen" :work="draft" @close="closeUpload" @saved="onSaved" />
    <PasswordDialog v-if="passwordOpen" @close="passwordOpen = false" @saved="passwordOpen = false; feedback = '密码已更新。'" />
    <PreviewDialog
      v-if="preview" :key="preview.id" :work="preview" :favorite="favorites.includes(preview.id)"
      @close="preview = undefined" @toggle-favorite="toggleFavorite(preview.id)" @edit="openUpload(preview)"
    />
  </template>
</template>
