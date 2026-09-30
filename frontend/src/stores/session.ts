import { defineStore } from 'pinia'

export type Account = { name: string; role: string; team: string }

// 与后端 app/services/identity.py 的在册账号保持一致
const ACCOUNTS: Account[] = [
  { name: '张三', role: '登记员', team: '一班' },
  { name: '李四', role: '登记员', team: '二班' },
  { name: '王五', role: '管理', team: '一班' },
  { name: '赵六', role: '管理', team: '二班' },
  { name: '平台管理员', role: '管理', team: '总部' },
]

export const ACCOUNT_KEY = 'session.account'

function loadAccount(): Account {
  try {
    const raw = localStorage.getItem(ACCOUNT_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Account>
      const hit = ACCOUNTS.find((item) => item.name === parsed.name)
      if (hit) return hit
    }
  } catch {
    // 本地缓存损坏时回落到默认账号
  }
  return ACCOUNTS[0]
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    account: loadAccount(),
    accounts: ACCOUNTS,
    shiftLabel: '白班 08:00-20:00',
    scope: '城市地下管网巡检养护平台',
  }),
  getters: {
    canOperate: (state) => state.account.name.length > 0,
    operatorLabel: (state) => `${state.account.name} · ${state.account.role} · ${state.account.team}`,
  },
  actions: {
    switchAccount(name: string) {
      const hit = this.accounts.find((item) => item.name === name)
      if (!hit) return
      this.account = hit
      // 持久化当前账号：换账号、刷新、再进入系统时身份保持一致
      localStorage.setItem(ACCOUNT_KEY, JSON.stringify(hit))
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
