<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { RoleItem, UserItem } from '@/types'
import { errorMessage, isUserCancelled, shortTime } from '@/utils/display'

const loading = ref(false)
const submitting = ref(false)
const users = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const query = ref('')
const editVisible = ref(false)
const passwordVisible = ref(false)
const selected = ref<UserItem | null>(null)
const createForm = reactive({ username: '', display_name: '', password: '', role_ids: [] as string[] })
const editForm = reactive({ display_name: '', role_ids: [] as string[] })
const passwordForm = reactive({ new_password: '' })

async function load(): Promise<void> {
  loading.value = true
  try {
    const q = query.value.trim() ? `?q=${encodeURIComponent(query.value.trim())}` : ''
    ;[users.value, roles.value] = await Promise.all([
      get<UserItem[]>(`/api/v1/admin/users${q}`),
      get<RoleItem[]>('/api/v1/admin/roles?page_size=100&status=active'),
    ])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function createUser(): Promise<void> {
  submitting.value = true
  try {
    await post<UserItem>('/api/v1/admin/users', createForm)
    Object.assign(createForm, { username: '', display_name: '', password: '', role_ids: [] })
    ElMessage.success('用户已创建')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openEdit(user: UserItem): void {
  selected.value = user
  editForm.display_name = user.display_name
  editForm.role_ids = user.roles.map((role) => role.id)
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  submitting.value = true
  try {
    await patch<UserItem>(`/api/v1/admin/users/${selected.value.id}`, editForm)
    editVisible.value = false
    ElMessage.success('用户信息已更新')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(user: UserItem): Promise<void> {
  const status = user.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(`确认将用户 ${user.username} 改为 ${status}？`, '状态确认', { type: 'warning' })
    await patch<UserItem>(`/api/v1/admin/users/${user.id}/status`, { status })
    ElMessage.success('用户状态已更新')
    await load()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

function openPassword(user: UserItem): void {
  selected.value = user
  passwordForm.new_password = ''
  passwordVisible.value = true
}

async function resetPassword(): Promise<void> {
  if (!selected.value || !passwordForm.new_password) return
  submitting.value = true
  try {
    await post<void>(`/api/v1/admin/users/${selected.value.id}/password-reset`, passwordForm)
    passwordVisible.value = false
    ElMessage.success('密码已重置')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="用户管理" description="维护账户、角色分配与启停状态，受系统管理员保护规则约束。">
    <el-input v-model="query" class="toolbar-search" clearable placeholder="搜索用户" @keyup.enter="load" />
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <el-table v-loading="loading" :data="users">
        <el-table-column prop="username" label="登录名" min-width="130" />
        <el-table-column prop="display_name" label="展示名称" min-width="140" />
        <el-table-column label="角色" min-width="190">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" class="value-tag" effect="plain">{{ role.name }}</el-tag>
            <span v-if="!row.roles.length">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column label="保护" width="92"><template #default="{ row }"><el-tag :type="row.is_system_admin ? 'warning' : 'info'" effect="plain">{{ row.is_system_admin ? '是' : '否' }}</el-tag></template></el-table-column>
        <el-table-column label="更新时间" min-width="170"><template #default="{ row }">{{ shortTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="218">
          <template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link @click="toggleStatus(row)">启停</el-button><el-button link type="danger" @click="openPassword(row)">重置密码</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增用户</strong></template>
      <el-form label-position="top" :model="createForm">
        <el-form-item label="登录名"><el-input v-model="createForm.username" /></el-form-item>
        <el-form-item label="展示名称"><el-input v-model="createForm.display_name" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="createForm.password" show-password type="password" /></el-form-item>
        <el-form-item label="角色">
          <el-checkbox-group v-model="createForm.role_ids" class="check-stack">
            <el-checkbox v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }} <small>{{ role.code }}</small></el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-button type="primary" :loading="submitting" @click="createUser">创建用户</el-button>
      </el-form>
    </el-card>
  </div>
  <el-dialog v-model="editVisible" title="编辑用户" width="520px">
    <el-form label-position="top" :model="editForm">
      <el-form-item label="登录名"><el-input :model-value="selected?.username" disabled /></el-form-item>
      <el-form-item label="展示名称"><el-input v-model="editForm.display_name" /></el-form-item>
      <el-form-item label="角色"><el-checkbox-group v-model="editForm.role_ids" class="check-stack"><el-checkbox v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }} <small>{{ role.code }}</small></el-checkbox></el-checkbox-group></el-form-item>
    </el-form>
    <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button></template>
  </el-dialog>
  <el-dialog v-model="passwordVisible" title="重置密码" width="460px">
    <p class="dialog-hint">为用户 {{ selected?.username }} 设置新密码，密码内容不会被返回或写入审计详情。</p>
    <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="输入新密码" />
    <template #footer><el-button @click="passwordVisible = false">取消</el-button><el-button type="danger" :loading="submitting" @click="resetPassword">确认重置</el-button></template>
  </el-dialog>
</template>
