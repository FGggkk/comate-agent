import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const streamBuffer = ref('')

  function addMessage(msg) {
    messages.value.push({ ...msg, timestamp: Date.now() })
  }

  function setStreaming(val) {
    isStreaming.value = val
  }

  function appendToStream(text) {
    streamBuffer.value += text
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'agent') {
      last.content = streamBuffer.value
    }
  }

  function finishStream() {
    isStreaming.value = false
    streamBuffer.value = ''
  }

  function clearHistory() {
    messages.value = []
  }

  return { messages, isStreaming, streamBuffer, addMessage, setStreaming, appendToStream, finishStream, clearHistory }
})
