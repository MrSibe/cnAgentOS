<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getEnvelope, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import type { SentimentTaskItem, SentimentTaskDetail, SentimentReportItem } from '@/types'
import { errorMessage, statusLabel, statusType } from '@/utils/display'

const loading = ref(false)
const tasks = ref<SentimentTaskItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// Create dialog
const createVisible = ref(false)
const createLoading = ref(false)
const createForm = ref({
  name: '',
  scope: 'data_warehouse',
  date_start: '',
  date_end: '',
})

// Detail drawer
const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedTask = ref<SentimentTaskDetail | null>(null)
const selectedReport = ref<SentimentReportItem | null>(null)

function scopeLabel(s: string): string {
  return s === 'chat' ? '聊天分析' : '数据仓库分析'
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const envelope = await getEnvelope<SentimentTaskItem[]>('/api/v1/admin/sentiment/tasks?' + params)
    tasks.value = envelope.data
    total.value = envelope.meta?.total ?? 0
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function openCreate(): Promise<void> {
  createForm.value = { name: '', scope: 'data_warehouse', date_start: '', date_end: '' }
  createVisible.value = true
}

async function submitCreate(): Promise<void> {
  if (!createForm.value.name) {
    ElMessage.warning('请输入任务名称')
    return
  }
  createLoading.value = true
  try {
    const payload: Record<string, unknown> = {
      name: createForm.value.name,
      scope: createForm.value.scope,
    }
    if (createForm.value.date_start || createForm.value.date_end) {
      const scope: Record<string, string> = {}
      if (createForm.value.date_start) scope.start_date = createForm.value.date_start
      if (createForm.value.date_end) scope.end_date = createForm.value.date_end
      payload.data_scope = scope
    }
    createVisible.value = false
    await load()
    await post('/api/v1/admin/sentiment/tasks', payload)
    ElMessage.success('任务已创建并开始分析')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    createLoading.value = false
  }
}

async function openDetail(task: SentimentTaskItem): Promise<void> {
  detailLoading.value = true
  detailVisible.value = true
  try {
    const detail = await getEnvelope<SentimentTaskDetail>('/api/v1/admin/sentiment/tasks/' + task.id)
    selectedTask.value = detail.data
    // Get the first (and only) report
    const reports = detail.data.reports || []
    selectedReport.value = reports.length > 0 ? reports[0] : null
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="舆情分析" description="分析聊天记录或数据仓库内容，自动生成综合风险评估报告" />

  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>分析任务</span>
        <el-button type="primary" @click="openCreate">创建任务</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="tasks" empty-text="暂无分析任务">
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column label="分析范围" width="130">
        <template #default="{ row }">{{ scopeLabel(row.scope) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="100">
        <template #default="{ row }">
          <el-progress :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : undefined" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div style="display: flex; justify-content: center; margin-top: 16px">
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>

  <!-- Create Task Dialog -->
  <el-dialog v-model="createVisible" title="创建分析任务" width="500px">
    <el-form label-width="110px">
      <el-form-item label="任务名称">
        <el-input v-model="createForm.name" placeholder="例：五月舆情分析" />
      </el-form-item>
      <el-form-item label="分析范围">
        <el-radio-group v-model="createForm.scope">
          <el-radio value="data_warehouse">数据仓库分析</el-radio>
          <el-radio value="chat">聊天分析</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="起始日期">
        <el-date-picker v-model="createForm.date_start" type="date" placeholder="开始" style="width: 100%" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="createForm.date_end" type="date" placeholder="结束" style="width: 100%" value-format="YYYY-MM-DD" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible = false">取消</el-button>
      <el-button type="primary" :loading="createLoading" @click="submitCreate">创建并分析</el-button>
    </template>
  </el-dialog>

  <!-- Task Detail Drawer -->
  <el-drawer v-model="detailVisible" title="分析报告" size="600px" :loading="detailLoading">
    <template v-if="selectedTask">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="名称">{{ selectedTask.name }}</el-descriptions-item>
        <el-descriptions-item label="范围">{{ scopeLabel(selectedTask.scope) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(selectedTask.status)" size="small">{{ statusLabel(selectedTask.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ selectedTask.created_at }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedTask.completed_at" label="完成时间">{{ selectedTask.completed_at }}</el-descriptions-item>
        <el-descriptions-item label="创建者">{{ selectedTask.created_by?.display_name || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedTask.error_message" label="错误信息" :span="2">
          <span style="color: #F56C6C">{{ selectedTask.error_message }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Report: show JSON text -->
      <div v-if="selectedReport" style="margin-top: 20px">
        <el-card>
          <template #header><span style="font-weight: bold">分析报告</span></template>
          <MarkdownRenderer :content="selectedReport.summary_text || (selectedReport.report_data as any)?.raw || '暂无内容'" />
        </el-card>
      </div>
    </template>
  </el-drawer>
</template>

