<template>
  <div class="quickbar">
    <button v-for="item in items" :key="item.action" class="qa" @click="$emit('action', item.action)">
      {{ item.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({ items: Array })
defineEmits(['action'])
</script>
