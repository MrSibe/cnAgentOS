<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { AuditLogItem } from '@/types'
import { errorMessage, shortTime } from '@/utils/display'

const loading = ref(false)
const items = ref<AuditLogItem[]>([])

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await get<AuditLogItem[]>('/api/v1/admin/audit-logs')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="审计日志" description="高风险动作的脱敏操作记录，不展示密码、会话或模型凭据。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="items">
      <el-table-column label="操作者" min-width="140"><template #default="{ row }">{{ row.actor?.display_name || '系统' }}</template></el-table-column>
      <el-table-column prop="action" label="动作" min-width="160" />
      <el-table-column prop="target_type" label="目标类型" min-width="120" />
      <el-table-column prop="target_id" label="目标 ID" min-width="200" />
      <el-table-column label="结果" width="110"><template #default="{ row }"><status-tag :value="row.result" /></template></el-table-column>
      <el-table-column label="发生时间" min-width="170"><template #default="{ row }">{{ shortTime(row.created_at) }}</template></el-table-column>
    </el-table>
  </el-card>
</template>
