<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览 · 安全台账首页</h2>
        <p class="page-desc">汇总各业务模块的关键指标；缺陷安全台账与缺陷登记列表同源，定级、闭环整改结论在此落账。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <section v-if="defectLedger" class="ledger-panel">
      <h3>缺陷登记安全台账</h3>
      <div class="ledger-grid">
        <span>台账总数<strong>{{ defectLedger.total }}</strong></span>
        <span v-for="status in statusLabels" :key="status">
          {{ status }}<strong>{{ defectLedger.by_status[status] ?? 0 }}</strong>
        </span>
        <span>待闭环<strong>{{ defectLedger.pending_close }}</strong></span>
        <span>严重及以上<strong class="level-严重">{{ defectLedger.abnormal }}</strong></span>
      </div>
      <div class="ledger-grid">
        <span v-for="level in levelLabels" :key="level">
          <span :class="`level-${level}`">{{ level }}</span><strong>{{ defectLedger.by_level[level] ?? 0 }}</strong>
        </span>
      </div>
      <h3 style="margin-top: 12px">闭环缺陷整改结论</h3>
      <table class="data-table">
        <thead>
          <tr><th>缺陷编号</th><th>所在管段</th><th>严重等级</th><th>整改结论</th><th>归属班组</th><th>登记人员</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in defectLedger.closed" :key="String(item['缺陷编号'])">
            <td>{{ item['缺陷编号'] }}</td>
            <td>{{ item['所在管段'] }}</td>
            <td :class="`level-${item['严重等级'] ?? ''}`">{{ item['严重等级'] }}</td>
            <td>{{ item['整改结论'] }}</td>
            <td>{{ item['归属班组'] }}</td>
            <td>{{ item['登记人员'] }}</td>
          </tr>
          <tr v-if="!defectLedger.closed.length">
            <td colspan="6" class="empty-state">暂无已闭环缺陷，整改结论将在闭环时落到这里</td>
          </tr>
        </tbody>
      </table>
    </section>

    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ moduleLabel(row.name) }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td :class="row.name === 'defect' ? 'level-严重' : ''">{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type LedgerClosed = {
  缺陷编号: string
  所在管段: string
  严重等级: string
  整改结论: string
  归属班组: string
  登记人员: string
}

type DefectLedger = {
  total: number
  by_status: Record<string, number>
  by_level: Record<string, number>
  abnormal: number
  pending_close: number
  closed: LedgerClosed[]
}

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  defect_ledger?: DefectLedger
}

const statusLabels = ['待定级', '已定级', '处置中', '已闭环']
const levelLabels = ['轻微', '一般', '严重', '重大']
const MODULE_LABELS: Record<string, string> = {
  pipe: '管段档案', manhole: '检查井', valve: '阀门井室', pumpstation: '泵站设施',
  patrol: '巡查任务', defect: '缺陷登记', cctv: '内窥检测', repair: '修复施工',
  pressure: '压力监测', flow: '流量监测', leak: '泄漏排查', dredge: '清淤疏浚',
  material: '养护材料', equip: '养护机械', traffic: '占道许可', complaint: '公众诉求',
  fund: '养护资金', archive: '管网档案',
}
function moduleLabel(name: string): string {
  return MODULE_LABELS[name] ?? name
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const defectLedger = ref<DefectLedger | null>(null)

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    defectLedger.value = payload.defect_ledger ?? null
  } catch {
    cards.value = [{ label: '业务模块', value: 0 }, { label: '今日新增', value: 0 }]
    moduleRows.value = []
  }
})
</script>
