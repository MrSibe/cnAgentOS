<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { ToolItem } from '@/types'
import { errorMessage } from '@/utils/display'

const loading = ref(false)
const tools = ref<ToolItem[]>([])
const createVisible = ref(false)
const editVisible = ref(false)
const selected = ref<ToolItem | null>(null)
const createForm = reactive({
  code: '', name: '', description: '', tool_type: 'builtin_function',
  config: '{}', sensitive_config: '', invocation_limit: 100,
  invocation_window_seconds: 3600,
})
const editForm = reactive({
  name: '', description: '', config: '{}', sensitive_config: '',
  invocation_limit: 100, invocation_window_seconds: 3600,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    tools.value = await get<ToolItem[]>('/api/v1/admin/tools?page_size=100')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function resetCreate(): void {
  Object.assign(createForm, {
    code: '', name: '', description: '', tool_type: 'builtin_function',
    config: '{}', sensitive_config: '', invocation_limit: 100,
    invocation_window_seconds: 3600,
  })
}

async function createTool(): Promise<void> {
  try {
    let config = {}
    try { config = JSON.parse(createForm.config) } catch { config = {} }
    await post('/api/v1/admin/tools', { ...createForm, config })
    createVisible.value = false
    resetCreate()
    ElMessage.success('工具已创建')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function openEdit(tool: ToolItem): void {
  selected.value = tool
  Object.assign(editForm, {
    name: tool.name, description: tool.description || '',
    config: JSON.stringify(tool.config, null, 2),
    sensitive_config: '', invocation_limit: tool.invocation_limit,
    invocation_window_seconds: tool.invocation_window_seconds,
  })
  editVisible.value = true
}

async function updateTool(): Promise<void> {
  if (!selected.value) return
  try {
    let config = {}
    try { config = JSON.parse(editForm.config) } catch { config = {} }
    await patch('/api/v1/admin/tools/' + selected.value.id, { ...editForm, config })
    editVisible.value = false
    ElMessage.success('工具已更新')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function updateStatus(tool: ToolItem, status: string): Promise<void> {
  try {
    await patch('/api/v1/admin/tools/' + tool.id + '/status', { status })
    ElMessage.success(status === 'active' ? '工具已启用' : '工具已禁用')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="工具管理" description="注册和管理系统工具" />
  <el-card>
    <div style="margin-bottom: 16px">
      <el-button type="primary" @click="createVisible = true; resetCreate()">注册工具</el-button>
    </div>
    <el-table v-loading="loading" :data="tools" stripe>
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="code" label="代码" width="120" />
      <el-table-column prop="tool_type" label="类型" width="120" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="限流" width="110">
        <template #default="{ row }">{{ row.invocation_limit }}/{{ row.invocation_window_seconds }}s</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" :type="row.status === 'active' ? 'warning' : 'success'" @click="updateStatus(row, row.status === 'active' ? 'disabled' : 'active')">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="createVisible" title="注册工具" width="600px">
    <el-form :model="createForm" label-width="140px">
      <el-form-item label="代码" required><el-input v-model="createForm.code" placeholder="如 weather_query" /></el-form-item>
      <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="createForm.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="类型">
        <el-select v-model="createForm.tool_type" style="width: 100%">
          <el-option value="builtin_function" label="内置函数" />
          <el-option value="api_call" label="API 调用" />
          <el-option value="web_search" label="网络搜索" />
        </el-select>
      </el-form-item>
      <el-form-item label="配置 (JSON)">
        <el-input v-model="createForm.config" type="textarea" :rows="4" placeholder='{"api_url":"https://..."}' />
      </el-form-item>
      <el-form-item label="敏感配置"><el-input v-model="createForm.sensitive_config" type="password" show-password placeholder="可选" /></el-form-item>
      <el-form-item label="限流次数"><el-input-number v-model="createForm.invocation_limit" :min="1" /></el-form-item>
      <el-form-item label="限流窗口(秒)"><el-input-number v-model="createForm.invocation_window_seconds" :min="1" /></el-form-item>
      <el-form-item><el-button type="primary" @click="createTool">创建</el-button></el-form-item>
    </el-form>
  </el-dialog>

  <el-dialog v-model="editVisible" title="编辑工具" width="600px">
    <el-form :model="editForm" label-width="140px">
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="editForm.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="配置 (JSON)"><el-input v-model="editForm.config" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="新敏感配置"><el-input v-model="editForm.sensitive_config" type="password" show-password placeholder="留空不变" /></el-form-item>
      <el-form-item label="限流次数"><el-input-number v-model="editForm.invocation_limit" :min="1" /></el-form-item>
      <el-form-item label="限流窗口(秒)"><el-input-number v-model="editForm.invocation_window_seconds" :min="1" /></el-form-item>
      <el-form-item><el-button type="primary" @click="updateTool">保存</el-button></el-form-item>
    </el-form>
  </el-dialog>
</template>
