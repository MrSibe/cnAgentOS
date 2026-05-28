import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, get, post, setCsrfToken } from '@/api/client'
import type { BootPayload, NavigationItem, SessionUser } from '@/types'

export const useSessionStore = defineStore('session', () => {
  const user = ref<SessionUser | null>(null)
  const permissions = ref<string[]>([])
  const navigation = ref<NavigationItem[]>([])
  const initialized = ref(false)
  const authenticated = computed(() => user.value !== null)

  function clear(): void {
    user.value = null
    permissions.value = []
    navigation.value = []
    setCsrfToken('')
  }

  async function bootstrap(): Promise<void> {
    try {
      const payload = await get<BootPayload>('/api/v1/auth/boot')
      user.value = payload.user
      permissions.value = payload.permissions
      navigation.value = payload.navigation
      setCsrfToken(payload.csrf_token)
    } catch (error) {
      clear()
      if (!(error instanceof ApiError) || error.status !== 401) throw error
    } finally {
      initialized.value = true
    }
  }

  async function login(credentials: { username: string; password: string }): Promise<void> {
    const payload = await post<{ user: SessionUser; csrf_token: string }>('/api/v1/auth/login', credentials)
    user.value = payload.user
    setCsrfToken(payload.csrf_token)
    await bootstrap()
  }

  async function logout(): Promise<void> {
    try {
      await post<void>('/api/v1/auth/logout')
    } finally {
      clear()
      initialized.value = true
    }
  }

  return { user, permissions, navigation, initialized, authenticated, bootstrap, login, logout }
})
