<template>
  <div class="action-inline">
    <div v-if="prompt || candidateSummary" class="action-prompt">
      <div v-if="prompt">{{ prompt }}</div>
      <p v-if="candidateSummary">{{ candidateSummary }}</p>
    </div>
    <button
      v-for="(btn, index) in buttons"
      :key="`${btn.action}-${index}`"
      :disabled="processing"
      @click="$emit('action', btn)"
    >
      {{ processing ? '处理中...' : btn.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  buttons: Array,
  prompt: String,
  candidateSummary: String,
  processing: Boolean,
})
defineEmits(['action'])
</script>

<style scoped>
.action-prompt {
  flex: 1 0 100%;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,.72);
  border: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 13px;
  line-height: 1.45;
}
.action-prompt p {
  margin-top: 4px;
  color: var(--ink);
  font-size: 14px;
}
</style>
