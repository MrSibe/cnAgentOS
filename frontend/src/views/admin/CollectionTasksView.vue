<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, getEnvelope, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { CollectionTaskDetail, CollectionTaskItem } from '@/types'
import { errorMessage, isUserCancelled, shortTime } from '@/utils/display'

const loading = ref(false)
const detailLoading = ref(false)
const tasks = ref<CollectionTaskItem[]>([])
const detail = ref<CollectionTaskDetail | null>(null)
const detailVisible = ref(false)
const filters = reactive({ status: '', started_from: '', started_to: '' })
const pagination = reactive({ page: 1, page_size: 20, total: 0 })

function buildQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(pagination.page))
  params.set('page_size', String(pagination.page_size))
  if (filters.status) params.set('status', filters.status)
  if (filters.started_from) params.set('started_from', filters.started_from)
  if (filters.started_to) params.set('started_to', filters.started_to)
  return params.toString() ? `?${params}` : ''
}

function applyPagination(meta?: { page?: number; page_size?: number; total?: number }): void {
  pagination.page = Number(meta?.page ?? pagination.page)
  pagination.page_size = Number(meta?.page_size ?? pagination.page_size)
  pagination.total = Number(meta?.total ?? tasks.value.length)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const payload = await getEnvelope<CollectionTaskItem[]>(`/api/v1/admin/collection-tasks${buildQuery()}`)
    tasks.value = payload.data
    applyPagination(payload.meta ?? payload)
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function openDetail(task: CollectionTaskItem): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await get<CollectionTaskDetail>(`/api/v1/admin/collection-tasks/${task.id}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function cancelTask(task: CollectionTaskItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认取消采集任务 ${task.id}？`, '取消任务', { type: 'warning' })
    await post<void>(`/api/v1/admin/collection-tasks/${task.id}/cancel`)
    ElMessage.success('已提交取消请求')
    await load()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

function search(): void {
  pagination.page = 1
  void load()
}

function changePage(page: number): void {
  pagination.page = page
  void load()
}

function changePageSize(pageSize: number): void {
  pagination.page = 1
  pagination.page_size = pageSize
  void load()
}

onMounted(load)
</script>

<template>
  <admin-page-header title="采集任务" description="查看手动采集任务的状态、来源级执行结果与脱敏失败摘要。">
    <el-select v-model="filters.status" clearable placeholder="状态" style="width: 170px">
      <el-option value="pending" label="pending" />
      <el-option value="running" label="running" />
      <el-option value="succeeded" label="succeeded" />
      <el-option value="partial_failed" label="partial_failed" />
      <el-option value="failed" label="failed" />
      <el-option value="cancelled" label="cancelled" />
    </el-select>
    <el-date-picker v-model="filters.started_from" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="开始时间" />
    <el-date-picker v-model="filters.started_to" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="结束时间" />
    <el-button @click="search">刷新</el-button>
  </admin-page-header>

  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="tasks">
      <el-table-column prop="id" label="任务 ID" min-width="260" show-overflow-tooltip />
      <el-table-column label="状态" width="140"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
      <el-table-column prop="source_count" label="来源数" width="90" />
      <el-table-column prop="item_success_count" label="成功内容" width="105" />
      <el-table-column prop="item_failure_count" label="失败数量" width="105" />
      <el-table-column label="创建时间" min-width="170"><template #default="{ row }">{{ shortTime(row.created_at) }}</template></el-table-column>
      <el-table-column label="完成时间" min-width="170"><template #default="{ row }">{{ shortTime(row.finished_at) }}</template></el-table-column>
      <el-table-column label="操作" fixed="right" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="danger" :disabled="!['pending', 'running'].includes(row.status)" @click="cancelTask(row)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      class="table-pagination"
      layout="total, sizes, prev, pager, next"
      :current-page="pagination.page"
      :page-size="pagination.page_size"
      :page-sizes="[10, 20, 50, 100]"
      :total="pagination.total"
      @current-change="changePage"
      @size-change="changePageSize"
    />
  </el-card>

  <el-drawer v-model="detailVisible" title="任务详情" size="560px">
    <el-skeleton v-if="detailLoading" :rows="6" animated />
    <template v-else-if="detail">
      <div class="detail-list">
        <p><strong>任务 ID</strong><span>{{ detail.id }}</span></p>
        <p><strong>状态</strong><span><status-tag :value="detail.status" /></span></p>
        <p><strong>成功 / 失败</strong><span>{{ detail.item_success_count }} / {{ detail.item_failure_count }}</span></p>
        <p><strong>失败摘要</strong><span>{{ detail.failure_summary || '-' }}</span></p>
        <p><strong>创建时间</strong><span>{{ shortTime(detail.created_at) }}</span></p>
      </div>
      <el-divider />
      <h3>来源执行结果</h3>
      <el-table :data="detail.sources || []" size="small">
        <el-table-column prop="source_name" label="来源" min-width="130" />
        <el-table-column prop="rule_name" label="规则" min-width="130" />
        <el-table-column label="状态" width="115"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column prop="failure_summary" label="失败摘要" min-width="160" />
      </el-table>
    </template>
  </el-drawer>
</template>
