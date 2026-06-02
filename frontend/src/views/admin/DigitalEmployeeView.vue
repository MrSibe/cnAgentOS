<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch, post, remove } from '@/api/client'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { DigitalEmployeeItem, ToolItem } from '@/types'
import { errorMessage } from '@/utils/display'

const loading = ref(false)
const employees = ref<DigitalEmployeeItem[]>([])
const models = ref<any[]>([])
const createVisible = ref(false)
const editVisible = ref(false)
const toolBindVisible = ref(false)
const callLogVisible = ref(false)
const callLogs = ref<any[]>([])
const selected = ref<DigitalEmployeeItem | null>(null)
const createForm = reactive({
  code: '', name: '', description: '', system_prompt: '',
  model_config_id: '', trigger_type: 'mention', max_turns: 20,
})
const editForm = reactive({
  name: '', description: '', system_prompt: '',
  model_config_id: '', trigger_type: 'mention', max_turns: 20,
})
const availableTools = ref<ToolItem[]>([])
const boundToolIds = ref<string[]>([])

async function load(): Promise<void> {
  loading.value = true
  try {
    const [emps, mods] = await Promise.all([
      get<DigitalEmployeeItem[]>('/api/v1/admin/digital-employees?page_size=100'),
      get<any[]>('/api/v1/admin/models?page_size=100'),
    ])
    employees.value = emps
    models.value = mods
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function resetCreate(): void {
  Object.assign(createForm, {
    code: '', name: '', description: '', system_prompt: '',
    model_config_id: '', trigger_type: 'mention', max_turns: 20,
  })
}

async function createEmployee(): Promise<void> {
  try {
    await post('/api/v1/admin/digital-employees', createForm)
    createVisible.value = false
    resetCreate()
    ElMessage.success('数字员工已创建')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function openEdit(emp: DigitalEmployeeItem): void {
  selected.value = emp
  Object.assign(editForm, {
    name: emp.name, description: emp.description || '', system_prompt: emp.system_prompt || '',
    model_config_id: emp.model_config_id || '', trigger_type: emp.trigger_type, max_turns: emp.max_turns,
  })
  editVisible.value = true
}

async function updateEmployee(): Promise<void> {
  if (!selected.value) return
  try {
    await patch('/api/v1/admin/digital-employees/' + selected.value.id, editForm)
    editVisible.value = false
    ElMessage.success('数字员工已更新')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function updateStatus(emp: DigitalEmployeeItem, status: string): Promise<void> {
  try {
    await patch('/api/v1/admin/digital-employees/' + emp.id + '/status', { status })
    ElMessage.success(status === 'active' ? '数字员工已启用' : '数字员工已禁用')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function openToolBind(emp: DigitalEmployeeItem): Promise<void> {
  selected.value = emp
  try {
    const [tools, bound] = await Promise.all([
      get<ToolItem[]>('/api/v1/admin/tools?page_size=100'),
      get<any[]>('/api/v1/admin/digital-employees/' + emp.id + '/tools'),
    ])
    availableTools.value = tools
    boundToolIds.value = bound.map((b: any) => b.tool_id)
    toolBindVisible.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function toggleToolBind(toolId: string): Promise<void> {
  if (!selected.value) return
  try {
    if (boundToolIds.value.includes(toolId)) {
      await remove('/api/v1/admin/digital-employees/' + selected.value.id + '/tools/' + toolId)
      boundToolIds.value = boundToolIds.value.filter(id => id !== toolId)
    } else {
      await post('/api/v1/admin/digital-employees/' + selected.value.id + '/tools', { tool_id: toolId })
      boundToolIds.value.push(toolId)
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function openCallLogs(emp: DigitalEmployeeItem): Promise<void> {
  selected.value = emp
  try {
    callLogs.value = await get<any[]>('/api/v1/admin/digital-employees/' + emp.id + '/call-logs?page_size=50')
    callLogVisible.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <AdminPageHeader title="数字员工管理" description="管理数字员工配置和工具绑定" />
  <el-card>
    <div style="margin-bottom: 16px">
      <el-button type="primary" @click="createVisible = true; resetCreate()">新增员工</el-button>
    </div>
    <el-table v-loading="loading" :data="employees">
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="code" label="代码" width="120" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column prop="trigger_type" label="触发方式" width="100" />
      <el-table-column prop="model_name" label="绑定模型" width="150" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="openToolBind(row)">工具绑定</el-button>
          <el-button size="small" @click="openCallLogs(row)">调用日志</el-button>
          <el-button size="small" :type="row.status === 'active' ? 'warning' : 'success'" @click="updateStatus(row, row.status === 'active' ? 'disabled' : 'active')">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="createVisible" title="新增数字员工" width="600px">
    <el-form :model="createForm" label-width="120px">
      <el-form-item label="代码" required><el-input v-model="createForm.code" placeholder="如 sichuan_agri" /></el-form-item>
      <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="createForm.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="系统提示词" required>
        <el-input v-model="createForm.system_prompt" type="textarea" :rows="6" />
      </el-form-item>
      <el-form-item label="绑定模型">
        <el-select v-model="createForm.model_config_id" clearable placeholder="选择模型" style="width: 100%">
          <el-option v-for="m in models" :key="m.id" :label="m.name + ' (' + m.model_name + ')'" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="触发方式">
        <el-radio-group v-model="createForm.trigger_type">
          <el-radio value="mention">@提及</el-radio>
          <el-radio value="direct_chat">私聊</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="上下文轮数"><el-input-number v-model="createForm.max_turns" :min="1" :max="100" /></el-form-item>
      <el-form-item><el-button type="primary" @click="createEmployee">创建</el-button></el-form-item>
    </el-form>
  </el-dialog>

  <el-dialog v-model="editVisible" title="编辑数字员工" width="600px">
    <el-form :model="editForm" label-width="120px">
      <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="editForm.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="系统提示词"><el-input v-model="editForm.system_prompt" type="textarea" :rows="6" /></el-form-item>
      <el-form-item label="绑定模型">
        <el-select v-model="editForm.model_config_id" clearable style="width: 100%">
          <el-option v-for="m in models" :key="m.id" :label="m.name + ' (' + m.model_name + ')'" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="触发方式">
        <el-radio-group v-model="editForm.trigger_type">
          <el-radio value="mention">@提及</el-radio>
          <el-radio value="direct_chat">私聊</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="上下文轮数"><el-input-number v-model="editForm.max_turns" :min="1" :max="100" /></el-form-item>
      <el-form-item><el-button type="primary" @click="updateEmployee">保存</el-button></el-form-item>
    </el-form>
  </el-dialog>

  <el-dialog v-model="toolBindVisible" title="工具绑定" width="500px">
    <template v-if="selected">
      <p style="margin-bottom: 12px">为「{{ selected.name }}」绑定工具：</p>
      <div v-for="tool in availableTools" :key="tool.id" style="padding: 8px 0; display: flex; align-items: center; justify-content: space-between">
        <div><strong>{{ tool.name }}</strong><span style="color: #999; margin-left: 8px">{{ tool.code }}</span></div>
        <el-switch :model-value="boundToolIds.includes(tool.id)" @change="toggleToolBind(tool.id)" />
      </div>
    </template>
  </el-dialog>

  <el-dialog v-model="callLogVisible" title="调用日志" width="600px">
    <el-table :data="callLogs">
      <el-table-column prop="tool_name" label="工具" />
      <el-table-column prop="caller_name" label="调用者" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column prop="error_code" label="错误码" width="120" />
      <el-table-column prop="latency_ms" label="耗时(ms)" width="90" />
      <el-table-column prop="created_at" label="时间" width="180" />
    </el-table>
  </el-dialog>
</template>
