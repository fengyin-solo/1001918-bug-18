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
          <td v-for="column in columns" :key="column">
            <button v-if="column === '机组编号'" class="link" type="button" @click="openDetail(Number(row.id))">
              {{ row[column] ?? '—' }}
            </button>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(Number(row.id))">查看详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              :disabled="busyId === row.id"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
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
      <span v-else-if="okMessage" class="ok-text">{{ okMessage }}</span>
    </footer>

    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <header class="modal-head">
          <h3>机组详情{{ detailForm.id ? `（记录 #${detailForm.id}）` : '' }}</h3>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </header>

        <div v-if="detailLoading" class="modal-tip">正在读取机组最新记录…</div>
        <div v-else class="modal-body">
          <div class="detail-readonly">
            <span>机组编号：<strong>{{ detailForm['机组编号'] ?? '—' }}</strong></span>
            <span>机组状态：<strong>{{ detailForm['机组状态'] ?? '—' }}</strong></span>
          </div>
          <label v-for="field in editableFields" :key="field" class="filter-item detail-field">
            <span>{{ field }}</span>
            <input v-model="detailForm[field]" :disabled="detailReadonly" :placeholder="`请输入${field}`" />
          </label>
          <p v-if="detailReadonly" class="modal-tip">机组已退役，台账已冻结，如需恢复请走重新启用流程。</p>
          <p v-if="detailError" class="error-text">{{ detailError }}</p>
        </div>

        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDetail">取消</button>
          <button
            class="btn primary"
            type="button"
            :disabled="detailLoading || detailReadonly || detailSaving"
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
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/turbine'
const columns = ["机组编号", "机组机型", "额定功率", "轮毂高度", "所属场站", "投运日期", "累计发电量", "机组状态"]
const actions = ["投运机组", "登记停机", "办理退役"]
const statuses = ["待投运", "运行中", "故障停机", "已退役"]
// 详情里可编辑的字段；机组编号是业务主键、机组状态只能靠动作流转，都不在此列
const editableFields = ["机组机型", "额定功率", "轮毂高度", "所属场站", "投运日期", "累计发电量"]
const RETIRED = "已退役"

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const okMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const busyId = ref<number | null>(null)

const stats = computed(() => [
  { label: "在运机组", value: rows.value.filter((row) => row["机组状态"] === "运行中").length },
  { label: "故障停机台数", value: rows.value.filter((row) => row["机组状态"] === "故障停机").length },
  { label: "已退役台数", value: rows.value.filter((row) => row["机组状态"] === RETIRED).length },
])

// 详情/编辑弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailSaving = ref(false)
const detailReadonly = ref(false)
const detailError = ref('')
const detailForm = ref<Row>({})

function resetFilters() {
  filters.value = {}
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
  okMessage.value = ''
  busyId.value = Number(row.id)
  try {
    // 后端动作统一收在 values.action 里；业务失败也会返回 200，需要再看 ok 字段
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload) {
      throw new Error('风电机组动作未生效，请稍后重试')
    }
    if (!payload.ok) {
      // 没落库：列表保持原内容，只给出后端的可读说明
      throw new Error(payload.message || '风电机组动作未生效，原状态已保留')
    }
    okMessage.value = payload.message || '操作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '风电机组操作失败'
  } finally {
    busyId.value = null
  }
}

async function openDetail(id: number) {
  detailVisible.value = true
  detailLoading.value = true
  detailReadonly.value = false
  detailError.value = ''
  detailForm.value = {}
  try {
    // 详情与列表取的是同一条服务端记录，退出再进来看到的就是最新值
    const response = await request(`${ENDPOINT}/${id}`)
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload) {
      throw new Error(response.status === 404 ? '该机组不存在或已归档' : '机组详情读取失败')
    }
    detailForm.value = { ...payload }
    detailReadonly.value = payload["机组状态"] === RETIRED
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '机组详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detailError.value = ''
  detailForm.value = {}
}

async function saveDetail() {
  if (!detailForm.value.id) {
    return
  }
  detailError.value = ''
  detailSaving.value = true
  const values: Record<string, string | number | null> = {}
  for (const field of editableFields) {
    values[field] = detailForm.value[field] ?? ''
  }
  try {
    const response = await request(`${ENDPOINT}/${detailForm.value.id}`, {
      method: 'PUT',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload) {
      throw new Error('台账保存失败，原内容已保留，请稍后重试')
    }
    if (!payload.ok) {
      // 保存被后端拒绝：表单原样留住，给出可读原因
      throw new Error(payload.message || '台账保存失败，原内容已保留')
    }
    closeDetail()
    okMessage.value = payload.message || '机组台账已保存'
    await reload()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '台账保存失败'
  } finally {
    detailSaving.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
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

onMounted(reload)
</script>
