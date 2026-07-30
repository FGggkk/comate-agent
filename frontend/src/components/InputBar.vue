<template>
  <div class="flex items-center gap-2 px-3 py-2 inputbar">
    <textarea
      ref="inputRef"
      v-model="text"
      rows="1"
      @input="resizeInput"
      @keydown.enter.exact.prevent="send"
      placeholder="说点什么…"
      :disabled="disabled"
    />
    <button @click="send" :disabled="disabled || !text.trim()" class="send-btn">
      <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    </button>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'

const props = defineProps({ disabled: Boolean })
const emit = defineEmits(['send'])
const text = ref('')
const inputRef = ref(null)

function send() {
  if (!text.value.trim() || props.disabled) return
  emit('send', text.value)
  text.value = ''
  nextTick(resizeInput)
}

function focus() {
  nextTick(() => inputRef.value?.focus())
}

function resizeInput() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

function applyDraft(draft, options = {}) {
  if (props.disabled) return
  const prompt = draft || ''
  if (!text.value.trim() || options.mode === 'replace') {
    text.value = prompt
  } else if (!text.value.startsWith(prompt)) {
    text.value = `${prompt}\n\n${text.value}`
  }
  nextTick(() => {
    resizeInput()
    inputRef.value?.focus()
  })
}

defineExpose({ focus, applyDraft })
</script>
