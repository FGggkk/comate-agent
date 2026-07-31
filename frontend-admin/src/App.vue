<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from './stores/admin'
import { apiAdminMe } from './api'

const store = useAdminStore()
const router = useRouter()

onMounted(async () => {
  if (!store.isLoggedIn) return
  try {
    const res = await apiAdminMe()
    if (res.success) store.setAdmin(res.admin)
    else { store.logout(); router.push('/login') }
  } catch {
    store.logout()
  }
})
</script>
