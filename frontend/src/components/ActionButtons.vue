<template>
  <div class="action-inline">
    <button v-for="btn in buttons" :key="btn.action" @click="$emit('action', btn.action)">
      {{ btn.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({ buttons: Array })
defineEmits(['action'])
</script>
