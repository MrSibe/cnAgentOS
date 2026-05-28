<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, post, postStream } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { ModelItem } from '@/types'
import { errorMessage, shortTime } from '@/utils/display'

const loading = ref(false)
const submitting = ref(false)
const items = ref<ModelItem[]>([])
const errorText = ref('')
const output = ref('')
const modelId = ref('model-main')
const createForm = reactive({
  name: '',
  model_name: '',
  base_url: 'https://provider.example/v1',
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
</template>
