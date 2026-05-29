import { createRouter, createWebHistory } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const EmptyRoute = { render: () => null }

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
        { path: 'watch-sources', component: () => import('@/views/admin/WatchSourcesView.vue') },
        { path: 'collection-tasks', component: () => import('@/views/admin/CollectionTasksView.vue') },
        { path: 'knowledge-items', component: () => import('@/views/admin/KnowledgeItemsView.vue') },
        { path: 'audit-logs', component: () => import('@/views/admin/AuditLogsView.vue') },
      ],
    },
    {
      path: '/qa',
      component: () => import('@/layouts/AdminLayout.vue'),
      children: [{ path: '', component: () => import('@/views/QaWorkspaceView.vue') }],
    },
    { path: '/', name: 'home', component: EmptyRoute },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

function firstNavigationRoute(session: ReturnType<typeof useSessionStore>): string {
  const stack = [...session.navigation]
  while (stack.length) {
    const item = stack.shift()
    if (!item) continue
    if (item.route_path) return item.route_path
    if (item.children?.length) stack.unshift(...item.children)
  }
  return '/admin/users'
}

router.beforeEach(async (to) => {
  const session = useSessionStore()
  if (!session.initialized) await session.bootstrap().catch(() => undefined)
  if (to.meta.public) return session.authenticated ? firstNavigationRoute(session) : true
  if (!session.authenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'home') return firstNavigationRoute(session)
  return true
})

export default router
