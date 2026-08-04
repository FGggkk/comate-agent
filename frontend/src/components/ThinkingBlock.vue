<template>
  <div class="thinking-block">
    <button class="thinking-toggle" :class="{ expanded }" @click="expanded = !expanded">
      <span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="thinking-label">{{ thinking.stage || '伴行正在思考…' }}</span>
      <span v-if="memories.length" class="thinking-count">{{ memories.length }} 条线索</span>
      <span class="thinking-caret">{{ expanded ? '收起' : '展开' }}</span>
    </button>
    <div v-if="expanded" class="thinking-body">
      <div v-if="thinking.text" class="thinking-reasoning">{{ thinking.text }}</div>
      <div v-if="memories.length" class="thinking-memories">
        <MemoryCard
          v-for="(memory, memoryIndex) in memories"
          :key="`${memory.layer}-${memory.summary}-${memoryIndex}`"
          :summary="memory.summary"
          :layer="memory.layer"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MemoryCard from './MemoryCard.vue'

defineProps({
  thinking: { type: Object, default: () => ({ active: false, stage: '', text: '' }) },
  memories: { type: Array, default: () => [] },
})
const expanded = ref(false)
</script>

<style scoped>
.thinking-block {
  margin: 4px 0 6px;
  max-width: 86%;
}
.thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.045);
  border: 1px solid rgba(0, 0, 0, 0.05);
  color: #8a8171;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}
.thinking-toggle:hover {
  background: rgba(0, 0, 0, 0.07);
}
.thinking-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.thinking-dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #b9b0a0;
  animation: thinking-blink 1.2s infinite ease-in-out;
}
.thinking-dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.thinking-dots i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes thinking-blink {
  0%, 100% { opacity: 0.25; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-1px); }
}
.thinking-count {
  font-size: 11px;
  color: #a99e8c;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  padding: 1px 7px;
}
.thinking-caret {
  font-size: 11px;
  color: #b3a99a;
}
.thinking-body {
  margin-top: 6px;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.04);
}
.thinking-reasoning {
  font-size: 12px;
  line-height: 1.7;
  color: #a49a88;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 6px;
}
.thinking-memories {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
