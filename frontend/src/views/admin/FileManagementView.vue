<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get, remove } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { AdminFileItem, FileStatsItem } from '@/types'
import { errorMessage, isUserCancelled, formatFileSize } from '@/utils/display'

const loading = ref(false)
const files = ref<AdminFileItem[]>([])
const stats = ref<FileStatsItem | null>(null)
const detailVisible = ref(false)
const selectedFile = ref<AdminFileItem | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: '1', page_size: '20' })
    const [fileData, statsData] = await Promise.all([
      get<AdminFileItem[]>('/api/v1/admin/files?' + params),
      get<FileStatsItem>('/api/v1/admin/files/stats'),
    ])
    files.value = fileData
    stats.value = statsData
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function openDetail(file: AdminFileItem): void {
  selectedFile.value = file
  detailVisible.value = true
}

async function deleteFile(file: AdminFileItem): Promise<void> {
  try {
    await ElMessageBox.confirm('确定删除文件「' + file.filename + '」？', '确认', { type: 'warning' })
    await remove('/api/v1/admin/files/' + file.id)
    ElMessage.success('文件已删除')
    await load()
  } catch (error) {
    if (isUserCancelled(error)) return
    ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="文件管理" description="管理上传的文件和存储空间" />
  <el-row :gutter="16" style="margin-bottom: 16px" v-if="stats">
    <el-col :span="6">
      <el-card><div style="text-align: center">
        <div style="font-size: 28px; font-weight: bold">{{ stats.total_files }}</div>
        <div style="color: #999">文件总数</div>
      </div></el-card>
    </el-col>
    <el-col :span="6">
      <el-card><div style="text-align: center">
        <div style="font-size: 28px; font-weight: bold">{{ stats.total_blobs }}</div>
        <div style="color: #999">存储块数</div>
      </div></el-card>
    </el-col>
    <el-col :span="6">
      <el-card><div style="text-align: center">
        <div style="font-size: 28px; font-weight: bold">{{ formatFileSize(stats.total_size_bytes) }}</div>
        <div style="color: #999">总占用空间</div>
      </div></el-card>
    </el-col>
    <el-col :span="6">
      <el-card><div style="text-align: center">
        <div style="font-size: 28px; font-weight: bold">{{ (stats.dedup_ratio * 100).toFixed(1) }}%</div>
        <div style="color: #999">去重节省比率</div>
      </div></el-card>
    </el-col>
  </el-row>
  <el-card>
    <el-table v-loading="loading" :data="files" stripe>
      <el-table-column prop="filename" label="文件名" min-width="200" />
      <el-table-column prop="mime_type" label="类型" width="120" />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column label="SHA-256" width="110">
        <template #default="{ row }">{{ (row.sha256 || '').slice(0, 12) }}...</template>
      </el-table-column>
      <el-table-column prop="uploaded_by" label="上传者" width="100" />
      <el-table-column prop="created_at" label="上传时间" width="180" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button size="small" type="danger" @click="deleteFile(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
  <el-dialog v-model="detailVisible" title="文件详情" width="500px">
    <template v-if="selectedFile">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="文件名">{{ selectedFile.filename }}</el-descriptions-item>
        <el-descriptions-item label="MIME 类型">{{ selectedFile.mime_type }}</el-descriptions-item>
        <el-descriptions-item label="大小">{{ formatFileSize(selectedFile.size_bytes) }}</el-descriptions-item>
        <el-descriptions-item label="SHA-256">{{ selectedFile.sha256 }}</el-descriptions-item>
        <el-descriptions-item label="上传者">{{ selectedFile.uploaded_by }}</el-descriptions-item>
        <el-descriptions-item label="上传时间">{{ selectedFile.created_at }}</el-descriptions-item>
      </el-descriptions>
    </template>
  </el-dialog>
</template>
