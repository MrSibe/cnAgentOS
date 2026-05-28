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
const testing = ref(false)
const testDone = ref(false)
const createVisible = ref(false)
const editVisible = ref(false)
const testVisible = ref(false)
const selected = ref<ModelItem | null>(null)
const testingModel = ref<ModelItem | null>(null)
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

function resetCreateForm(): void {
  Object.assign(createForm, {
    name: '', model_name: '', base_url: 'https://provider.example/v1', api_key: '',
    timeout_seconds: 60, description: '',
  })
}

async function createModel(): Promise<void> {
  submitting.value = true
  try {
    await post<ModelItem>('/api/v1/admin/models', createForm)
    resetCreateForm()
    createVisible.value = false
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

function openTest(model: ModelItem): void {
  testingModel.value = model
  output.value = ''
  testing.value = false
  testDone.value = false
  testVisible.value = true
}

async function normalTest(): Promise<void> {
  if (!testingModel.value) return
  output.value = '测试中，请稍候...'
  testing.value = true
  testDone.value = false
  try {
    const data = await post<{ reply: string; call_log_id: string; latency_ms: number; usage?: { total_tokens?: number } }>(
      `/api/v1/admin/models/${encodeURIComponent(testingModel.value.id)}/connection-tests`,
      { message: '请回复连接正常', stream: false },
    )
    output.value = `回复：${data.reply}\n\n调用记录：${data.call_log_id}\n耗时：${data.latency_ms}ms\nToken：${data.usage?.total_tokens ?? '-'}`
    testDone.value = true
  } catch (error) {
    output.value = errorMessage(error)
  } finally {
    testing.value = false
  }
}

async function streamTest(): Promise<void> {
  if (!testingModel.value) return
  output.value = '等待流式响应...\n'
  testing.value = true
  testDone.value = false
  try {
    await postStream(
      `/api/v1/admin/models/${encodeURIComponent(testingModel.value.id)}/connection-tests/stream`,
      { message: '请回复连接正常' },
      ({ event, data }) => {
        if (event === 'delta') {
          if (output.value === '等待流式响应...\n') output.value = ''
          const choices = data.choices as Array<{ delta: { content?: string } }> | undefined
          const content = choices?.[0]?.delta?.content
          if (content) output.value += content
        }
        if (event === 'completed') {
          output.value += `\n\n━━━━━━ 流式测试完成 ━━━━━━\n调用记录：${String(data.call_log_id ?? 'ok')}`
          testDone.value = true
          testing.value = false
        }
        if (event === 'error') {
          const streamError = data.error as { message?: string } | undefined
          output.value += `\n\n错误：${String(streamError?.message ?? data.message ?? '生成失败')}`
          testDone.value = true
          testing.value = false
        }
      },
    )
  } catch (error) {
    output.value = errorMessage(error)
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="模型配置" description="OpenAI 兼容模型、凭据掩码、连接测试与流式验证。">
    <el-button type="primary" @click="createVisible = true">新增模型</el-button>
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <el-alert v-if="errorText" :title="errorText" type="warning" show-icon :closable="false" />
  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="items">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="model_name" label="模型" min-width="150" />
      <el-table-column prop="base_url" label="服务地址" min-width="230" />
      <el-table-column prop="credential_mask" label="凭据" min-width="120" />
      <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
      <el-table-column label="默认" width="90"><template #default="{ row }"><el-tag :type="row.is_default ? 'success' : 'info'" effect="plain">{{ row.is_default ? '默认' : '否' }}</el-tag></template></el-table-column>
      <el-table-column label="更新时间" min-width="170"><template #default="{ row }">{{ shortTime(row.updated_at) }}</template></el-table-column>
      <el-table-column label="操作" fixed="right" width="290">
        <template #default="{ row }">
          <el-button link type="primary" @click="openTest(row)">测试</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link @click="toggleStatus(row)">启停</el-button>
          <el-button link type="success" @click="setDefault(row)">设默认</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
  <el-dialog v-model="createVisible" title="新增模型" width="560px" @close="resetCreateForm">
    <el-form label-position="top" :model="createForm">
      <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
      <el-form-item label="模型名"><el-input v-model="createForm.model_name" /></el-form-item>
      <el-form-item label="Base URL"><el-input v-model="createForm.base_url" /></el-form-item>
      <el-form-item label="API Key"><el-input v-model="createForm.api_key" type="password" show-password /></el-form-item>
      <el-form-item label="超时秒数"><el-input-number v-model="createForm.timeout_seconds" :min="1" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="createForm.description" type="textarea" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="createModel">创建模型</el-button></template>
  </el-dialog>
  <el-dialog v-model="testVisible" :title="`模型测试 — ${testingModel?.name ?? ''}`" width="640px">
    <p class="test-model-info">模型：{{ testingModel?.model_name }}　地址：{{ testingModel?.base_url }}</p>
    <div class="test-toolbar">
      <el-button :loading="testing" :disabled="testing" @click="normalTest">普通测试</el-button>
      <el-button type="primary" :loading="testing" :disabled="testing" @click="streamTest">流式测试</el-button>
    </div>
    <el-alert v-if="testing" title="测试执行中，请等待完成" type="info" show-icon :closable="false" class="test-status" />
    <el-alert v-if="testDone" title="测试已完成" type="success" show-icon :closable="false" class="test-status" />
    <pre class="stream-box">{{ output }}</pre>
  </el-dialog>
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
