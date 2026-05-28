<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post, postStream, put } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { ModelItem } from '@/types'
import { errorMessage, isUserCancelled, shortTime } from '@/utils/display'

const loading = ref(false)
const submitting = ref(false)
const items = ref<ModelItem[]>([])
const errorText = ref('')
const output = ref('')
const modelId = ref('model-main')
const editVisible = ref(false)
const selected = ref<ModelItem | null>(null)
const createForm = reactive({
  name: '',
  model_name: '',
  base_url: 'https://provider.example/v1',
  api_key: '',
  timeout_seconds: 60,
  description: '',
})
const editForm = reactive({
  name: '',
  model_name: '',
  base_url: '',
  api_key: '',
  timeout_seconds: 60,
  description: '',
})

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    items.value = await get<ModelItem[]>('/api/v1/admin/models')
  } catch (error) {
    errorText.value = errorMessage(error)
    ElMessage.warning(errorText.value)
  } finally {
    loading.value = false
  }
}

async function createModel(): Promise<void> {
  submitting.value = true
  try {
    await post<ModelItem>('/api/v1/admin/models', createForm)
    ElMessage.success('模型配置已创建')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openEdit(model: ModelItem): void {
  selected.value = model
  editForm.name = model.name
  editForm.model_name = model.model_name
  editForm.base_url = model.base_url
  editForm.api_key = ''
  editForm.timeout_seconds = model.timeout_seconds
  editForm.description = model.description ?? ''
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  submitting.value = true
  try {
    const body: Record<string, unknown> = {
      name: editForm.name,
      model_name: editForm.model_name,
      base_url: editForm.base_url,
      timeout_seconds: editForm.timeout_seconds,
      description: editForm.description || null,
    }
    if (editForm.api_key) body.api_key = editForm.api_key
    await patch<ModelItem>(`/api/v1/admin/models/${selected.value.id}`, body)
    editVisible.value = false
    ElMessage.success('模型配置已更新')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(model: ModelItem): Promise<void> {
  const status = model.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(`确认将模型 ${model.name} 改为 ${status}？`, '状态确认', { type: 'warning' })
    await patch<ModelItem>(`/api/v1/admin/models/${model.id}/status`, { status })
    ElMessage.success('模型状态已更新')
    await load()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

async function setDefault(model: ModelItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认将模型 ${model.name} 设为默认模型？`, '默认模型确认', { type: 'warning' })
    await put<ModelItem>(`/api/v1/admin/models/${model.id}/default`)
    ElMessage.success('已设为默认模型')
    await load()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

async function normalTest(): Promise<void> {
  output.value = ''
  try {
    const data = await post<{ reply: string; call_log_id: string; latency_ms: number; usage?: { total_tokens?: number } }>(
      `/api/v1/admin/models/${encodeURIComponent(modelId.value)}/connection-tests`,
      { message: '请回复连接正常', stream: false },
    )
    output.value = `${data.reply}\n\n调用记录：${data.call_log_id}\n耗时：${data.latency_ms}ms\nToken：${data.usage?.total_tokens ?? '-'}`
  } catch (error) {
    output.value = errorMessage(error)
  }
}

async function streamTest(): Promise<void> {
  output.value = ''
  try {
    await postStream(
      `/api/v1/admin/models/${encodeURIComponent(modelId.value)}/connection-tests/stream`,
      { message: '请回复连接正常' },
      ({ event, data }) => {
        if (event === 'delta') output.value += String(data.content ?? '')
        if (event === 'completed') output.value += `\n\n完成：${String(data.call_log_id ?? 'ok')}`
        if (event === 'error') output.value += `\n\n${String(data.message ?? '生成失败')}`
      },
    )
  } catch (error) {
    output.value = errorMessage(error)
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="模型配置" description="OpenAI 兼容模型、凭据掩码、连接测试与流式验证。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <el-alert v-if="errorText" :title="errorText" type="warning" show-icon :closable="false" />
  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <el-table v-loading="loading" :data="items">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="model_name" label="模型" min-width="150" />
        <el-table-column prop="base_url" label="服务地址" min-width="230" />
        <el-table-column prop="credential_mask" label="凭据" min-width="120" />
        <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column label="默认" width="90"><template #default="{ row }"><el-tag :type="row.is_default ? 'success' : 'info'" effect="plain">{{ row.is_default ? '默认' : '否' }}</el-tag></template></el-table-column>
        <el-table-column label="更新时间" min-width="170"><template #default="{ row }">{{ shortTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="230">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link @click="toggleStatus(row)">启停</el-button>
            <el-button link type="success" @click="setDefault(row)">设默认</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增模型</strong></template>
      <el-form label-position="top" :model="createForm">
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="模型名"><el-input v-model="createForm.model_name" /></el-form-item>
        <el-form-item label="Base URL"><el-input v-model="createForm.base_url" /></el-form-item>
        <el-form-item label="API Key"><el-input v-model="createForm.api_key" type="password" show-password /></el-form-item>
        <el-form-item label="超时秒数"><el-input-number v-model="createForm.timeout_seconds" :min="1" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="createForm.description" type="textarea" /></el-form-item>
        <el-button type="primary" :loading="submitting" @click="createModel">创建模型</el-button>
      </el-form>
    </el-card>
  </div>
  <el-card class="resource-card" shadow="never">
    <template #header><strong>模型测试</strong></template>
    <div class="test-toolbar">
      <el-input v-model="modelId" placeholder="模型 ID" />
      <el-button @click="normalTest">普通测试</el-button>
      <el-button type="primary" @click="streamTest">开始 SSE</el-button>
    </div>
    <pre class="stream-box">{{ output }}</pre>
  </el-card>
  <el-dialog v-model="editVisible" title="编辑模型" width="560px">
    <el-form label-position="top" :model="editForm">
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="模型名"><el-input v-model="editForm.model_name" /></el-form-item>
      <el-form-item label="Base URL"><el-input v-model="editForm.base_url" /></el-form-item>
      <el-form-item label="API Key（留空不更新）"><el-input v-model="editForm.api_key" type="password" show-password /></el-form-item>
      <el-form-item label="超时秒数"><el-input-number v-model="editForm.timeout_seconds" :min="1" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="editForm.description" type="textarea" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
    </template>
  </el-dialog>
</template>
