<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { ModelCallItem } from '@/types'
import { errorMessage, shortTime } from '@/utils/display'

const loading = ref(false)
const items = ref<ModelCallItem[]>([])
const errorText = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    items.value = await get<ModelCallItem[]>('/api/v1/admin/model-calls')
  } catch (error) {
    errorText.value = errorMessage(error)
    ElMessage.warning(errorText.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="调用记录" description="模型调用用途、状态、耗时与 token 统计。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <el-alert v-if="errorText" :title="errorText" type="warning" show-icon :closable="false" />
  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="items">
      <el-table-column label="模型" min-width="160">
        <template #default="{ row }">{{ row.model?.name ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="purpose" label="用途" min-width="140" />
      <el-table-column label="流式" width="90"><template #default="{ row }"><el-tag :type="row.streamed ? 'success' : 'info'" effect="plain">{{ row.streamed ? 'SSE' : '普通' }}</el-tag></template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
      <el-table-column label="Token" width="100"><template #default="{ row }">{{ row.total_tokens ?? '-' }}</template></el-table-column>
      <el-table-column label="耗时" width="110"><template #default="{ row }">{{ row.latency_ms ? `${row.latency_ms}ms` : '-' }}</template></el-table-column>
      <el-table-column label="开始时间" min-width="170"><template #default="{ row }">{{ shortTime(row.started_at) }}</template></el-table-column>
    </el-table>
  </el-card>
</template>
