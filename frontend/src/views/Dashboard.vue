<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>

    <section class="ledger-block">
      <h3>缺陷安全台账</h3>
      <p class="page-desc">与缺陷登记列表同一份数据汇总：等级分布、状态分布与整改结论，条数实时对得上。</p>
      <div class="stat-row">
        <article v-for="item in severityCards" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>
      <div class="stat-row">
        <article v-for="item in statusCards" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>缺陷编号</th><th>严重等级</th><th>整改结论</th><th>闭环时间</th><th>登记人员</th><th>所属班组</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in conclusions" :key="String(row['缺陷编号'])">
            <td>{{ row['缺陷编号'] }}</td>
            <td>{{ row['严重等级'] }}</td>
            <td>{{ row['整改结论'] }}</td>
            <td>{{ row['闭环时间'] }}</td>
            <td>{{ row['登记人员'] }}</td>
            <td>{{ row['所属班组'] }}</td>
          </tr>
          <tr v-if="!conclusions.length">
            <td colspan="6" class="empty-state">暂无已闭环的整改结论</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}
type Ledger = {
  total: number
  severity: { 等级: string; 条数: number }[]
  status: { 状态: string; 条数: number }[]
  conclusions: Record<string, string | null>[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const severityCards = ref<{ label: string; value: number }[]>([])
const statusCards = ref<{ label: string; value: number }[]>([])
const conclusions = ref<Ledger['conclusions']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "管段档案", "created": 0, "pending": 0, "abnormal": 0}, {"name": "检查井", "created": 0, "pending": 0, "abnormal": 0}, {"name": "阀门井室", "created": 0, "pending": 0, "abnormal": 0}, {"name": "泵站设施", "created": 0, "pending": 0, "abnormal": 0}, {"name": "巡查任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "缺陷登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "内窥检测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "修复施工", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "流量监测", "created": 0, "pending": 0, "abnormal": 0}, {"name": "泄漏排查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "清淤疏浚", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护材料", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护机械", "created": 0, "pending": 0, "abnormal": 0}, {"name": "占道许可", "created": 0, "pending": 0, "abnormal": 0}, {"name": "公众诉求", "created": 0, "pending": 0, "abnormal": 0}, {"name": "养护资金", "created": 0, "pending": 0, "abnormal": 0}, {"name": "管网档案", "created": 0, "pending": 0, "abnormal": 0}]
  }
  try {
    const ledger = await fetchJson<Ledger>('/api/defect/ledger')
    severityCards.value = ledger.severity.map((item) => ({ label: `等级·${item.等级}`, value: item.条数 }))
    statusCards.value = ledger.status.map((item) => ({ label: `状态·${item.状态}`, value: item.条数 }))
    conclusions.value = ledger.conclusions
  } catch {
    severityCards.value = []
    statusCards.value = []
    conclusions.value = []
  }
})
</script>
