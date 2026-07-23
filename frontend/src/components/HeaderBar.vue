<template>
  <div class="flex items-center justify-between px-4 py-3 border-b bg-white">
    <div class="flex items-center gap-2">
      <div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center text-sm">🌱</div>
      <div>
        <div class="font-semibold text-sm">伴行agent</div>
        <div class="text-xs text-green-500">在线</div>
      </div>
    </div>
    <div class="flex items-center gap-3">
      <span class="text-xs text-gray-400 bg-gray-50 px-2 py-1 rounded-full">v1</span>
      <div class="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-sm">{{ userEmail[0] }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '../stores/user'
const userStore = useUserStore()
const userEmail = computed(() => userStore.email || 'U')
</script>
