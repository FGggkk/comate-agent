<template>
  <div class="memory-inline">
    <div class="inner">
      <span class="tag">{{ layerLabel }}</span>
      <span>{{ summary }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ summary: String, layer: String })
const layerLabel = computed(() => {
  const map = { priors: '系统', co_created: '我记得', tacit: '默契', anchor: '上次提到' }
  return map[props.layer] || '记忆'
})
</script>
