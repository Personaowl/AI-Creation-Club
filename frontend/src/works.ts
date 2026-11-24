export type WorkKind = 'slides' | 'video' | 'source'
export type Cover = 'form' | 'lake' | 'code' | 'architecture'
export type WorkStatus = 'draft' | 'pending' | 'approved' | 'rejected'

export interface Asset {
  id: string
  original_name: string
  extension: string
  kind: WorkKind
  size: number
}

export interface Work {
  id: string
  title: string
  description: string
  status: WorkStatus
  is_visible: boolean
  assets: Asset[]
  created_at: string
  updated_at: string
  is_mine: boolean
  can_edit: boolean
  can_download: boolean
  review_note: string
}

export const kindLabels: Record<WorkKind, string> = { slides: '演示文稿', video: '视频', source: '源码' }
export const statusLabels: Record<WorkStatus, string> = { draft: '草稿', pending: '待审核', approved: '已通过', rejected: '已退回' }
export const fileKinds: Record<string, WorkKind> = { ppt: 'slides', pptx: 'slides', mp4: 'video', webm: 'video', zip: 'source' }

export function assetPath(work: Work, asset: Asset, action: 'video' | 'viewer' | 'download'): string {
  return '/api/works/' + work.id + '/assets/' + asset.id + '/' + action + '/'
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
