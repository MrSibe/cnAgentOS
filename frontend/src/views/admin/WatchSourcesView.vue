<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { getEnvelope, patch, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'
import type { WatchRuleItem, WatchSourceItem } from '@/types'
import { errorMessage, isUserCancelled, shortTime } from '@/utils/display'

const session = useSessionStore()
const loading = ref(false)
const ruleLoading = ref(false)
const submitting = ref(false)
const sources = ref<WatchSourceItem[]>([])
const rules = ref<WatchRuleItem[]>([])
const selectedSource = ref<WatchSourceItem | null>(null)
const editingSource = ref<WatchSourceItem | null>(null)
const selectedRule = ref<WatchRuleItem | null>(null)
const editSourceVisible = ref(false)
const editRuleVisible = ref(false)
const taskVisible = ref(false)
const sourceQuery = reactive({ q: '', status: '', source_type: '' })
const sourcePagination = reactive({ page: 1, page_size: 20, total: 0 })
const rulePagination = reactive({ page: 1, page_size: 20, total: 0 })
const emptySourceForm = () => ({
  name: '',
  source_type: 'web_page',
  entry_url: '',
  allowed_hosts_text: '',
  auth_config_text: '',
  description: '',
})
const emptyRuleForm = () => ({
  name: '',
  request_method: 'GET',
  request_headers_text: '{\n  "Accept": "text/html"\n}',
  request_params_text: '{}',
  extractor_type: 'html',
  extractor_config_text: '{\n  "item_selector": ".item",\n  "title_selector": ".title",\n  "content_selector": ".content"\n}',
})
const sourceForm = reactive(emptySourceForm())
const sourceEditForm = reactive(emptySourceForm())
const ruleForm = reactive(emptyRuleForm())
const ruleEditForm = reactive({ ...emptyRuleForm(), status: 'disabled' })
const taskForm = reactive({ variables_text: '{}' })

const canCreateRule = computed(() => Boolean(selectedSource.value))
const canRunTask = computed(() => session.permissions.includes('watch.tasks.run'))

function buildQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(sourcePagination.page))
  params.set('page_size', String(sourcePagination.page_size))
  if (sourceQuery.q.trim()) params.set('q', sourceQuery.q.trim())
  if (sourceQuery.status) params.set('status', sourceQuery.status)
  if (sourceQuery.source_type) params.set('source_type', sourceQuery.source_type)
  return params.toString() ? `?${params}` : ''
}

function buildRuleQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(rulePagination.page))
  params.set('page_size', String(rulePagination.page_size))
  return `?${params}`
}

function applySourcePagination(meta?: { page?: number; page_size?: number; total?: number }): void {
  sourcePagination.page = Number(meta?.page ?? sourcePagination.page)
  sourcePagination.page_size = Number(meta?.page_size ?? sourcePagination.page_size)
  sourcePagination.total = Number(meta?.total ?? sources.value.length)
}

function applyRulePagination(meta?: { page?: number; page_size?: number; total?: number }): void {
  rulePagination.page = Number(meta?.page ?? rulePagination.page)
  rulePagination.page_size = Number(meta?.page_size ?? rulePagination.page_size)
  rulePagination.total = Number(meta?.total ?? rules.value.length)
}

async function loadSources(): Promise<void> {
  loading.value = true
  try {
    const payload = await getEnvelope<WatchSourceItem[]>(`/api/v1/admin/watch-sources${buildQuery()}`)
    sources.value = payload.data
    applySourcePagination(payload.meta ?? payload)
    if (selectedSource.value) {
      selectedSource.value = sources.value.find((item) => item.id === selectedSource.value?.id) ?? null
      if (!selectedSource.value) {
        rules.value = []
        rulePagination.total = 0
      }
    }
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function searchSources(): void {
  sourcePagination.page = 1
  void loadSources()
}

function changeSourcePage(page: number): void {
  sourcePagination.page = page
  void loadSources()
}

function changeSourcePageSize(pageSize: number): void {
  sourcePagination.page = 1
  sourcePagination.page_size = pageSize
  void loadSources()
}

async function selectSource(source?: WatchSourceItem | null): Promise<void> {
  if (!source) {
    selectedSource.value = null
    rules.value = []
    rulePagination.total = 0
    return
  }
  selectedSource.value = source
  rulePagination.page = 1
  await loadRules()
}

async function loadRules(): Promise<void> {
  if (!selectedSource.value) return
  ruleLoading.value = true
  try {
    const payload = await getEnvelope<WatchRuleItem[]>(`/api/v1/admin/watch-sources/${selectedSource.value.id}/rules${buildRuleQuery()}`)
    rules.value = payload.data
    applyRulePagination(payload.meta ?? payload)
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    ruleLoading.value = false
  }
}

function changeRulePage(page: number): void {
  rulePagination.page = page
  void loadRules()
}

function changeRulePageSize(pageSize: number): void {
  rulePagination.page = 1
  rulePagination.page_size = pageSize
  void loadRules()
}

function parseJsonObject(value: string, field: string): Record<string, unknown> | null {
  if (!value.trim()) return null
  const parsed = JSON.parse(value) as unknown
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error(`${field} 必须是 JSON 对象`)
  return parsed as Record<string, unknown>
}

function parseHosts(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function jsonText(value?: Record<string, unknown> | null): string {
  return JSON.stringify(value ?? {}, null, 2)
}

function sourcePayload(form: ReturnType<typeof emptySourceForm>): Record<string, unknown> {
  const body: Record<string, unknown> = {
    name: form.name,
    source_type: form.source_type,
    entry_url: form.entry_url,
    allowed_hosts: parseHosts(form.allowed_hosts_text),
    description: form.description || null,
  }
  if (form.auth_config_text.trim()) {
    body.auth_config = parseJsonObject(form.auth_config_text, '认证配置') ?? {}
  }
  return body
}

function rulePayload(form: ReturnType<typeof emptyRuleForm> | typeof ruleEditForm): Record<string, unknown> {
  const body: Record<string, unknown> = {
    name: form.name,
    request_method: form.request_method,
    request_headers: parseJsonObject(form.request_headers_text, '请求头') ?? {},
    request_params: parseJsonObject(form.request_params_text, '请求参数') ?? {},
    extractor_type: form.extractor_type,
    extractor_config: parseJsonObject(form.extractor_config_text, '解析配置') ?? {},
  }
  if ('status' in form) body.status = form.status
  return body
}

async function createSource(): Promise<void> {
  submitting.value = true
  try {
    await post<WatchSourceItem>('/api/v1/admin/watch-sources', sourcePayload(sourceForm))
    Object.assign(sourceForm, emptySourceForm())
    ElMessage.success('数据源已创建')
    await loadSources()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openSourceEdit(source: WatchSourceItem): void {
  editingSource.value = source
  Object.assign(sourceEditForm, {
    name: source.name,
    source_type: source.source_type,
    entry_url: source.entry_url,
    allowed_hosts_text: source.allowed_hosts.join('\n'),
    auth_config_text: '',
    description: source.description ?? '',
  })
  editSourceVisible.value = true
}

function closeSourceEdit(): void {
  editSourceVisible.value = false
  editingSource.value = null
}

async function saveSource(): Promise<void> {
  if (!editingSource.value) return
  submitting.value = true
  try {
    await patch<WatchSourceItem>(`/api/v1/admin/watch-sources/${editingSource.value.id}`, sourcePayload(sourceEditForm))
    closeSourceEdit()
    ElMessage.success('数据源已更新')
    await loadSources()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function toggleSource(source: WatchSourceItem): Promise<void> {
  const status = source.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(`确认将数据源 ${source.name} 改为 ${status}？`, '状态确认', { type: 'warning' })
    await patch<WatchSourceItem>(`/api/v1/admin/watch-sources/${source.id}/status`, { status })
    ElMessage.success('数据源状态已更新')
    await loadSources()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

async function createRule(): Promise<void> {
  if (!selectedSource.value) return
  submitting.value = true
  try {
    await post<WatchRuleItem>(`/api/v1/admin/watch-sources/${selectedSource.value.id}/rules`, rulePayload(ruleForm))
    Object.assign(ruleForm, emptyRuleForm())
    ElMessage.success('采集规则已创建')
    await loadRules()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openRuleEdit(rule: WatchRuleItem): void {
  selectedRule.value = rule
  Object.assign(ruleEditForm, {
    name: rule.name,
    request_method: rule.request_method,
    request_headers_text: jsonText(rule.request_headers),
    request_params_text: jsonText(rule.request_params),
    extractor_type: rule.extractor_type,
    extractor_config_text: jsonText(rule.extractor_config),
    status: rule.status,
  })
  editRuleVisible.value = true
}

async function saveRule(): Promise<void> {
  if (!selectedRule.value) return
  submitting.value = true
  try {
    await patch<WatchRuleItem>(`/api/v1/admin/watch-rules/${selectedRule.value.id}`, rulePayload(ruleEditForm))
    editRuleVisible.value = false
    ElMessage.success('采集规则已更新')
    await loadRules()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openTask(rule: WatchRuleItem): void {
  if (!canRunTask.value) return
  selectedRule.value = rule
  taskForm.variables_text = '{}'
  taskVisible.value = true
}

async function runTask(): Promise<void> {
  if (!selectedSource.value || !selectedRule.value || !canRunTask.value) return
  submitting.value = true
  try {
    const variables = parseJsonObject(taskForm.variables_text, '任务变量') ?? {}
    const task = await post<{ id: string; status: string; created_at: string }>('/api/v1/admin/collection-tasks', {
      targets: [{ source_id: selectedSource.value.id, rule_id: selectedRule.value.id, variables }],
    })
    taskVisible.value = false
    ElMessage.success(`采集任务已创建：${task.id}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(loadSources)
</script>

<template>
  <admin-page-header title="数据源与规则" description="配置受安全边界约束的数据源、解析规则，并发起手动采集任务。">
    <el-input v-model="sourceQuery.q" class="toolbar-search" clearable placeholder="搜索数据源" @keyup.enter="searchSources" />
    <el-select v-model="sourceQuery.status" clearable placeholder="状态" style="width: 130px"><el-option value="active" label="active" /><el-option value="disabled" label="disabled" /></el-select>
    <el-select v-model="sourceQuery.source_type" clearable placeholder="类型" style="width: 140px"><el-option value="web_page" label="web_page" /><el-option value="web_api" label="web_api" /></el-select>
    <el-button @click="searchSources">刷新</el-button>
  </admin-page-header>

  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <template #header><strong>数据源</strong></template>
      <el-table v-loading="loading" :data="sources" highlight-current-row @current-change="selectSource">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="source_type" label="类型" width="105" />
        <el-table-column prop="entry_url" label="入口 URL" min-width="260" show-overflow-tooltip />
        <el-table-column label="白名单主机" min-width="180"><template #default="{ row }"><el-tag v-for="host in row.allowed_hosts" :key="host" class="value-tag" effect="plain">{{ host }}</el-tag></template></el-table-column>
        <el-table-column label="认证" width="120"><template #default="{ row }">{{ row.auth_configured ? row.auth_mask || '已配置' : '未配置' }}</template></el-table-column>
        <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column label="更新时间" min-width="160"><template #default="{ row }">{{ shortTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="150"><template #default="{ row }"><el-button link type="primary" @click.stop="openSourceEdit(row)">编辑</el-button><el-button link @click.stop="toggleSource(row)">启停</el-button></template></el-table-column>
      </el-table>
      <el-pagination
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :current-page="sourcePagination.page"
        :page-size="sourcePagination.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="sourcePagination.total"
        @current-change="changeSourcePage"
        @size-change="changeSourcePageSize"
      />
    </el-card>

    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增数据源</strong></template>
      <el-form label-position="top" :model="sourceForm">
        <el-form-item label="名称"><el-input v-model="sourceForm.name" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="sourceForm.source_type"><el-option value="web_page" label="web_page" /><el-option value="web_api" label="web_api" /></el-select></el-form-item>
        <el-form-item label="入口 URL"><el-input v-model="sourceForm.entry_url" /></el-form-item>
        <el-form-item label="允许主机"><el-input v-model="sourceForm.allowed_hosts_text" type="textarea" :rows="3" placeholder="每行或逗号分隔一个 host" /></el-form-item>
        <el-form-item label="认证配置 JSON"><el-input v-model="sourceForm.auth_config_text" type="textarea" :rows="4" placeholder='{"headers":{"Authorization":"Bearer test"}}' /></el-form-item>
        <el-form-item label="说明"><el-input v-model="sourceForm.description" type="textarea" /></el-form-item>
        <el-button type="primary" :loading="submitting" @click="createSource">创建数据源</el-button>
      </el-form>
    </el-card>
  </div>

  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <template #header><strong>采集规则 {{ selectedSource ? `· ${selectedSource.name}` : '' }}</strong></template>
      <el-empty v-if="!selectedSource" description="选择一个数据源后查看规则" />
      <el-table v-else v-loading="ruleLoading" :data="rules">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="request_method" label="方法" width="80" />
        <el-table-column prop="extractor_type" label="解析" width="90" />
        <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column label="更新时间" min-width="160"><template #default="{ row }">{{ shortTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="170"><template #default="{ row }"><el-button link type="primary" @click="openRuleEdit(row)">编辑</el-button><el-button link type="success" :disabled="!canRunTask" @click="openTask(row)">运行</el-button></template></el-table-column>
      </el-table>
      <el-pagination
        v-if="selectedSource"
        class="table-pagination"
        layout="total, sizes, prev, pager, next"
        :current-page="rulePagination.page"
        :page-size="rulePagination.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="rulePagination.total"
        @current-change="changeRulePage"
        @size-change="changeRulePageSize"
      />
    </el-card>

    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增规则</strong></template>
      <el-form label-position="top" :model="ruleForm">
        <el-form-item label="名称"><el-input v-model="ruleForm.name" :disabled="!canCreateRule" /></el-form-item>
        <el-form-item label="请求方法"><el-select v-model="ruleForm.request_method" :disabled="!canCreateRule"><el-option value="GET" label="GET" /><el-option value="POST" label="POST" /></el-select></el-form-item>
        <el-form-item label="请求头 JSON"><el-input v-model="ruleForm.request_headers_text" type="textarea" :rows="4" :disabled="!canCreateRule" /></el-form-item>
        <el-form-item label="请求参数 JSON"><el-input v-model="ruleForm.request_params_text" type="textarea" :rows="4" :disabled="!canCreateRule" /></el-form-item>
        <el-form-item label="解析类型"><el-select v-model="ruleForm.extractor_type" :disabled="!canCreateRule"><el-option value="html" label="html" /><el-option value="json" label="json" /></el-select></el-form-item>
        <el-form-item label="解析配置 JSON"><el-input v-model="ruleForm.extractor_config_text" type="textarea" :rows="6" :disabled="!canCreateRule" /></el-form-item>
        <el-button type="primary" :loading="submitting" :disabled="!canCreateRule" @click="createRule">创建规则</el-button>
      </el-form>
    </el-card>
  </div>

  <el-dialog v-model="editSourceVisible" title="编辑数据源" width="640px" @closed="closeSourceEdit">
    <el-form label-position="top" :model="sourceEditForm">
      <el-form-item label="名称"><el-input v-model="sourceEditForm.name" /></el-form-item>
      <el-form-item label="类型"><el-input v-model="sourceEditForm.source_type" disabled /></el-form-item>
      <el-form-item label="入口 URL"><el-input v-model="sourceEditForm.entry_url" /></el-form-item>
      <el-form-item label="允许主机"><el-input v-model="sourceEditForm.allowed_hosts_text" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="认证配置 JSON（留空保留旧值）"><el-input v-model="sourceEditForm.auth_config_text" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="sourceEditForm.description" type="textarea" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="closeSourceEdit">取消</el-button><el-button type="primary" :loading="submitting" @click="saveSource">保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="editRuleVisible" title="编辑规则" width="680px">
    <el-form label-position="top" :model="ruleEditForm">
      <el-form-item label="名称"><el-input v-model="ruleEditForm.name" /></el-form-item>
      <el-form-item label="请求方法"><el-select v-model="ruleEditForm.request_method"><el-option value="GET" label="GET" /><el-option value="POST" label="POST" /></el-select></el-form-item>
      <el-form-item label="状态"><el-select v-model="ruleEditForm.status"><el-option value="active" label="active" /><el-option value="disabled" label="disabled" /></el-select></el-form-item>
      <el-form-item label="请求头 JSON"><el-input v-model="ruleEditForm.request_headers_text" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="请求参数 JSON"><el-input v-model="ruleEditForm.request_params_text" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="解析类型"><el-select v-model="ruleEditForm.extractor_type"><el-option value="html" label="html" /><el-option value="json" label="json" /></el-select></el-form-item>
      <el-form-item label="解析配置 JSON"><el-input v-model="ruleEditForm.extractor_config_text" type="textarea" :rows="6" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="editRuleVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="saveRule">保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="taskVisible" title="运行采集任务" width="560px">
    <p class="dialog-hint">将使用 {{ selectedSource?.name }} / {{ selectedRule?.name }} 创建手动采集任务。</p>
    <el-input v-model="taskForm.variables_text" type="textarea" :rows="6" />
    <template #footer><el-button @click="taskVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="runTask">发起任务</el-button></template>
  </el-dialog>
</template>
