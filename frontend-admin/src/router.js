import { createRouter, createWebHistory } from 'vue-router'
import { useAdminStore } from './stores/admin'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./pages/Login.vue') },
    {
      path: '/',
      component: () => import('./layout/Layout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', component: () => import('./pages/Dashboard.vue'), meta: { title: '仪表盘' } },
        { path: 'users', component: () => import('./pages/Users.vue'), meta: { title: '用户' } },
        { path: 'codes', component: () => import('./pages/Codes.vue'), meta: { title: '兑换码' } },
        { path: 'billing', component: () => import('./pages/Billing.vue'), meta: { title: '计费规则' } },
        { path: 'stats', component: () => import('./pages/Stats.vue'), meta: { title: '数据统计' } },
        { path: 'settings', component: () => import('./pages/Settings.vue'), meta: { title: '系统设置' } },
        { path: 'roles', component: () => import('./pages/Roles.vue'), meta: { title: '角色管理' } },
        { path: 'company-knowledge', component: () => import('./pages/CompanyKnowledge.vue'), meta: { title: '公司制度' } },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const store = useAdminStore()
  if (to.path !== '/login' && !store.isLoggedIn) return '/login'
  if (to.path === '/login' && store.isLoggedIn) return '/dashboard'
})
