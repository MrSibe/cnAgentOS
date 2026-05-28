<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { get } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import type { PermissionItem } from '@/types'
import { errorMessage } from '@/utils/display'

const loading = ref(false)
const items = ref<PermissionItem[]>([])

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await get<PermissionItem[]>('/api/v1/admin/permissions')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <admin-page-header title="权限字典" description="服务端定义的权限代码，仅用于授权选择与展示。">
    <el-button @click="load">刷新</el-button>
  </admin-page-header>
  <el-card class="resource-card" shadow="never">
    <el-table v-loading="loading" :data="items">
      <el-table-column prop="code" label="权限代码" min-width="180" />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="module" label="模块" width="130" />
      <el-table-column prop="description" label="说明" min-width="280" />
    </el-table>
  </el-card>
</template>
