<template>
  <div class="flex items-center gap-2 px-3 py-2 inputbar">
    <input
      v-model="text"
      @keydown.enter="send"
      placeholder="说点什么…"
      :disabled="disabled"
    />
    <button @click="send" :disabled="disabled || !text.trim()" class="send-btn">
      <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({ disabled: Boolean })
const emit = defineEmits(['send'])
const text = ref('')

function send() {
  if (!text.value.trim() || props.disabled) return
  emit('send', text.value)
  text.value = ''
}
</script>
