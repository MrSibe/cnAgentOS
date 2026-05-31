<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { post } from '@/api/client'
import { errorMessage } from '@/utils/display'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  password: '',
  password_confirm: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 30, message: '用户名长度 4-30 字符', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z][a-zA-Z0-9_-]{2,28}[a-zA-Z0-9]$/,
      message: '以字母开头，只允许字母、数字、下划线和连字符',
      trigger: 'blur',
    },
  ],
  display_name: [
    { required: true, message: '请输入显示名', trigger: 'blur' },
    { min: 1, max: 120, message: '显示名最长 120 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 12, max: 128, message: '密码长度 12-128 字符', trigger: 'blur' },
  ],
  password_confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string) => value === form.password,
      message: '两次密码输入不一致',
      trigger: 'blur',
    },
  ],
}

async function submit(): Promise<void> {
  if (!(await formRef.value?.validate().catch(() => false))) return
  loading.value = true
  try {
    await post('/api/v1/auth/register', {
      username: form.username,
      display_name: form.display_name,
      password: form.password,
    })
    ElMessage.success('注册成功，请登录')
    await router.replace('/login')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="register-screen">
    <section class="register-story">
      <p class="page-eyebrow">INTELLIGENCE WATCH / DATA ANSWERS</p>
      <h1>注册账号<br />开始使用</h1>
      <p>注册后将获得智能问数和智能聊天的使用权限。</p>
    </section>
    <el-card class="register-card" shadow="never">
      <div class="brand">
        <span class="brand-monogram">CN</span>
        <span><strong>cnAgentOS</strong><small>创建账号</small></span>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="4-30 字符，字母开头" size="large" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" placeholder="你的显示名称" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" autocomplete="new-password" placeholder="至少 12 字符" show-password size="large" />
        </el-form-item>
        <el-form-item label="确认密码" prop="password_confirm">
          <el-input v-model="form.password_confirm" autocomplete="new-password" placeholder="再次输入密码" show-password size="large" @keyup.enter="submit" />
        </el-form-item>
        <el-button class="register-submit" type="primary" size="large" :loading="loading" @click="submit">注册</el-button>
      </el-form>
      <p class="login-link">
        已有账号？<router-link to="/login">登录</router-link>
      </p>
    </el-card>
  </main>
</template>

<style scoped>
.register-screen {
  display: flex;
  min-height: 100vh;
  align-items: center;
  justify-content: center;
  gap: 3rem;
  padding: 2rem;
  background: var(--el-bg-color-page);
}

.register-story {
  max-width: 360px;
}

.page-eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.15em;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.5rem;
}

.register-story h1 {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.3;
  margin-bottom: 0.75rem;
}

.register-story p {
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.register-card {
  width: 400px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 1.5rem;
}

.brand-monogram {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-color-primary);
  color: #fff;
  font-weight: 700;
  border-radius: 8px;
  font-size: 0.875rem;
}

.brand small {
  display: block;
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

.register-submit {
  width: 100%;
  margin-top: 0.5rem;
}

.login-link {
  text-align: center;
  margin-top: 1rem;
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
}

.login-link a {
  color: var(--el-color-primary);
  text-decoration: none;
}

@media (max-width: 768px) {
  .register-screen {
    flex-direction: column;
    gap: 1.5rem;
  }
  .register-story { display: none; }
  .register-card { width: 100%; max-width: 400px; }
}
</style>
