import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const streamBuffer = ref('')
  const sessions = ref([])
  const currentSessionId = ref(localStorage.getItem('comate_session_id') || '')
  const showSessionList = ref(false)

  const currentSession = computed(() => {
    return sessions.value.find(s => s.id === currentSessionId.value) || null
  })

  function addMessage(msg) {
    messages.value.push({ ...msg, timestamp: Date.now() })
  }

  function setStreaming(val) {
    isStreaming.value = val
  }

  function appendToStream(text) {
    streamBuffer.value += text
    // 找到最后一个 agent 消息（可能被 memory_card 等隔开）
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.role === 'agent') {
        m.content = streamBuffer.value
        break
      }
    }
  }

  function finishStream() {
    isStreaming.value = false
    streamBuffer.value = ''
  }

  function clearHistory() {
    messages.value = []
  }

  function setSessions(list) {
    sessions.value = list
  }

  function setCurrentSession(id) {
    currentSessionId.value = id
    localStorage.setItem('comate_session_id', id || '')
  }

  function toggleSessionList() {
    showSessionList.value = !showSessionList.value
  }

  function closeSessionList() {
    showSessionList.value = false
  }

  function replaceSessions(session) {
    const idx = sessions.value.findIndex(s => s.id === session.id)
    if (idx >= 0) {
      sessions.value[idx] = session
    } else {
      sessions.value.unshift(session)
    }
  }

  function removeSession(id) {
    sessions.value = sessions.value.filter(s => s.id !== id)
  }

  return {
    messages, isStreaming, streamBuffer, sessions, currentSessionId, showSessionList, currentSession,
    addMessage, setStreaming, appendToStream, finishStream, clearHistory,
    setSessions, setCurrentSession, toggleSessionList, closeSessionList,
    replaceSessions, removeSession,
  }
})