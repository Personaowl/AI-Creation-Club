import type { Asset, Work } from './works'

export interface Account {
  id: number
  username: string
  is_admin: boolean
}

interface Session {
  user: Account | null
  csrf_token: string
}

let token = ''

export class RequestError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, method = 'GET', body?: object | FormData): Promise<T> {
  const headers = new Headers({ Accept: 'application/json' })
  if (method !== 'GET') headers.set('X-CSRFToken', token)
  if (body && !(body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch('/api/' + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new RequestError(0, '无法连接作品平台，请检查后端服务。')
  }
  if (response.status === 204) return undefined as T
  const result = await response.json().catch(() => null)
  if (!response.ok || result === null) {
    let detail = '请求失败，请稍后重试。'
    if (typeof result?.detail === 'string') detail = result.detail
    else if (result && typeof result === 'object') {
      const message = Object.values(result).flat().find(value => typeof value === 'string')
      if (typeof message === 'string') detail = message
    } else if (response.status >= 500) detail = '暂时无法连接后端服务。'
    throw new RequestError(response.status, detail)
  }
  return result as T
}

async function authenticate(path: string, method: string, body?: object): Promise<Account | null> {
  const session = await request<Session>('auth/' + path + '/', method, body)
  token = session.csrf_token
  return session.user
}

export const readSession = () => authenticate('session', 'GET')
export const signIn = (username: string, password: string) => authenticate('login', 'POST', { username, password })
export const signOut = () => authenticate('logout', 'POST')
export const changePassword = (current_password: string, password: string) =>
  authenticate('password', 'POST', { current_password, password })

export const readWorks = (scope: 'gallery' | 'mine') => request<Work[]>('works/?scope=' + scope)
export const createWork = (title: string, description: string) => request<Work>('works/', 'POST', { title, description })
export const updateWork = (id: string, title: string, description: string) =>
  request<Work>('works/' + id + '/', 'PATCH', { title, description })
export const submitWork = (id: string) => request<Work>('works/' + id + '/submit/', 'POST')

export function uploadAsset(id: string, file: File) {
  const data = new FormData()
  data.set('file', file)
  return request<Asset>('works/' + id + '/assets/', 'POST', data)
}

export const deleteAsset = (workId: string, assetId: string) =>
  request<void>('works/' + workId + '/assets/' + assetId + '/', 'DELETE')
