<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。点击模块名称可回到对应列表核对。</p>
      </div>
      <div class="page-actions dashboard-tools">
        <button class="btn" type="button" :disabled="loading" @click="loadOverview">
          {{ loading ? '刷新中…' : '刷新数据' }}
        </button>
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
          <td>
            <button class="module-link" type="button" @click="openModule(row.name)">
              {{ moduleLabels[row.name] ?? row.name }}
            </button>
          </td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
        <tr v-if="!moduleRows.length">
          <td colspan="4" class="empty-state">暂未读到汇总数据，可点右上角“刷新数据”重试</td>
        </tr>
      </tbody>
    </table>
    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

// 后端模块代号到中文名称与列表路由的映射；路由路径与模块代号一致
const moduleLabels: Record<string, string> = {
  windfarm: '风电场站',
  turbine: '风电机组',
  blade: '叶片',
  gearbox: '齿轮箱',
  generator: '发电机',
  pitch: '变桨系统',
  yaw: '偏航系统',
  metmast: '测风塔',
  collector: '集电线路',
  substation: '升压站',
  forecast: '功率预测',
  vibration: '振动监测',
  defect: '缺陷登记',
  maintjob: '检修任务',
  spare: '备件领用',
  patrol: '巡视检查',
  accept: '验收确认',
  settle: '电量结算',
}

const router = useRouter()
const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const loading = ref(false)
const errorMessage = ref('')

function openModule(name: string) {
  void router.push(`/${name}`)
}

async function loadOverview() {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch (error) {
    cards.value = []
    moduleRows.value = []
    errorMessage.value = error instanceof Error ? error.message : '运营概览读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// 看板每次重新进入都会重新挂载并拉取，退役后的行数随之一并刷新
onMounted(loadOverview)
</script>
