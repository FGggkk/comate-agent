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
      ],
    },
  ],
})

router.beforeEach((to) => {
  const store = useAdminStore()
  if (to.path !== '/login' && !store.isLoggedIn) return '/login'
  if (to.path === '/login' && store.isLoggedIn) return '/dashboard'
})
