<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { ChatServerItem } from '@/types'
import { errorMessage } from '@/utils/display'

const loading = ref(false)
const servers = ref<ChatServerItem[]>([])
const createVisible = ref(false)
const editVisible = ref(false)
const selected = ref<ChatServerItem | null>(null)
const createForm = reactive({
  name: '', base_url: '', health_check_url: '',
  auth_token: '', priority: 0,
})
const editForm = reactive({
  name: '', base_url: '', health_check_url: '',
  auth_token: '', priority: 0,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    servers.value = await get<ChatServerItem[]>('/api/v1/admin/chat-servers?page_size=100')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function resetCreate(): void {
  Object.assign(createForm, { name: '', base_url: '', health_check_url: '', auth_token: '', priority: 0 })
}

async function createServer(): Promise<void> {
  try {
    await post('/api/v1/admin/chat-servers', createForm)
    createVisible.value = false
    resetCreate()
    ElMessage.success('服务器已创建')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function openEdit(server: ChatServerItem): void {
  selected.value = server
  Object.assign(editForm, {
    name: server.name, base_url: server.base_url,
    health_check_url: server.health_check_url || '',
    auth_token: '', priority: server.priority,
  })
  editVisible.value = true
}

async function updateServer(): Promise<void> {
  if (!selected.value) return
  try {
    await patch('/api/v1/admin/chat-servers/' + selected.value.id, editForm)
    editVisible.value = false
    ElMessage.success('服务器已更新')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function updateStatus(server: ChatServerItem, status: string): Promise<void> {
  try {
    await patch('/api/v1/admin/chat-servers/' + server.id + '/status', { status })
    ElMessage.success(status === 'active' ? '服务器已启用' : '服务器已禁用')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function runHealthCheck(server: ChatServerItem): Promise<void> {
  try {
    const result = await post<any>('/api/v1/admin/chat-servers/' + server.id + '/health-check', {})
    ElMessage.success('健康检查完成: ' + result.result + ' (' + result.latency_ms + 'ms)')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="服务器管理" description="管理聊天服务器配置和健康检查" />
  <el-card>
    <div style="margin-bottom: 16px">
      <el-button type="primary" @click="createVisible = true; resetCreate()">新增服务器</el-button>
    </div>
    <el-table v-loading="loading" :data="servers" stripe>
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="base_url" label="URL" min-width="250" />
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'unhealthy' ? 'danger' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="健康检查" width="180">
        <template #default="{ row }">
          <div v-if="row.last_health_check_result" style="font-size: 12px">
            <el-tag :type="row.last_health_check_result === 'passed' ? 'success' : 'danger'" size="small">{{ row.last_health_check_result }}</el-tag>
            <div style="color: #999; margin-top: 2px">{{ row.last_health_check_at }}</div>
          </div>
          <span v-else style="color: #999">未检查</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="runHealthCheck(row)">健康检查</el-button>
          <el-button size="small" :type="row.status === 'active' ? 'warning' : 'success'" @click="updateStatus(row, row.status === 'active' ? 'disabled' : 'active')">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="createVisible" title="新增服务器" width="500px">
    <el-form :model="createForm" label-width="100px">
      <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
      <el-form-item label="URL" required><el-input v-model="createForm.base_url" placeholder="https://example.com" /></el-form-item>
      <el-form-item label="健康检查 URL"><el-input v-model="createForm.health_check_url" placeholder="可选" /></el-form-item>
      <el-form-item label="认证令牌"><el-input v-model="createForm.auth_token" type="password" show-password /></el-form-item>
      <el-form-item label="优先级"><el-input-number v-model="createForm.priority" :min="0" /></el-form-item>
      <el-form-item><el-button type="primary" @click="createServer">创建</el-button></el-form-item>
    </el-form>
  </el-dialog>

  <el-dialog v-model="editVisible" title="编辑服务器" width="500px">
    <el-form :model="editForm" label-width="100px">
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="URL"><el-input v-model="editForm.base_url" /></el-form-item>
      <el-form-item label="健康检查 URL"><el-input v-model="editForm.health_check_url" /></el-form-item>
      <el-form-item label="新令牌"><el-input v-model="editForm.auth_token" type="password" show-password placeholder="留空不变" /></el-form-item>
      <el-form-item label="优先级"><el-input-number v-model="editForm.priority" :min="0" /></el-form-item>
      <el-form-item><el-button type="primary" @click="updateServer">保存</el-button></el-form-item>
    </el-form>
  </el-dialog>
</template>
