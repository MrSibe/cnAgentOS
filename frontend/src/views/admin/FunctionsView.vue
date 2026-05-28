<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post, remove } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'
import type { FunctionItem, PermissionItem } from '@/types'
import { errorMessage, isUserCancelled } from '@/utils/display'

const session = useSessionStore()
const loading = ref(false)
const submitting = ref(false)
const functions = ref<FunctionItem[]>([])
const permissions = ref<PermissionItem[]>([])
const editVisible = ref(false)
const selected = ref<FunctionItem | null>(null)
const emptyForm = () => ({ code: '', name: '', parent_id: null as string | null, route_path: '', icon: 'circle', required_permission_code: null as string | null, sort_order: 100 })
const createForm = reactive(emptyForm())
const editForm = reactive({ name: '', parent_id: null as string | null, route_path: '', icon: '', required_permission_code: null as string | null, sort_order: 0, status: 'active' })

async function load(): Promise<void> {
  loading.value = true
  try {
    ;[functions.value, permissions.value] = await Promise.all([
      get<FunctionItem[]>('/api/v1/admin/functions'),
      get<PermissionItem[]>('/api/v1/admin/permissions'),
    ])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function payload(form: typeof createForm | typeof editForm): Record<string, unknown> {
  return { ...form, route_path: form.route_path || null, icon: form.icon || null }
}

async function refreshAfterChange(): Promise<void> {
  await Promise.all([load(), session.bootstrap()])
}

async function createFunction(): Promise<void> {
  submitting.value = true
  try {
    await post<FunctionItem>('/api/v1/admin/functions', payload(createForm))
    Object.assign(createForm, emptyForm())
    ElMessage.success('功能入口已创建，启用前请确认页面与权限均可用')
    await refreshAfterChange()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

function openEdit(item: FunctionItem): void {
  selected.value = item
  Object.assign(editForm, {
    name: item.name,
    parent_id: item.parent_id ?? null,
    route_path: item.route_path ?? '',
    icon: item.icon ?? '',
    required_permission_code: item.required_permission_code ?? null,
    sort_order: item.sort_order,
    status: item.status,
  })
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!selected.value) return
  submitting.value = true
  try {
    await patch<FunctionItem>(`/api/v1/admin/functions/${selected.value.id}`, payload(editForm))
    editVisible.value = false
    ElMessage.success('功能入口已更新')
    await refreshAfterChange()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(item: FunctionItem): Promise<void> {
  const status = item.status === 'active' ? 'disabled' : 'active'
  try {
    await ElMessageBox.confirm(`确认将功能 ${item.code} 改为 ${status}？`, '状态确认', { type: 'warning' })
    await patch<FunctionItem>(`/api/v1/admin/functions/${item.id}`, { status })
    await refreshAfterChange()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

async function deleteFunction(item: FunctionItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除功能 ${item.code}？`, '删除确认', { type: 'warning' })
    await remove(`/api/v1/admin/functions/${item.id}`)
    ElMessage.success('功能入口已删除')
    await refreshAfterChange()
  } catch (error) {
    if (!isUserCancelled(error)) ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="功能导航" description="菜单负责入口展示，接口权限仍由服务端在每次请求时校验。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <div class="resource-grid">
    <el-card class="resource-card" shadow="never">
      <el-table v-loading="loading" :data="functions">
        <el-table-column prop="code" label="功能代码" min-width="150" />
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column prop="route_path" label="页面路径" min-width="175" />
        <el-table-column prop="required_permission_code" label="所需权限" min-width="180" />
        <el-table-column label="状态" width="105"><template #default="{ row }"><status-tag :value="row.status" /></template></el-table-column>
        <el-table-column prop="sort_order" label="排序" width="72" />
        <el-table-column label="操作" fixed="right" width="190">
          <template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link @click="toggleStatus(row)">启停</el-button><el-button link type="danger" @click="deleteFunction(row)">删除</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card class="editor-card" shadow="never">
      <template #header><strong>新增功能</strong></template>
      <el-form label-position="top" :model="createForm">
        <el-form-item label="功能代码"><el-input v-model="createForm.code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="父级功能"><el-select v-model="createForm.parent_id" clearable><el-option v-for="item in functions" :key="item.id" :value="item.id" :label="`${item.name} (${item.code})`" /></el-select></el-form-item>
        <el-form-item label="页面路径"><el-input v-model="createForm.route_path" placeholder="/admin/example" /></el-form-item>
        <el-form-item label="图标标识"><el-input v-model="createForm.icon" /></el-form-item>
        <el-form-item label="所需权限"><el-select v-model="createForm.required_permission_code" clearable><el-option v-for="item in permissions" :key="item.id" :value="item.code" :label="`${item.name} (${item.code})`" /></el-select></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="createForm.sort_order" :min="0" /></el-form-item>
        <el-button type="primary" :loading="submitting" @click="createFunction">创建功能</el-button>
      </el-form>
    </el-card>
  </div>
  <el-dialog v-model="editVisible" title="编辑功能" width="560px">
    <el-form label-position="top" :model="editForm">
      <el-form-item label="功能代码"><el-input :model-value="selected?.code" disabled /></el-form-item>
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="父级功能"><el-select v-model="editForm.parent_id" clearable><el-option v-for="item in functions.filter((entry) => entry.id !== selected?.id)" :key="item.id" :value="item.id" :label="`${item.name} (${item.code})`" /></el-select></el-form-item>
      <el-form-item label="页面路径"><el-input v-model="editForm.route_path" /></el-form-item>
      <el-form-item label="图标标识"><el-input v-model="editForm.icon" /></el-form-item>
      <el-form-item label="所需权限"><el-select v-model="editForm.required_permission_code" clearable><el-option v-for="item in permissions" :key="item.id" :value="item.code" :label="`${item.name} (${item.code})`" /></el-select></el-form-item>
      <el-form-item label="排序"><el-input-number v-model="editForm.sort_order" :min="0" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="editForm.status"><el-option value="active" label="active" /><el-option value="disabled" label="disabled" /></el-select></el-form-item>
    </el-form>
    <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button></template>
  </el-dialog>
</template>
