import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAdminStore = defineStore('admin', () => {
  const token = ref(localStorage.getItem('admin_token') || '')
  const admin = ref(null)

  const isLoggedIn = computed(() => !!token.value)
  const displayName = computed(() => admin.value?.nickname || admin.value?.email?.split('@')[0] || '管理员')

  function login(t, adminInfo) {
    token.value = t
    admin.value = adminInfo
    localStorage.setItem('admin_token', t)
  }

  function setAdmin(info) {
    admin.value = info
  }

  function logout() {
    token.value = ''
    admin.value = null
    localStorage.removeItem('admin_token')
  }

  return { token, admin, isLoggedIn, displayName, login, setAdmin, logout }
})
