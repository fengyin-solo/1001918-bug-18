<template>
  <section class="page" data-module="turbine">
    <header class="page-head">
      <div>
        <h2>风电机组管理</h2>
        <p class="page-desc">维护风电机组，围绕机组编号、机组机型、额定功率、轮毂高度做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记风电机组</button>
        <button class="btn" type="button" @click="exportRows">导出风电机组清单</button>
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
        <span>机组编号</span>
        <input v-model="keyword" placeholder="按机组编号检索" />
      </label>
      <label class="filter-item">
        <span>机组状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
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
            <button v-if="column === '机组编号'" class="link" type="button" @click="openDetail(row)">
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-if="row.status === '已退役'">
              <span class="muted-text">已退役，终态锁定</span>
            </template>
            <template v-else>
              <button
                v-for="action in availableActions(String(row.status))"
                :key="action"
                class="link"
                type="button"
                :disabled="busyKey === `${row.id}:${action}`"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
              <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无风电机组数据，可先登记风电机组</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条风电机组记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <header class="modal-head">
          <h3>机组详情 · {{ detailForm.机组编号 }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <p v-if="detailReadonly" class="modal-tip">该机组已退役，台账为只读；如需恢复请重新建档。</p>
        <dl class="detail-grid">
          <div v-for="field in readonlyFields" :key="field" class="detail-item">
            <dt>{{ field }}</dt>
            <dd>{{ detailForm[field] || '—' }}</dd>
          </div>
          <div v-for="field in editableFields" :key="field" class="detail-item">
            <dt>{{ field }}</dt>
            <dd>
              <input
                v-model="detailForm[field]"
                :disabled="detailReadonly || detailSaving"
                :placeholder="`请输入${field}`"
              />
            </dd>
          </div>
        </dl>
        <footer class="modal-foot">
          <span v-if="detailMessage" :class="detailError ? 'error-text' : 'success-text'">{{ detailMessage }}</span>
          <span class="modal-spacer" />
          <button class="btn ghost" type="button" :disabled="detailSaving" @click="closeDetail">取消</button>
          <button
            v-if="!detailReadonly"
            class="btn primary"
            type="button"
            :disabled="detailSaving"
            @click="saveDetail"
          >
            {{ detailSaving ? '保存中…' : '保存修改' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/turbine'
const columns = ['机组编号', '机组机型', '额定功率', '轮毂高度', '所属场站', '投运日期', '累计发电量', '机组状态']
const statuses = ['待投运', '运行中', '故障停机', '已退役']
const editableFields = ['机组机型', '轮毂高度']
const readonlyFields = columns.filter((field) => !editableFields.includes(field) && field !== '机组编号')
// 只暴露从当前状态出发合法的动作，避免已退役机组被「投运机组」打回运行中。
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  待投运: ['投运机组', '登记停机', '办理退役'],
  运行中: ['登记停机', '办理退役'],
  故障停机: ['投运机组', '办理退役'],
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref([
  { label: '在运机组', value: 0 },
  { label: '故障停机台数', value: 0 },
  { label: '待处理机组', value: 0 },
])
const busyKey = ref('')

function availableActions(status: string): string[] {
  return ACTIONS_BY_STATUS[status] ?? []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '风电机组登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  busyKey.value = `${row.id}:${action}`
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('风电机组动作未生效，请稍后重试')
    }
    const payload = await response.json()
    // 业务校验失败时后端不动原记录：只提示，不刷新，列表里留下的仍是原有内容。
    if (!payload.ok) {
      errorMessage.value = payload.message || '风电机组动作未生效，请稍后重试'
      return
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电机组操作失败'
  } finally {
    busyKey.value = ''
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const data = await response.json()
    // 与运营概览取同一个按机组编号去重的统计口径，筛选/分页都不影响卡片数字。
    stats.value = [
      { label: '在运机组', value: Number(data.running ?? 0) },
      { label: '故障停机台数', value: Number(data.fault ?? 0) },
      { label: '待处理机组', value: Number(data.pending ?? 0) },
    ]
  } catch {
    // 统计拉取失败不阻断列表操作，保留上一次的数字。
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('风电机组列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电机组列表读取失败'
  }
}

const detailVisible = ref(false)
const detailReadonly = ref(false)
const detailSaving = ref(false)
const detailError = ref(false)
const detailMessage = ref('')
const detailId = ref<number | null>(null)
const detailForm = ref<Record<string, string>>({})

async function openDetail(row: Row) {
  errorMessage.value = ''
  detailMessage.value = ''
  detailError.value = false
  detailId.value = Number(row.id)
  detailVisible.value = true
  detailReadonly.value = row.status === '已退役'
  try {
    // 详情始终向后端取同一条记录，保证列表与详情不会各写各的。
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('机组详情读取失败')
    }
    const entry = await response.json()
    detailForm.value = {
      机组编号: String(entry['机组编号'] ?? ''),
      机组机型: String(entry['机组机型'] ?? ''),
      额定功率: String(entry['额定功率'] ?? ''),
      轮毂高度: String(entry['轮毂高度'] ?? ''),
      所属场站: String(entry['所属场站'] ?? ''),
      投运日期: String(entry['投运日期'] ?? ''),
      累计发电量: String(entry['累计发电量'] ?? ''),
      机组状态: String(entry['机组状态'] ?? entry.status ?? ''),
    }
    detailReadonly.value = entry.status === '已退役'
  } catch (error) {
    // 详情没拿到时保留列表里这一行的原值，不让表单变空。
    detailForm.value = Object.fromEntries(columns.map((field) => [field, String(row[field] ?? '')]))
    detailError.value = true
    detailMessage.value = error instanceof Error ? error.message : '机组详情读取失败'
  }
}

function closeDetail() {
  if (detailSaving.value) return
  detailVisible.value = false
}

async function saveDetail() {
  if (detailId.value === null) return
  detailMessage.value = ''
  detailError.value = false
  // 先记住旧值：保存失败时表单与列表都保留改动前的内容。
  const snapshot = { ...detailForm.value }
  if (!detailForm.value['机组机型'].trim() || !detailForm.value['轮毂高度'].trim()) {
    detailError.value = true
    detailMessage.value = '机组机型与轮毂高度不能为空，请补全后再保存'
    return
  }
  detailSaving.value = true
  try {
    const response = await request(`${ENDPOINT}/${detailId.value}`, {
      method: 'PUT',
      body: JSON.stringify({
        values: {
          机组机型: detailForm.value['机组机型'],
          轮毂高度: detailForm.value['轮毂高度'],
        },
      }),
    })
    if (!response.ok) {
      throw new Error('台账保存失败，请稍后重试')
    }
    const payload = await response.json()
    if (!payload.ok) {
      // 后端拒绝保存时，恢复旧值并给出可读说明。
      detailForm.value = snapshot
      detailError.value = true
      detailMessage.value = payload.message || '台账保存失败，请稍后重试'
      return
    }
    detailMessage.value = '台账已保存'
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    detailForm.value = snapshot
    detailError.value = true
    detailMessage.value = error instanceof Error ? error.message : '台账保存失败，请稍后重试'
  } finally {
    detailSaving.value = false
  }
}

onMounted(async () => {
  await reload()
  await loadStats()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

.modal-card {
  width: min(720px, 92vw);
  max-height: 86vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.25);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.modal-tip {
  margin: 0 0 12px;
  color: #b45309;
  font-size: 13px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 20px;
  margin: 0;
}

.detail-item dt {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.detail-item dd {
  margin: 0;
}

.detail-item input {
  width: 100%;
}

.modal-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.modal-spacer {
  flex: 1;
}

.muted-text {
  color: #94a3b8;
  font-size: 12px;
}

.success-text {
  color: #15803d;
  font-size: 13px;
}
</style>
