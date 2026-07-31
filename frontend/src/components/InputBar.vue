<template>
  <div class="flex items-center gap-2 px-3 py-2 inputbar">
    <textarea
      ref="inputRef"
      v-model="text"
      rows="1"
      @input="resizeInput"
      @keydown.enter.exact.prevent="send"
      placeholder="说点什么…"
      :disabled="disabled || voiceState !== 'idle'"
    />
    <button
      :class="['voice-btn', `is-${voiceState}`]"
      :disabled="disabled && voiceState === 'idle'"
      :title="voiceButtonLabel"
      :aria-label="voiceButtonLabel"
      @click="toggleVoice"
    >
      <svg v-if="voiceState === 'recording' || voiceState === 'responding'" viewBox="0 0 24 24">
        <rect x="7" y="7" width="10" height="10" rx="1.5" />
      </svg>
      <svg v-else viewBox="0 0 24 24">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" />
      </svg>
    </button>
    <button @click="send" :disabled="disabled || !text.trim()" class="send-btn">
      <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  disabled: Boolean,
  voiceState: { type: String, default: 'idle' },
})
const emit = defineEmits(['send', 'voice'])
const text = ref('')
const inputRef = ref(null)

const voiceButtonLabel = computed(() => {
  if (props.voiceState === 'recording') return '结束录音'
  if (props.voiceState === 'responding') return '停止语音回复'
  if (props.voiceState === 'connecting') return '正在连接语音服务'
  return '开始语音输入'
})

function send() {
  if (!text.value.trim() || props.disabled) return
  emit('send', text.value)
  text.value = ''
  nextTick(resizeInput)
}

function toggleVoice() {
  if (props.disabled && props.voiceState === 'idle') return
  emit('voice')
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
