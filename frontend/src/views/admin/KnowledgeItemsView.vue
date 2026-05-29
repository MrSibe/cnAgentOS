<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { get, getEnvelope, patch } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'
import type { KnowledgeItem, KnowledgeItemDetail, WatchSourceItem } from '@/types'
import { errorMessage, isUserCancelled, shortTime } from '@/utils/display'

const session = useSessionStore()
const loading = ref(false)
const detailLoading = ref(false)
const items = ref<KnowledgeItem[]>([])
const sources = ref<WatchSourceItem[]>([])
const detail = ref<KnowledgeItemDetail | null>(null)
const detailVisible = ref(false)
const filters = reactive({
  q: '',
  source_id: '',
  status: '',
  collected_from: '',
  collected_to: '',
})
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const canManageItems = computed(() => session.permissions.includes('data.items.manage'))

function buildQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(pagination.page))
  params.set('page_size', String(pagination.page_size))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.source_id) params.set('source_id', filters.source_id)
  if (filters.status) params.set('status', filters.status)
  if (filters.collected_from) params.set('collected_from', filters.collected_from)
  if (filters.collected_to) params.set('collected_to', filters.collected_to)
  return params.toString() ? `?${params}` : ''
}

async function loadSources(): Promise<void> {
  try {
    const loaded: WatchSourceItem[] = []
    let page = 1
    let total = 0
    do {
      const payload = await getEnvelope<WatchSourceItem[]>(`/api/v1/admin/watch-sources?page=${page}&page_size=100`)
      loaded.push(...payload.data)
      total = Number((payload.meta ?? payload).total ?? loaded.length)
      page += 1
    } while (loaded.length < total)
    sources.value = loaded
  } catch {
    sources.value = []
  }
}

function applyPagination(meta?: { page?: number; page_size?: number; total?: number }): void {
  pagination.page = Number(meta?.page ?? pagination.page)
  pagination.page_size = Number(meta?.page_size ?? pagination.page_size)
  pagination.total = Number(meta?.total ?? items.value.length)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const payload = await getEnvelope<KnowledgeItem[]>(`/api/v1/admin/knowledge-items${buildQuery()}`)
    items.value = payload.data
    applyPagination(payload.meta ?? payload)
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    loading.value = false
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

function sourceName(item: KnowledgeItem): string {
  return item.source_name || item.source_id
}

async function openDetail(item: KnowledgeItem): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await get<KnowledgeItemDetail>(`/api/v1/admin/knowledge-items/${item.id}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function changeStatus(item: KnowledgeItem, status: string): Promise<void> {
  if (!canManageItems.value) return
  try {
    await ElMessageBox.confirm(`确认将内容「${item.title || item.id}」标记为 ${status}？`, '治理状态确认', { type: 'warning' })
    await patch<KnowledgeItem>(`/api/v1/admin/knowledge-items/${item.id}/status`, { status })
    ElMessage.success('治理状态已更新')
    await load()
    if (detail.value?.id === item.id) detail.value = await get<KnowledgeItemDetail>(`/api/v1/admin/knowledge-items/${item.id}`)
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

function changeStatusFromCommand(item: KnowledgeItem, command: unknown): void {
  void changeStatus(item, String(command))
}

onMounted(async () => {
  await Promise.all([loadSources(), load()])
})
</script>

<template>
  <admin-page-header title="数据仓库" description="查看标准化入库内容、追踪来源，并治理进入问数检索范围的内容状态。">
    <el-input v-model="filters.q" class="toolbar-search" clearable placeholder="搜索标题或摘要" @keyup.enter="search" />
    <el-select v-model="filters.source_id" clearable filterable placeholder="来源" style="width: 180px"><el-option v-for="source in sources" :key="source.id" :value="source.id" :label="source.name" /></el-select>
    <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px"><el-option value="available" label="available" /><el-option value="excluded" label="excluded" /><el-option value="archived" label="archived" /></el-select>
    <el-button @click="search">刷新</el-button>
  </admin-page-header>

  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="items">
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
      <el-table-column label="来源" min-width="150"><template #default="{ row }">{{ sourceName(row) }}</template></el-table-column>
      <el-table-column label="状态" width="125"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
      <el-table-column label="采集时间" min-width="170"><template #default="{ row }">{{ shortTime(row.collected_at) }}</template></el-table-column>
      <el-table-column label="发布时间" min-width="170"><template #default="{ row }">{{ shortTime(row.published_at) }}</template></el-table-column>
      <el-table-column label="操作" fixed="right" width="235">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-dropdown trigger="click" :disabled="!canManageItems" @command="changeStatusFromCommand(row, $event)">
            <el-button link type="success" :disabled="!canManageItems">治理状态</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="available">available</el-dropdown-item>
                <el-dropdown-item command="excluded">excluded</el-dropdown-item>
                <el-dropdown-item command="archived">archived</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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

  <el-drawer v-model="detailVisible" title="内容详情" size="680px">
    <el-skeleton v-if="detailLoading" :rows="8" animated />
    <template v-else-if="detail">
      <div class="detail-list">
        <p><strong>标题</strong><span>{{ detail.title || '-' }}</span></p>
        <p><strong>状态</strong><span><status-tag :value="detail.status" /></span></p>
        <p><strong>来源</strong><span>{{ sourceName(detail) }}</span></p>
        <p><strong>原始链接</strong><span><a v-if="detail.canonical_url" :href="detail.canonical_url" target="_blank" rel="noreferrer">{{ detail.canonical_url }}</a><template v-else>-</template></span></p>
        <p><strong>外部标识</strong><span>{{ detail.external_key || '-' }}</span></p>
        <p><strong>治理时间</strong><span>{{ shortTime(detail.reviewed_at) }}</span></p>
      </div>
      <el-divider />
      <h3>摘要</h3>
      <p class="content-preview">{{ detail.summary || '-' }}</p>
      <h3>正文</h3>
      <pre class="content-box">{{ detail.content }}</pre>
      <div class="drawer-actions">
        <el-button :disabled="!canManageItems" @click="changeStatus(detail, 'available')">标记 available</el-button>
        <el-button :disabled="!canManageItems" @click="changeStatus(detail, 'excluded')">标记 excluded</el-button>
        <el-button :disabled="!canManageItems" @click="changeStatus(detail, 'archived')">标记 archived</el-button>
      </div>
    </template>
  </el-drawer>
</template>
