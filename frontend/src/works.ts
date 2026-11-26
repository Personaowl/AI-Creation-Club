export type WorkKind = 'slides' | 'pdf' | 'video' | 'audio' | 'source'
export type Cover = 'form' | 'lake' | 'code' | 'architecture'
export type WorkStatus = 'draft' | 'pending' | 'approved' | 'rejected'

export interface Asset {
  id: string
  original_name: string
  extension: string
  kind: WorkKind | 'photo'
  size: number
}

export interface WorkDetails {
  title: string
  description: string
  competition: number | null
  competition_year: number | null
  team_name: string
  team_members: string
  team_intro: string
  award_info: string
  ip_details: string
}

export interface Work extends WorkDetails {
  id: string
  revision_of: string | null
  revision: { id: string; status: WorkStatus } | null
  competition_name: string
  status: WorkStatus
  is_visible: boolean
  assets: Asset[]
  created_at: string
  updated_at: string
  is_mine: boolean
  can_edit: boolean
  can_revise: boolean
  can_download: boolean
  review_note: string
}

export interface ManagedWork extends Work {
  owner_username: string
  allow_download: boolean
}

export interface Competition {
  id: number
  name: string
  years: number[]
}

export type FilterValue = number | 'all' | 'unset'

export interface WorkComment {
  id: number
  author: string
  body: string
  created_at: string
  can_delete: boolean
}

export interface CommentPage {
  items: WorkComment[]
  next_before: number | null
}

export const kindLabels: Record<Asset['kind'], string> = { slides: '演示文稿', pdf: 'PDF', video: '视频', audio: '音频', source: '源码', photo: '团队照片' }
export const statusLabels: Record<WorkStatus, string> = { draft: '草稿', pending: '待审核', approved: '已通过', rejected: '已退回' }
export const fileKinds: Record<string, WorkKind> = {
  ppt: 'slides', pptx: 'slides', pdf: 'pdf', mp4: 'video', webm: 'video', mp3: 'audio', zip: 'source',
}
export const fileExtensions = Object.keys(fileKinds)
export const fileFormatLabels = fileExtensions.map(ext => ext === 'webm' ? 'WebM' : ext.toUpperCase()).join('、')
export const photoExtensions = ['jpg', 'jpeg', 'png', 'webp']
export const photoMaxCount = 8
export const photoMaxBytes = 10 * 1024 * 1024

export function workAttachments(work?: Work) {
  return work?.assets.filter((asset): asset is Asset & { kind: WorkKind } => asset.kind !== 'photo') ?? []
}

export function assetPath(work: Work, asset: Asset, action: 'video' | 'audio' | 'pdf' | 'viewer' | 'download' | 'photo'): string {
  return '/api/works/' + work.id + '/assets/' + asset.id + '/' + action + '/'
}

export function pdfReaderPath(workId: string, assetId: string): string {
  return '#pdf/' + workId + '/' + assetId
}

export function workDetailPath(workId: string): string {
  return '#work/' + workId
}

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
