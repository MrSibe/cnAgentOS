<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post, remove } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'
import type { PermissionItem, RoleItem } from '@/types'
import { errorMessage, isUserCancelled } from '@/utils/display'

const session = useSessionStore()
const loading = ref(false)
const submitting = ref(false)
const roles = ref<RoleItem[]>([])
const permissions = ref<PermissionItem[]>([])
const editVisible = ref(false)
const selected = ref<RoleItem | null>(null)
const createForm = reactive({ code: '', name: '', description: '', permission_ids: [] as string[] })
const editForm = reactive({ name: '', description: '', status: 'active', permission_ids: [] as string[] })

async function load(): Promise<void> {
  loading.value = true
  try {
    ;[roles.value, permissions.value] = await Promise.all([
      get<RoleItem[]>('/api/v1/admin/roles?page_size=100'),
      get<PermissionItem[]>('/api/v1/admin/permissions'),
    ])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function refreshAfterChange(): Promise<void> {
  await Promise.all([load(), session.bootstrap()])
}

async function createRole(): Promise<void> {
  submitting.value = true
  try {
    await post<RoleItem>('/api/v1/admin/roles', createForm)
    Object.assign(createForm, { code: '', name: '', description: '', permission_ids: [] })
    ElMessage.success('角色已创建')
    await refreshAfterChange()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openEdit(role: RoleItem): void {
  selected.value = role
  editForm.name = role.name
  editForm.description = role.description ?? ''
  editForm.status = role.status
  editForm.permission_ids = permissions.value.filter((item) => role.permissions.includes(item.code)).map((item) => item.id)
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  submitting.value = true
  try {
    await patch<RoleItem>(`/api/v1/admin/roles/${selected.value.id}`, editForm)
    editVisible.value = false
    ElMessage.success('角色已更新')
    await refreshAfterChange()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function deleteRole(role: RoleItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除角色 ${role.code}？`, '删除确认', { type: 'warning' })
    await remove(`/api/v1/admin/roles/${role.id}`)
    ElMessage.success('角色已删除')
    await refreshAfterChange()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="角色权限" description="角色授权修改后，后续受保护请求会立即按实时权限重新判定。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <el-table v-loading="loading" :data="roles">
        <el-table-column prop="code" label="角色代码" min-width="150" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="权限" min-width="290"><template #default="{ row }"><el-tag v-for="permission in row.permissions" :key="permission" class="value-tag" effect="plain">{{ permission }}</el-tag><span v-if="!row.permissions.length">-</span></template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column label="系统角色" width="110"><template #default="{ row }"><el-tag :type="row.is_system ? 'warning' : 'info'" effect="plain">{{ row.is_system ? '是' : '否' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="130"><template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="deleteRole(row)">删除</el-button></template></el-table-column>
      </el-table>
    </el-card>
    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增角色</strong></template>
      <el-form label-position="top" :model="createForm">
        <el-form-item label="角色代码"><el-input v-model="createForm.code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="createForm.description" type="textarea" /></el-form-item>
        <el-form-item label="授予权限"><el-checkbox-group v-model="createForm.permission_ids" class="check-stack"><el-checkbox v-for="permission in permissions" :key="permission.id" :value="permission.id">{{ permission.name }} <small>{{ permission.code }}</small></el-checkbox></el-checkbox-group></el-form-item>
        <el-button type="primary" :loading="submitting" @click="createRole">创建角色</el-button>
      </el-form>
    </el-card>
  </div>
  <el-dialog v-model="editVisible" title="编辑角色" width="560px">
    <el-form label-position="top" :model="editForm">
      <el-form-item label="角色代码"><el-input :model-value="selected?.code" disabled /></el-form-item>
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="editForm.description" type="textarea" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="editForm.status"><el-option label="active" value="active" /><el-option label="disabled" value="disabled" /></el-select></el-form-item>
      <el-form-item label="授予权限"><el-checkbox-group v-model="editForm.permission_ids" class="check-stack"><el-checkbox v-for="permission in permissions" :key="permission.id" :value="permission.id">{{ permission.name }} <small>{{ permission.code }}</small></el-checkbox></el-checkbox-group></el-form-item>
    </el-form>
    <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button></template>
  </el-dialog>
</template>
