<template>
  <div :class="role === 'user' ? 'msg-user' : 'msg-bot'">
    <SoulOrb v-if="role === 'agent'" :template="soul || {}" size="xs" class="message-soul-orb" />
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
import SoulOrb from './SoulOrb.vue'

defineProps({
  role: String,
  content: String,
  soul: { type: Object, default: null },
})
defineEmits(['edit', 'delete'])
const hover = ref(false)
</script>

<style scoped>
.message-soul-orb {
  flex-shrink: 0;
  align-self: flex-end;
  margin-bottom: 2px;
  animation: message-orb-bob 3.2s ease-in-out infinite;
}
@keyframes message-orb-bob {
  0%,100% { transform: translateY(0) rotate(-1deg); }
  50% { transform: translateY(-3px) rotate(1deg); }
}
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
