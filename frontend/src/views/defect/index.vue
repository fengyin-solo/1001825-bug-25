<template>
  <section class="page" data-module="defect">
    <header class="page-head">
      <div>
        <h2>缺陷登记管理</h2>
        <p class="page-desc">
          维护缺陷记录与定级流转：只有登记本人或本班组管理员能改定级，状态按
          待定级 → 已定级 → 处置中 → 已闭环 顺序推进，每次定级都留痕。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记缺陷记录</button>
        <button class="btn" type="button" @click="exportRows">导出缺陷登记清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>缺陷编号</span>
        <input v-model="filters.keyword" placeholder="按缺陷编号检索" />
      </label>
      <label class="filter-item">
        <span>缺陷状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>严重等级</span>
        <select v-model="filters.level">
          <option value="">全部等级</option>
          <option v-for="level in levels" :key="level" :value="level">{{ level }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '严重等级'" :class="`level-${row[column] ?? ''}`">{{ row[column] || '—' }}</span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <template v-for="action in actionsFor(row)" :key="action.key">
              <button
                v-if="action.enabled"
                class="link"
                type="button"
                @click="openAction(action.key, row)"
              >
                {{ action.key }}
              </button>
              <span v-else class="locked-text" :title="action.reason">{{ action.key }}🔒</span>
            </template>
            <button class="link" type="button" @click="openHistory(row)">定级记录</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的缺陷记录，可先登记缺陷</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条缺陷登记记录（列表等级与安全台账同源）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="ok-text">{{ successMessage }}</span>
    </footer>

    <!-- 登记 / 定级操作共用弹窗 -->
    <div v-if="dialog.mode" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>{{ dialogTitle }}</h3>
        <div class="modal-body">
          <template v-if="dialog.mode === 'create'">
            <label class="form-row">
              <span>缺陷编号<span class="required-mark">*</span></span>
              <input v-model="dialog.form.缺陷编号" placeholder="如 DEFE-0010" />
            </label>
            <label class="form-row">
              <span>所在管段<span class="required-mark">*</span></span>
              <input v-model="dialog.form.所在管段" />
            </label>
            <label class="form-row">
              <span>缺陷类别<span class="required-mark">*</span></span>
              <input v-model="dialog.form.缺陷类别" placeholder="如 管道破裂、接口错位" />
            </label>
            <label class="form-row">
              <span>缺陷位置</span>
              <input v-model="dialog.form.缺陷位置" />
            </label>
            <label class="form-row">
              <span>发现日期</span>
              <input v-model="dialog.form.发现日期" type="date" />
            </label>
            <p class="page-desc">
              登记人员「{{ store.operator }}」、归属班组「{{ store.team }}」由登录账号自动带入，
              页面无法改挂到别的班组。
            </p>
          </template>
          <template v-else>
            <p class="page-desc">
              缺陷 {{ dialog.row?.['缺陷编号'] }} 当前状态「{{ dialog.row?.status }}」，
              归属 {{ dialog.row?.['归属班组'] }} · 登记人 {{ dialog.row?.['登记人员'] }}
            </p>
            <label v-if="needsLevel" class="form-row">
              <span>严重等级<span class="required-mark">*</span></span>
              <select v-model="dialog.form.严重等级">
                <option value="" disabled>请选择严重等级</option>
                <option v-for="level in levels" :key="level" :value="level">{{ level }}</option>
              </select>
            </label>
            <label v-if="dialog.action === '提交闭环'" class="form-row">
              <span>整改结论<span class="required-mark">*</span></span>
              <textarea v-model="dialog.form.整改结论" placeholder="闭环必须填写整改结论，结论将落到安全台账首页"></textarea>
            </label>
          </template>
        </div>
        <footer class="modal-foot">
          <span v-if="dialog.error" class="error-text">卡在【{{ dialog.blocked || '校验' }}】：{{ dialog.error }}</span>
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitDialog">
            {{ submitting ? '提交中…' : '提交' }}
          </button>
        </footer>
      </div>
    </div>

    <!-- 定级/流转历史 -->
    <div v-if="history.open" class="modal-mask" @click.self="history.open = false">
      <div class="modal" style="width: 720px">
        <h3>定级与流转记录 · {{ history.code }}</h3>
        <div class="modal-body">
          <table class="history-table">
            <thead>
              <tr><th>时间</th><th>动作</th><th>状态变化</th><th>严重等级</th><th>整改结论</th><th>操作人</th><th>班组</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in history.items" :key="index">
                <td>{{ item['时间'] }}</td>
                <td>{{ item.action }}</td>
                <td>{{ item.from || '—' }} → {{ item.to }}</td>
                <td :class="`level-${item['严重等级'] ?? ''}`">{{ item['严重等级'] || '—' }}</td>
                <td>{{ item['整改结论'] || '—' }}</td>
                <td>{{ item['操作人'] }}</td>
                <td>{{ item['归属班组'] }}</td>
              </tr>
              <tr v-if="!history.items.length">
                <td colspan="7" class="empty-state">该缺陷暂无定级记录</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="modal-foot">
          <button class="btn primary" type="button" @click="history.open = false">关闭</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type HistoryItem = Record<string, string>

const ENDPOINT = '/api/defect'
const columns = ['缺陷编号', '所在管段', '缺陷类别', '缺陷位置', '严重等级', '发现日期', '登记人员', '归属班组', '缺陷状态']
const levels = ['轻微', '一般', '严重', '重大']
const statuses = ['待定级', '已定级', '处置中', '已闭环']
// 每个状态只暴露顺序上的下一步动作；定级后若发现判错，可用「调整定级」改判而不改状态
const NEXT_ACTION: Record<string, string> = {
  待定级: '确认定级',
  已定级: '提交处置',
  处置中: '提交闭环',
}

const store = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const ledger = ref<{ by_status: Record<string, number>; by_level: Record<string, number> }>({
  by_status: {},
  by_level: {},
})
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<{ keyword: string; status: string; level: string }>({ keyword: '', status: '', level: '' })

// 卡片直接取安全台账口径，与首页、台账条数永远一致，不随当前筛选页变化
const stats = computed(() => [
  { label: '待定级缺陷', value: ledger.value.by_status['待定级'] ?? 0 },
  { label: '处置中缺陷', value: (ledger.value.by_status['已定级'] ?? 0) + (ledger.value.by_status['处置中'] ?? 0) },
  { label: '严重及以上', value: (ledger.value.by_level['严重'] ?? 0) + (ledger.value.by_level['重大'] ?? 0) },
])

function resetFilters() {
  filters.value = { keyword: '', status: '', level: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

/** 每个状态给出该出现的动作及当前账号是否可执行；不可执行时说明卡在哪。 */
function actionsFor(row: Row): { key: string; enabled: boolean; reason: string }[] {
  const list: { key: string; enabled: boolean; reason: string }[] = []
  const status = String(row.status ?? '')
  const next = NEXT_ACTION[status]
  if (next) list.push({ key: next, enabled: store.canModifyDefect(row), reason: denyReason(row) })
  if (status === '已定级' || status === '处置中') {
    list.push({ key: '调整定级', enabled: store.canModifyDefect(row), reason: denyReason(row) })
  }
  return list
}

function denyReason(row: Row): string {
  if (row.归属班组 !== store.team) {
    return `归属班组不符：该缺陷属于${row.归属班组}，当前账号属于${store.team}`
  }
  if (!store.isManager && row.登记人员 !== store.operator) {
    return `只有登记人${String(row.登记人员)}或本班组管理员可以操作`
  }
  return ''
}

// ---- 弹窗 ----
type DialogMode = '' | 'create' | 'action'
const dialog = reactive<{
  mode: DialogMode
  action: string
  row: Row | null
  form: { 缺陷编号: string; 所在管段: string; 缺陷类别: string; 缺陷位置: string; 发现日期: string; 严重等级: string; 整改结论: string }
  error: string
  blocked: string
}>({
  mode: '',
  action: '',
  row: null,
  form: { 缺陷编号: '', 所在管段: '', 缺陷类别: '', 缺陷位置: '', 发现日期: '', 严重等级: '', 整改结论: '' },
  error: '',
  blocked: '',
})
const submitting = ref(false)

const dialogTitle = computed(() => {
  if (dialog.mode === 'create') return `登记缺陷记录（${store.team} · ${store.operator}）`
  return `${dialog.action} · ${String(dialog.row?.['缺陷编号'] ?? '')}`
})
const needsLevel = computed(() => dialog.action === '确认定级' || dialog.action === '调整定级')

function emptyForm() {
  return { 缺陷编号: '', 所在管段: '', 缺陷类别: '', 缺陷位置: '', 发现日期: '', 严重等级: '', 整改结论: '' }
}

function openCreate() {
  dialog.mode = 'create'
  dialog.action = ''
  dialog.row = null
  dialog.form = emptyForm()
  dialog.error = ''
  dialog.blocked = ''
}

function openAction(action: string, row: Row) {
  dialog.mode = 'action'
  dialog.action = action
  dialog.row = row
  dialog.form = { ...emptyForm(), 严重等级: String(row['严重等级'] ?? '') }
  dialog.error = ''
  dialog.blocked = ''
}

function closeDialog() {
  dialog.mode = ''
}

async function submitDialog() {
  dialog.error = ''
  dialog.blocked = ''
  submitting.value = true
  try {
    if (dialog.mode === 'create') {
      const values = {
        缺陷编号: dialog.form.缺陷编号.trim(),
        所在管段: dialog.form.所在管段.trim(),
        缺陷类别: dialog.form.缺陷类别.trim(),
        缺陷位置: dialog.form.缺陷位置.trim(),
        发现日期: dialog.form.发现日期,
      }
      const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
      const payload = await response.json()
      if (!payload.ok) {
        dialog.blocked = payload.blocked ?? ''
        dialog.error = payload.message
        return
      }
      dialog.mode = ''
      successMessage.value = '缺陷记录已登记，初始状态为待定级'
      await reload()
      return
    }

    const values: Record<string, string> = { action: dialog.action }
    if (needsLevel.value) values.严重等级 = dialog.form.严重等级
    if (dialog.action === '提交闭环') values.整改结论 = dialog.form.整改结论.trim()
    const response = await request(`${ENDPOINT}/${dialog.row?.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      // 后端明确说明卡在哪一项：归属班组 / 登记人员 / 状态顺序 / 严重等级 / 整改结论
      dialog.blocked = payload.blocked ?? ''
      dialog.error = payload.message
      return
    }
    dialog.mode = ''
    successMessage.value = payload.message
    await reload()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '提交失败'
  } finally {
    submitting.value = false
  }
}

// ---- 历史 ----
const history = reactive<{ open: boolean; code: string; items: HistoryItem[] }>({
  open: false,
  code: '',
  items: [],
})

async function openHistory(row: Row) {
  history.open = true
  history.code = String(row['缺陷编号'] ?? '')
  history.items = []
  try {
    const response = await request(`${ENDPOINT}/${row.id}/history`)
    if (!response.ok) throw new Error('定级记录读取失败')
    const payload = await response.json()
    history.items = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '定级记录读取失败'
    history.open = false
  }
}

// ---- 列表 ----
async function reload() {
  errorMessage.value = ''
  successMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) query.set('keyword', filters.value.keyword.trim())
  if (filters.value.status) query.set('status', filters.value.status)
  if (filters.value.level) query.set('level', filters.value.level)
  try {
    const [listResponse, ledgerResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/ledger`),
    ])
    if (!listResponse.ok) {
      throw new Error('缺陷记录列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (ledgerResponse.ok) {
      ledger.value = await ledgerResponse.json()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缺陷登记列表读取失败'
  }
}

// 换账号后重新拉取：按钮权限随之变化，但定级历史始终来自后端、不会随账号消失
watch(() => store.account.name, () => void reload())

onMounted(reload)
</script>
