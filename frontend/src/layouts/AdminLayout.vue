<script setup lang="ts">
import { Moon, Sunny } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppNavigation from '@/components/AppNavigation.vue'
import { useSessionStore } from '@/stores/session'
import { errorMessage } from '@/utils/display'

const router = useRouter()
const session = useSessionStore()
const dark = ref(localStorage.getItem('theme') === 'dark')
const displayName = computed(() => session.user?.display_name || '用户')

function applyTheme(): void {
  document.documentElement.classList.toggle('dark', dark.value)
  localStorage.setItem('theme', dark.value ? 'dark' : 'light')
}

applyTheme()

function toggleTheme(): void {
  dark.value = !dark.value
  applyTheme()
}

async function logout(): Promise<void> {
  try {
    await session.logout()
  } catch (error) {
    ElMessage.warning(errorMessage(error))
  } finally {
    await router.replace('/login')
  }
}
</script>

<template>
  <div class="console-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-monogram">CN</span>
        <span><strong>cnAgentOS</strong><small>智能瞭望控制台</small></span>
      </div>
      <p class="sidebar-label">功能导航</p>
      <app-navigation :nodes="session.navigation" class="sidebar-navigation" />
      <button class="theme-switch" type="button" @click="toggleTheme">
        <el-icon><Sunny v-if="dark" /><Moon v-else /></el-icon>
        {{ dark ? '亮色模式' : '深色模式' }}
      </button>
    </aside>
    <section class="workspace">
      <header class="topbar">
        <div class="environment-pill"><span /> 受控环境 / 权限实时生效</div>
        <div class="account-actions">
          <span class="account-name">{{ displayName }} · {{ session.user?.username }}</span>
          <el-button plain @click="logout">退出</el-button>
        </div>
      </header>
      <main class="page-content">
        <router-view />
      </main>
    </section>
  </div>
</template>
