import { defineStore } from 'pinia'

/** 演示花名册：与后端 app/identity.py 保持一致，岗位只能由这里决定，前端不能自行提权。 */
export interface Account {
  name: string
  team: string
  role: '登记人' | '管理员'
}

export const ACCOUNTS: Account[] = [
  { name: '王登', team: '巡检一班', role: '登记人' },
  { name: '赵管', team: '巡检一班', role: '管理员' },
  { name: '李巡', team: '巡检二班', role: '登记人' },
  { name: '钱管', team: '巡检二班', role: '管理员' },
]

const STORAGE_KEY = 'defect-session'

function restore(): Account {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved) as Account
      const hit = ACCOUNTS.find((item) => item.name === parsed.name)
      if (hit) return hit
    }
  } catch {
    // 本地缓存损坏时回落到默认账号，不阻塞进系统
  }
  return ACCOUNTS[0]
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    // 换账号后落到 localStorage：再进入系统仍沿用同一身份，历史定级不会“像丢失”
    account: restore(),
    shiftLabel: '白班 08:00-20:00',
    scope: '城市地下管网巡检养护平台',
  }),
  getters: {
    operator: (state) => state.account.name,
    team: (state) => state.account.team,
    role: (state) => state.account.role,
    isManager(): boolean {
      return this.role === '管理员'
    },
    canOperate: (state) => state.account.name.length > 0,
    /** 随每个请求带给后端的身份头 */
    headers(): Record<string, string> {
      return { 'X-Operator': this.operator }
    },
  },
  actions: {
    switchAccount(name: string) {
      const hit = ACCOUNTS.find((item) => item.name === name)
      if (!hit) return
      this.account = hit
      localStorage.setItem(STORAGE_KEY, JSON.stringify(hit))
    },
    /** 这条缺陷当前账号能不能改定级/推动状态：仅登记本人或同班组管理员。 */
    canModifyDefect(row: { 登记人员?: unknown; 归属班组?: unknown }): boolean {
      if (this.role === '管理员') return row.归属班组 === this.team
      return row.归属班组 === this.team && row.登记人员 === this.operator
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
