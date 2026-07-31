<template>
  <div class="admin-shell">
    <!-- 侧栏 -->
    <aside class="sidebar">
      <div class="side-logo">
        <div class="logo-orb"></div>
        <div>
          <b>伴行</b>
          <small>管理后台</small>
        </div>
      </div>
      <nav class="side-nav">
        <router-link v-for="n in navs" :key="n.to" :to="n.to" :class="{ active: route.path.startsWith(n.to) }">
          <span class="nav-icon" v-html="n.icon"></span>
          <span>{{ n.label }}</span>
          <span v-if="n.badge" class="badge badge-gold" style="margin-left:auto;padding:1px 8px;font-size:10px;">规划中</span>
        </router-link>
      </nav>
      <div class="side-foot">v0.1 · 骨架阶段</div>
    </aside>

    <!-- 主区 -->
    <div class="admin-main">
      <header class="topbar">
        <div class="crumb">{{ route.meta.title || '仪表盘' }}</div>
        <div class="admin-user">
          <span class="admin-av">{{ store.displayName[0] }}</span>
          <span>{{ store.displayName }}</span>
          <button class="logout" @click="handleLogout">退出</button>
        </div>
      </header>
      <main class="admin-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAdminStore } from '../stores/admin'

const route = useRoute()
const router = useRouter()
const store = useAdminStore()

const navs = [
  { to: '/dashboard', label: '仪表盘', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 10h3l2-5 3 9 2-4h4"/></svg>' },
  { to: '/users', label: '用户', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="7" r="3"/><path d="M3 17c0-3 2.7-5 6-5s6 2 6 5"/></svg>' },
  { to: '/codes', label: '兑换码', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="14" height="10" rx="2"/><path d="M6 8h8M6 11h4"/></svg>' },
  { to: '/billing', label: '计费规则', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="7"/><path d="M10 6v8M8 8h4a2 2 0 010 4H8"/></svg>' },
  { to: '/roles', label: '角色管理', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="8" r="3"/><path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg>', badge: true },
  { to: '/stats', label: '数据统计', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 16V9M9 16V4M14 16v-5"/></svg>' },
  { to: '/settings', label: '系统设置', icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="2.5"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.5 4.5l1.4 1.4M14.1 14.1l1.4 1.4M4.5 15.5l1.4-1.4M14.1 5.9l1.4-1.4"/></svg>' },
]

function handleLogout() {
  store.logout()
  router.push('/login')
}
</script>
