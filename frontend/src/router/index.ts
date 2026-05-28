import { createRouter, createWebHistory } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    {
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [
        { path: '', redirect: '/admin/users' },
        { path: 'users', component: () => import('@/views/admin/UsersView.vue') },
        { path: 'roles', component: () => import('@/views/admin/RolesView.vue') },
        { path: 'permissions', component: () => import('@/views/admin/PermissionsView.vue') },
        { path: 'functions', component: () => import('@/views/admin/FunctionsView.vue') },
        { path: 'models', component: () => import('@/views/admin/ModelsView.vue') },
        { path: 'model-calls', component: () => import('@/views/admin/ModelCallsView.vue') },
        { path: 'audit-logs', component: () => import('@/views/admin/AuditLogsView.vue') },
      ],
    },
    { path: '/', redirect: '/admin/users' },
    { path: '/:pathMatch(.*)*', redirect: '/admin/users' },
  ],
})

router.beforeEach(async (to) => {
  const session = useSessionStore()
  if (!session.initialized) await session.bootstrap().catch(() => undefined)
  if (to.meta.public) return session.authenticated ? '/admin/users' : true
  if (!session.authenticated) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
