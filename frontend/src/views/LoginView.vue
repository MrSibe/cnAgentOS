<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session'
import { errorMessage } from '@/utils/display'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const credentials = reactive({ username: '', password: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入登录名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function firstNavigationRoute(): string {
  const stack = [...session.navigation]
  while (stack.length) {
    const item = stack.shift()
    if (!item) continue
    if (item.route_path) return item.route_path
    if (item.children?.length) stack.unshift(...item.children)
  }
  return '/admin/users'
}

async function submit(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  loading.value = true
  try {
    await session.login(credentials)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : firstNavigationRoute()
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-screen">
    <section class="login-story">
      <p class="page-eyebrow">INTELLIGENCE WATCH / DATA ANSWERS</p>
      <h1>让每一次判断<br />都有来源可循</h1>
      <p>在统一权限边界内管理模型、采集内容与引用回答。</p>
      <div class="story-metrics">
        <span><strong>RBAC</strong><small>访问控制</small></span>
        <span><strong>SSE</strong><small>流式反馈</small></span>
        <span><strong>AUDIT</strong><small>审计追踪</small></span>
      </div>
    </section>
    <el-card class="login-card" shadow="never">
      <div class="brand"><span class="brand-monogram">CN</span><span><strong>cnAgentOS</strong><small>管理端登录</small></span></div>
      <el-form ref="formRef" :model="credentials" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="登录名" prop="username">
          <el-input v-model="credentials.username" autocomplete="username" placeholder="输入管理账号" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="credentials.password" autocomplete="current-password" placeholder="输入密码" show-password size="large" @keyup.enter="submit" />
        </el-form-item>
        <p class="security-note">凭据仅用于建立受保护会话，后台操作同时验证 CSRF 与实时权限。</p>
        <el-button class="login-submit" type="primary" size="large" :loading="loading" @click="submit">进入系统</el-button>
      </el-form>
      <p class="register-link">
        没有账号？<router-link to="/register">注册</router-link>
      </p>
    </el-card>
  </main>
</template>
