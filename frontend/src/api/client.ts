/** 统一请求封装：拼后端地址、带上当前操作账号、抛网络错误、给页脚留一句可读的说明。 */
import { ACCOUNT_KEY } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function identityHeaders(): Record<string, string> {
  // 每次请求实时读当前账号，切换账号后无需刷新页面即可生效
  try {
    const raw = localStorage.getItem(ACCOUNT_KEY)
    if (!raw) return {}
    const account = JSON.parse(raw) as { name?: string; role?: string; team?: string }
    return {
      'X-Operator-Name': encodeURIComponent(account.name ?? ''),
      'X-Operator-Role': encodeURIComponent(account.role ?? ''),
      'X-Operator-Team': encodeURIComponent(account.team ?? ''),
    }
  } catch {
    return {}
  }
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...identityHeaders(), ...(init?.headers ?? {}) },
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
