<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { SentimentTaskItem, SentimentTaskDetail, SentimentReportItem } from '@/types'
import { errorMessage, isUserCancelled } from '@/utils/display'

const loading = ref(false)
const tasks = ref<SentimentTaskItem[]>([])
const page = ref(1)
const pageSize = ref(20)

// Create dialog
const createVisible = ref(false)
const createLoading = ref(false)
const createForm = ref({
  name: '',
  task_type: 'full',
  include_chat_data: false,
  date_start: '',
  date_end: '',
})

// Detail drawer
const detailVisible = ref(false)
const detailLoading = ref(false)
const selectedTask = ref<SentimentTaskDetail | null>(null)
const selectedReports = ref<SentimentReportItem[]>([])
const activeReportTab = ref('summary')

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const resp = await get<SentimentTaskItem[]>('/api/v1/admin/sentiment/tasks?' + params)
    tasks.value = resp
    // total is returned via meta envelope
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function openCreate(): Promise<void> {
  createForm.value = { name: '', task_type: 'full', include_chat_data: false, date_start: '', date_end: '' }
  createVisible.value = true
}

async function submitCreate(): Promise<void> {
  if (!createForm.value.name) {
    ElMessage.warning('请输入任务名称')
    return
  }
  createLoading.value = true
  try {
    const payload: Record<string, unknown> = { name: createForm.value.name, task_type: createForm.value.task_type }
    if (createForm.value.date_start || createForm.value.date_end || createForm.value.include_chat_data) {
      const scope: Record<string, string> = {}
      if (createForm.value.date_start) scope.start_date = createForm.value.date_start
      if (createForm.value.date_end) scope.end_date = createForm.value.date_end
      if (Object.keys(scope).length) payload.data_scope = scope
    }
    if (createForm.value.include_chat_data) payload.include_chat_data = true
    await post('/api/v1/admin/sentiment/tasks', payload)
    ElMessage.success('任务已创建')
    createVisible.value = false
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
    const [detail, reports] = await Promise.all([
      get<SentimentTaskDetail>('/api/v1/admin/sentiment/tasks/' + task.id),
      get<SentimentReportItem[]>('/api/v1/admin/sentiment/tasks/' + task.id + '/reports'),
    ])
    selectedTask.value = detail
    selectedReports.value = reports
    if (reports.length) activeReportTab.value = reports[0].report_type
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function runTask(task: SentimentTaskItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定运行任务「${task.name}」？`, '确认', { type: 'info' })
    await post('/api/v1/admin/sentiment/tasks/' + task.id + '/run')
    ElMessage.success('任务已启动')
    await load()
  } catch (error) {
    if (isUserCancelled(error)) return
    ElMessage.error(errorMessage(error))
  }
}

function taskTypeLabel(t: string): string {
  const map: Record<string, string> = { full: '综合分析', sentiment: '情感分析', keyword: '关键词', hotspot: '热点挖掘' }
  return map[t] || t
}

function statusTag(s: string): string {
  const map: Record<string, string> = {
    pending: 'info', running: 'warning', completed: 'success', failed: 'danger',
  }
  return map[s] || 'info'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = { pending: '等待', running: '运行中', completed: '完成', failed: '失败' }
  return map[s] || s
}

function reportTypeLabel(t: string): string {
  const map: Record<string, string> = { sentiment: '情感分析', keyword: '关键词提取', hotspot: '热点挖掘', summary: '综合摘要' }
  return map[t] || t
}

function sentimentColor(s: string): string {
  if (s === 'positive') return '#67C23A'
  if (s === 'negative') return '#F56C6C'
  return '#909399'
}

function sentimentLabel(s: string): string {
  const map: Record<string, string> = { positive: '正面', neutral: '中性', negative: '负面' }
  return map[s] || s
}

function renderSentiment(report: SentimentReportItem): string {
  const data = report.report_data as Record<string, unknown>
  const pos = Number(data.positive_count || data.positive || 0)
  const neg = Number(data.negative_count || data.negative || 0)
  const neu = Number(data.neutral_count || data.neutral || 0)
  const total = pos + neg + neu || 1
  const posPct = ((pos / total) * 100).toFixed(1)
  const negPct = ((neg / total) * 100).toFixed(1)
  const neuPct = ((neu / total) * 100).toFixed(1)
  return `正面 ${posPct}% | 中性 ${neuPct}% | 负面 ${negPct}%`
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="舆情分析" description="运行情感、关键词、热点分析任务并查看报告" />

  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>分析任务</span>
        <el-button type="primary" @click="openCreate">创建任务</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="tasks" stripe empty-text="暂无分析任务">
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="100">
        <template #default="{ row }">
          <el-progress :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : undefined" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDetail(row)">详情</el-button>
          <el-button
            size="small"
            :disabled="row.status === 'running'"
            @click="runTask(row)"
          >运行</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- Create Task Dialog -->
  <el-dialog v-model="createVisible" title="创建分析任务" width="500px">
    <el-form label-width="100px">
      <el-form-item label="任务名称">
        <el-input v-model="createForm.name" placeholder="例：五月舆情分析" />
      </el-form-item>
      <el-form-item label="分析类型">
        <el-select v-model="createForm.task_type" style="width: 100%">
          <el-option value="full" label="综合分析（情感+关键词+热点）" />
          <el-option value="sentiment" label="情感分析" />
          <el-option value="keyword" label="关键词提取" />
          <el-option value="hotspot" label="热点挖掘" />
        </el-select>
      </el-form-item>
      <el-form-item label="起始日期">
        <el-date-picker v-model="createForm.date_start" type="date" placeholder="开始" style="width: 100%" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="createForm.date_end" type="date" placeholder="结束" style="width: 100%" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="聊天数据">
        <el-switch v-model="createForm.include_chat_data" />
        <span style="margin-left: 8px; color: #999; font-size: 12px">纳入授权聊天内容到分析</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible = false">取消</el-button>
      <el-button type="primary" :loading="createLoading" @click="submitCreate">创建</el-button>
    </template>
  </el-dialog>

  <!-- Task Detail Drawer -->
  <el-drawer v-model="detailVisible" title="任务详情" size="600px" :loading="detailLoading">
    <template v-if="selectedTask">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="名称">{{ selectedTask.name }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ taskTypeLabel(selectedTask.task_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(selectedTask.status)" size="small">{{ statusLabel(selectedTask.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">
          <el-progress :percentage="selectedTask.progress" :status="selectedTask.status === 'failed' ? 'exception' : undefined" style="width: 120px" />
        </el-descriptions-item>
        <el-descriptions-item label="分析条目">{{ selectedTask.source_item_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建者">{{ selectedTask.created_by?.display_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ selectedTask.created_at }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ selectedTask.completed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedTask.error_message" label="错误信息" :span="2">
          <span style="color: #F56C6C">{{ selectedTask.error_message }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Reports -->
      <div style="margin-top: 20px" v-if="selectedReports.length">
        <el-tabs v-model="activeReportTab">
          <el-tab-pane
            v-for="report in selectedReports"
            :key="report.id"
            :label="reportTypeLabel(report.report_type)"
            :name="report.report_type"
          >
            <!-- Summary Report -->
            <template v-if="report.report_type === 'summary'">
              <el-card>
                <p style="white-space: pre-wrap; line-height: 1.8">{{ report.summary_text || '暂无摘要' }}</p>
              </el-card>
            </template>

            <!-- Sentiment Report -->
            <template v-else-if="report.report_type === 'sentiment'">
              <el-card style="margin-bottom: 12px">
                <div style="font-size: 16px; font-weight: bold; margin-bottom: 12px">情感分布</div>
                <div>{{ renderSentiment(report) }}</div>
                <el-progress
                  :percentage="(Number((report.report_data as any).positive_count || 0) / Math.max(1, (report.report_data as any).positive_count + (report.report_data as any).neutral_count + (report.report_data as any).negative_count)) * 100"
                  color="#67C23A"
                  style="margin-top: 8px"
                />
              </el-card>
              <div v-if="report.summary_text" style="margin-top: 8px; color: #666; font-size: 13px">
                {{ report.summary_text }}
              </div>
              <el-table v-if="(report.report_data as any).details?.length" :data="(report.report_data as any).details" stripe size="small" style="margin-top: 12px">
                <el-table-column prop="content_title" label="内容" min-width="200" />
                <el-table-column label="情感" width="80">
                  <template #default="{ row }">
                    <el-tag :color="sentimentColor(row.sentiment)" size="small" style="color:#fff;border:none">
                      {{ sentimentLabel(row.sentiment) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="80">
                  <template #default="{ row }">
                    {{ ((row.confidence || 0) * 100).toFixed(0) }}%
                  </template>
                </el-table-column>
              </el-table>
            </template>

            <!-- Keyword Report -->
            <template v-else-if="report.report_type === 'keyword'">
              <div v-if="(report.report_data as any).keywords?.length" style="display: flex; flex-wrap: wrap; gap: 8px">
                <el-tag
                  v-for="kw in (report.report_data as any).keywords"
                  :key="kw.word"
                  :style="{ fontSize: 12 + (kw.weight || 0.5) * 8 + 'px' }"
                  effect="plain"
                >{{ kw.word }} ({{ kw.count }})</el-tag>
              </div>
              <div v-else style="color: #999">暂无关键词数据</div>
              <div v-if="report.summary_text" style="margin-top: 12px; color: #666; font-size: 13px">
                {{ report.summary_text }}
              </div>
            </template>

            <!-- Hotspot Report -->
            <template v-else-if="report.report_type === 'hotspot'">
              <el-table v-if="(report.report_data as any).hotspots?.length" :data="(report.report_data as any).hotspots" stripe size="small">
                <el-table-column prop="title" label="热点主题" min-width="200" />
                <el-table-column prop="related_count" label="相关文章" width="100" />
                <el-table-column prop="description" label="描述" min-width="250" />
              </el-table>
              <div v-else style="color: #999">暂无热点数据</div>
              <div v-if="report.summary_text" style="margin-top: 12px; color: #666; font-size: 13px">
                {{ report.summary_text }}
              </div>
            </template>
          </el-tab-pane>
        </el-tabs>
      </div>
      <div v-else-if="!detailLoading" style="text-align: center; color: #999; margin-top: 40px">
        暂无分析报告，请运行任务生成报告
      </div>
    </template>
  </el-drawer>
</template>
