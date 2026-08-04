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
    const storedMessage = { ...msg, timestamp: msg.timestamp || Date.now() }
    messages.value.push(storedMessage)
    return storedMessage
  }

  function attachMessageId(payload) {
    if (!payload?.role || !payload?.id) return
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if ((m.type === 'text' || m.type === 'company_knowledge') && m.role === payload.role && !m.id) {
        m.id = payload.id
        return
      }
    }
  }

  function addThinkingMemory(memory) {
    const trace = [...messages.value].reverse().find(m => m.type === 'thinking_trace' && m.active)
    const item = {
      summary: memory.summary,
      layer: memory.layer,
    }
    if (trace) {
      const exists = trace.memories?.some(m => m.summary === item.summary && m.layer === item.layer)
      if (!exists) trace.memories.push(item)
      return
    }
    messages.value.push({
      type: 'thinking_trace',
      active: true,
      collapsed: false,
      memories: [item],
      timestamp: Date.now(),
    })
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

  function setLastAgentSoul(soul) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const m = messages.value[i]
      if (m.role === 'agent') {
        m.soul = soul
        break
      }
    }
  }

  function finishStream() {
    isStreaming.value = false
    streamBuffer.value = ''
    messages.value.forEach((m) => {
      if (m.type === 'thinking_trace' && m.active) {
        m.active = false
        m.collapsed = true
      }
    })
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
    addMessage, attachMessageId, addThinkingMemory, setStreaming, appendToStream, setLastAgentSoul, finishStream, clearHistory,
    setSessions, setCurrentSession, toggleSessionList, closeSessionList,
    replaceSessions, removeSession,
  }
})
