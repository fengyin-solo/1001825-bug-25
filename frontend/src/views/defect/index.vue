<template>
  <section class="page" data-module="defect">
    <header class="page-head">
      <div>
        <h2>缺陷登记管理</h2>
        <p class="page-desc">
          登记人与管理岗位（限本班组范围）才能改定级；状态按 待定级 → 已定级 → 处置中 → 已闭环 顺序流转，整改结论自动落入安全台账。
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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="toggleHistory(row)">历史</button>
            <span v-if="!rowActions(row).length" class="action-hint">已闭环</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无缺陷登记数据，可先登记缺陷记录</td>
        </tr>
      </tbody>
    </table>

    <section v-if="historyFor !== null" class="history-panel">
      <h3>定级与流转历史（{{ historyCode }}）</h3>
      <table class="data-table">
        <thead>
          <tr><th>时间</th><th>操作人</th><th>岗位</th><th>班组</th><th>动作</th><th>严重等级</th><th>状态</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in historyRows" :key="idx">
            <td>{{ item['时间'] }}</td>
            <td>{{ item['操作人'] }}</td>
            <td>{{ item['岗位'] }}</td>
            <td>{{ item['班组'] }}</td>
            <td>{{ item['动作'] }}</td>
            <td>{{ item['原等级'] }} → {{ item['新等级'] }}</td>
            <td>{{ item['原状态'] }} → {{ item['新状态'] }}</td>
            <td>{{ item['说明'] || '—' }}</td>
          </tr>
          <tr v-if="!historyRows.length">
            <td colspan="8" class="empty-state">暂无历史记录</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条缺陷登记记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="dialog" class="modal-mask" @click.self="dialog = null">
      <div class="modal-card">
        <h3>{{ dialog.action }}（{{ dialog.row['缺陷编号'] }}）</h3>
        <label v-if="needsLevel" class="modal-field">
          <span>严重等级</span>
          <select v-model="actionForm['严重等级']">
            <option value="" disabled>请选择严重等级</option>
            <option v-for="level in severityLevels" :key="level" :value="level">{{ level }}</option>
          </select>
        </label>
        <label v-if="dialog.action === '提交闭环'" class="modal-field">
          <span>整改结论</span>
          <textarea v-model="actionForm['整改结论']" rows="3" placeholder="闭环结论会同步到安全台账首页"></textarea>
        </label>
        <label v-if="dialog.action === '挂起缺陷'" class="modal-field">
          <span>挂起原因</span>
          <input v-model="actionForm['挂起原因']" placeholder="选填；挂起不改变当前状态" />
        </label>
        <p class="modal-tip">操作账号：{{ session.operatorLabel }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitAction">确认{{ dialog.action }}</button>
          <button class="btn ghost" type="button" @click="dialog = null">取消</button>
        </div>
      </div>
    </div>

    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal-card">
        <h3>登记缺陷记录</h3>
        <label v-for="field in createFields" :key="field" class="modal-field">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p class="modal-tip">登记人员、所属班组取当前账号：{{ session.operatorLabel }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitCreate">确认登记</button>
          <button class="btn ghost" type="button" @click="createOpen = false">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type HistoryItem = Record<string, string | number>

const ENDPOINT = '/api/defect'
const columns = ["缺陷编号", "所在管段", "缺陷类别", "缺陷位置", "严重等级", "发现日期", "登记人员", "所属班组", "缺陷状态"]
const severityLevels = ["轻微", "一般", "较大", "重大"]
const statusOrder = ["待定级", "已定级", "处置中", "已闭环"]
// 状态只能按顺序走：每个状态只暴露下一步需要的动作
const transitionActions: Record<string, string[]> = {
  "待定级": ["确认定级"],
  "已定级": ["改定级", "开始处置"],
  "处置中": ["改定级", "提交闭环"],
  "已闭环": [],
}
const createFields = ["缺陷编号", "所在管段", "缺陷类别", "缺陷位置"]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const stats = ref(statusOrder.map((item) => ({ label: `${item}缺陷`, value: 0 })))

const dialog = ref<{ action: string; row: Row } | null>(null)
const actionForm = ref<Record<string, string>>({ '严重等级': '', '整改结论': '', '挂起原因': '' })
const createOpen = ref(false)
const createForm = ref<Record<string, string>>({})

const historyFor = ref<number | null>(null)
const historyCode = ref('')
const historyRows = ref<HistoryItem[]>([])

const needsLevel = computed(() => dialog.value?.action === '确认定级' || dialog.value?.action === '改定级')

function rowActions(row: Row): string[] {
  const status = String(row['缺陷状态'] ?? '')
  const acts = [...(transitionActions[status] ?? [])]
  if (status && status !== statusOrder[statusOrder.length - 1]) acts.push('挂起缺陷')
  return acts
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createOpen.value = true
}

function openAction(action: string, row: Row) {
  actionForm.value = { '严重等级': String(row['严重等级'] ?? ''), '整改结论': '', '挂起原因': '' }
  dialog.value = { action, row }
}

async function submitAction() {
  if (!dialog.value) return
  errorMessage.value = ''
  const { action, row } = dialog.value
  const values: Record<string, string> = { action }
  if (action === '确认定级' || action === '改定级') values['严重等级'] = actionForm.value['严重等级']
  if (action === '提交闭环') values['整改结论'] = actionForm.value['整改结论']
  if (action === '挂起缺陷') values['挂起原因'] = actionForm.value['挂起原因']
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      // 挡回原因（卡在哪一项）由后端给出，原样展示
      errorMessage.value = payload?.message ?? payload?.detail ?? '缺陷登记动作未生效，请稍后重试'
      return
    }
    dialog.value = null
    await Promise.all([reload(), loadLedger()])
    if (historyFor.value !== null) await loadHistory(historyFor.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缺陷登记操作失败'
  }
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      errorMessage.value = payload?.message ?? payload?.detail ?? '缺陷记录登记未生效，请稍后重试'
      return
    }
    createOpen.value = false
    await Promise.all([reload(), loadLedger()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缺陷记录登记失败'
  }
}

async function toggleHistory(row: Row) {
  if (historyFor.value === Number(row.id)) {
    historyFor.value = null
    return
  }
  await loadHistory(Number(row.id), String(row['缺陷编号'] ?? ''))
}

async function loadHistory(entryId: number, code = '') {
  try {
    const response = await request(`${ENDPOINT}/${entryId}/history`)
    if (!response.ok) throw new Error('历史记录读取失败')
    const payload = await response.json()
    historyRows.value = payload.items ?? []
    historyFor.value = entryId
    if (code) historyCode.value = code
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '历史记录读取失败'
  }
}

async function loadLedger() {
  try {
    const response = await request(`${ENDPOINT}/ledger`)
    if (!response.ok) return
    const payload = await response.json()
    const byStatus = payload.status ?? []
    stats.value = byStatus.map((item: { 状态: string; 条数: number }) => ({ label: `${item.状态}缺陷`, value: item.条数 }))
  } catch {
    // 统计读取失败不阻塞列表
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('缺陷记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缺陷登记列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadLedger()
})
</script>
