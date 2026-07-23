<template>
  <div class="statusbar">
    <div class="num">{{ time }}</div>
    <div class="flex items-center gap-1">
      <svg width="17" height="12" viewBox="0 0 20 14"><rect x="1" y="10" width="3" height="4" rx="1" fill="#2E2A24"/><rect x="6" y="7" width="3" height="7" rx="1" fill="#2E2A24"/><rect x="11" y="4" width="3" height="10" rx="1" fill="#2E2A24"/><rect x="16" y="1" width="3" height="13" rx="1" fill="#2E2A24"/></svg>
      <span class="battery num" style="font-size:10px;background:#2E2A24;color:#8AD583;padding:1px 6px;border-radius:4px;">76</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const time = ref('20:14')
onMounted(() => {
  const d = new Date()
  time.value = String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
  setInterval(() => {
    const d = new Date()
    time.value = String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0')
  }, 30000)
})
</script>
