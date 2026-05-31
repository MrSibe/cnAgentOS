<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { GroupDetailItem, GroupAnnouncementItem } from '@/types'
import { errorMessage, isUserCancelled } from '@/utils/display'

const loading = ref(false)
const submitting = ref(false)
const groups = ref<any[]>([])
const page = ref(1)
const pageSize = 20
const searchQuery = ref('')
const detailVisible = ref(false)
const selectedGroup = ref<GroupDetailItem | null>(null)
const annVisible = ref(false)
const annForm = reactive({ title: '', content: '' })
const announcements = ref<GroupAnnouncementItem[]>([])

async function load(): Promise<void> {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) })
    if (searchQuery.value) params.set('q', searchQuery.value)
    const res = await get<any>(`/api/v1/admin/chat/groups?${params}`)
    groups.value = res
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function openDetail(group: any): Promise<void> {
  try {
    selectedGroup.value = await get<GroupDetailItem>(`/api/v1/admin/chat/groups/${group.id}`)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function disbandGroup(group: any): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定解散群聊「${group.name}」？此操作不可撤销。`, '警告', {
      confirmButtonText: '解散', cancelButtonText: '取消', type: 'warning',
    })
    await patch(`/api/v1/admin/chat/groups/${group.id}/disband`, {})
    ElMessage.success('群聊已解散')
    await load()
  } catch (error) {
    if (isUserCancelled(error)) return
    ElMessage.error(errorMessage(error))
  }
}

async function banMember(userId: string): Promise<void> {
  if (!selectedGroup.value) return
  try {
    await ElMessageBox.confirm('确定封禁该成员？', '警告', {
      confirmButtonText: '封禁', cancelButtonText: '取消', type: 'warning',
    })
    await patch(`/api/v1/admin/chat/groups/${selectedGroup.value.id}/members/ban`, { user_id: userId })
    ElMessage.success('成员已封禁')
    await openDetail(selectedGroup.value)
  } catch (error) {
    if (isUserCancelled(error)) return
    ElMessage.error(errorMessage(error))
  }
}

async function unbanMember(userId: string): Promise<void> {
  if (!selectedGroup.value) return
  try {
    await patch(`/api/v1/admin/chat/groups/${selectedGroup.value.id}/members/unban`, { user_id: userId })
    ElMessage.success('成员已解封')
    await openDetail(selectedGroup.value)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function openAnnouncements(group: any): Promise<void> {
  try {
    announcements.value = await get<GroupAnnouncementItem[]>(`/api/v1/admin/chat/groups/${group.id}/announcements`)
    selectedGroup.value = group
    annVisible.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function createAnnouncement(): Promise<void> {
  if (!selectedGroup.value) return
  submitting.value = true
  try {
    await post(`/api/v1/admin/chat/groups/${selectedGroup.value.id}/announcements`, annForm)
    ElMessage.success('公告已发布')
    annForm.title = ''
    annForm.content = ''
    await openAnnouncements(selectedGroup.value)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function onSearch(): void {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="群管理" description="管理所有聊天群组" />
  <el-card>
    <div style="margin-bottom: 16px; display: flex; gap: 8px">
      <el-input v-model="searchQuery" placeholder="搜索群名称" clearable style="width: 300px" @keyup.enter="onSearch" />
      <el-button type="primary" @click="onSearch">搜索</el-button>
    </div>
    <el-table v-loading="loading" :data="groups" stripe>
      <el-table-column prop="name" label="群名称" />
      <el-table-column prop="member_count" label="成员数" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_disbanded ? 'danger' : 'success'" size="small">
            {{ row.is_disbanded ? '已解散' : '正常' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_by" label="创建者" width="120" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button size="small" @click="openAnnouncements(row)">公告</el-button>
          <el-button size="small" type="danger" :disabled="row.is_disbanded" @click="disbandGroup(row)">解散</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="detailVisible" title="群详情" width="600px">
    <template v-if="selectedGroup">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="群名称">{{ selectedGroup.name }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ selectedGroup.member_count }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="selectedGroup.is_disbanded ? 'danger' : 'success'" size="small">
            {{ selectedGroup.is_disbanded ? '已解散' : '正常' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建者">{{ selectedGroup.created_by }}</el-descriptions-item>
      </el-descriptions>
      <el-divider>成员列表</el-divider>
      <el-table :data="selectedGroup.members" stripe>
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="display_name" label="显示名称" />
        <el-table-column prop="role" label="角色" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.banned_at" type="danger" size="small">已封禁</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="!row.banned_at" size="small" type="warning" @click="banMember(row.user_id)">封禁</el-button>
            <el-button v-else size="small" type="primary" @click="unbanMember(row.user_id)">解封</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </el-dialog>

  <el-dialog v-model="annVisible" title="群公告" width="500px">
    <el-form :model="annForm" label-width="60px">
      <el-form-item label="标题">
        <el-input v-model="annForm.title" placeholder="公告标题（可选）" />
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="annForm.content" type="textarea" :rows="4" placeholder="公告内容" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="createAnnouncement">发布公告</el-button>
      </el-form-item>
    </el-form>
    <el-divider>历史公告</el-divider>
    <div v-for="a in announcements" :key="a.id" style="padding: 8px 0; border-bottom: 1px solid #eee">
      <div style="font-weight: bold">{{ a.title || '(无标题)' }}</div>
      <div style="margin: 4px 0; white-space: pre-wrap">{{ a.content }}</div>
      <div style="font-size: 12px; color: #999">{{ a.created_at }}</div>
    </div>
    <div v-if="!announcements.length" style="color: #999; text-align: center; padding: 20px">暂无公告</div>
  </el-dialog>
</template>
