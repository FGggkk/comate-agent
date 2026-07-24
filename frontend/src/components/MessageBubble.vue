<template>
  <div :class="role === 'user' ? 'msg-user' : 'msg-bot'">
    <div v-if="role === 'agent'" :class="['companion', squished ? 'squish' : 'bob']" style="--s:28px;flex-shrink:0;" @click="squishIt">
      <div class="companion-body">
        <span class="companion-eye l"></span>
        <span class="companion-eye r"></span>
        <span class="companion-cheek l"></span>
        <span class="companion-cheek r"></span>
        <span class="companion-mouth"></span>
      </div>
      <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
    </div>
    <div style="position:relative;" @mouseenter="hover=true" @mouseleave="hover=false">
      <div :class="role === 'user' ? 'bubble-user' : 'bubble-bot'">{{ content }}</div>
      <!-- 用户消息 hover 操作 -->
      <div v-if="role === 'user' && hover" class="msg-actions">
        <button @click="$emit('edit', content)" class="msg-action-btn">编辑</button>
        <button @click="$emit('delete')" class="msg-action-btn" style="color:var(--berry);">删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({ role: String, content: String })
defineEmits(['edit', 'delete'])
const squished = ref(false)
const hover = ref(false)
function squishIt() {
  squished.value = true
  setTimeout(() => { squished.value = false }, 450)
}
</script>

<style scoped>
.msg-actions {
  position: absolute; top: -22px; right: 0; display: flex; gap: 2px;
  background: var(--card); border-radius: 8px; padding: 2px 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10;
}
.msg-action-btn {
  font-size: 11px; padding: 2px 6px; border-radius: 4px;
  color: var(--ink-soft);
}
.msg-action-btn:active { background: var(--cream-2); }
</style>