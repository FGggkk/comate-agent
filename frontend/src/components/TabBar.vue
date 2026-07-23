<template>
  <nav class="tabbar">
    <button v-for="t in tabs" :key="t.id" :class="['tab', active === t.id ? 'active' : '']" @click="$emit('tab-change', t.id)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" v-html="t.icon"></svg>
      <span>{{ t.label }}</span>
      <div class="dot"></div>
    </button>
  </nav>
</template>

<script setup>
defineProps({ active: String })
defineEmits(['tab-change'])
const tabs = [
  {
    id: 'chat',
    label: '聊聊',
    icon: '<path d="M21 11.5a8.38 8.38 0 01-9 8.4 9 9 0 01-4-1L3 20l1.1-4.5A8.38 8.38 0 0112 3a8.5 8.5 0 019 8.5z"/>',
  },
  {
    id: 'memory',
    label: '记忆',
    icon: '<path d="M4 5a2 2 0 012-2h12a2 2 0 012 2v16l-4-3-4 3-4-3-4 3V5z"/>',
  },
  {
    id: 'interview',
    label: '面试',
    icon: '<path d="M12 2a4 4 0 0 0-4 4c0 2 2 3 2 6H14c0-3 2-4 2-6a4 4 0 0 0-4-4z"/><path d="M10 17v1a2 2 0 1 0 4 0v-1"/><line x1="10" y1="13" x2="14" y2="13"/>',
  },
  {
    id: 'settings',
    label: '设置',
    icon: '<circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
  },
]
</script>
