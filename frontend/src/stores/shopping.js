import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'comate_shopping'

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {}
}

export const useShoppingStore = defineStore('shopping', () => {
  const saved = loadSaved()

  const messages = ref(saved?.messages || [
    { role: 'assistant', content: '嗨！告诉我你想买什么，我来帮你搜实时价格、出方案 😊\n比如 *"5000预算配电脑"* 或 *"推荐个3000左右的手机"*' }
  ])
  
  const progress = ref(saved?.progress || {
    status: '',
    phase: '',
    parts: [],
    results: [],
    current: 0,
    total: 0,
    message: ''
  })
  
  const currentPlans = ref(saved?.currentPlans || null)
  const currentTaskId = ref(saved?.currentTaskId || '')
  const activeTab = ref(saved?.activeTab || 'chat')
  const demand = ref(saved?.demand || '')
  const savedFlag = ref(false)

  const progressPct = computed(() => {
    const p = progress.value
    if (p.total === 0) return 0
    return (p.results.length / p.total) * 100
  })

  let _evtSource = null

  // 自动持久化到 localStorage
  function persist() {
    saveState({
      messages: messages.value,
      progress: progress.value,
      currentPlans: currentPlans.value,
      currentTaskId: currentTaskId.value,
      activeTab: activeTab.value,
      demand: demand.value,
      savedFlag: savedFlag.value,
    })
  }

  // 关键状态变化时自动保存
  watch([messages, progress, currentPlans, currentTaskId], persist, { deep: true })

  function addMessage(role, content, extra = {}) {
    messages.value.push({ role, content, ...extra })
  }

  function clearMessages() {
    messages.value = [
      { role: 'assistant', content: '嗨！告诉我你想买什么，我来帮你搜实时价格、出方案 😊\n比如 *"5000预算配电脑"* 或 *"推荐个3000左右的手机"*' }
    ]
    persist()
  }

  function setProgress(status, data = {}) {
    progress.value = { ...progress.value, status, ...data }
  }

  function connectSSE(taskId) {
    startPolling()
    disconnectSSE()
    currentTaskId.value = taskId
    const evtUrl = `/api/shopping/progress/${taskId}`
    _evtSource = new EventSource(evtUrl)

    _evtSource.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)
        if (evt.type === 'analyzed') {
          progress.value.parts = evt.data.items
          progress.value.total = evt.data.items.length
          progress.value.status = 'searching'
          progress.value.phase = 'searching'
        } else if (evt.type === 'found') {
          progress.value.results.push(evt.data)
        } else if (evt.type === 'complete') {
          currentPlans.value = evt.data
          progress.value.status = 'done'
          currentTaskId.value = ''
          _evtSource?.close()
          _evtSource = null
        } else if (evt.type === 'error') {
          progress.value.status = 'error'
          progress.value.message = evt.data.message
          currentTaskId.value = ''
          _evtSource?.close()
          _evtSource = null
        } else if (evt.type === 'done') {
          _evtSource?.close()
          _evtSource = null
        } else if (evt.type === 'status' && evt.data?.phase === 'building') {
          progress.value.phase = 'building'
          progress.value.status = 'building'
        } else if (evt.type === 'status' && evt.data?.message) {
          progress.value.message = evt.data.message
        }
      } catch {}
    }
    _evtSource.onerror = () => {
      // 断线不立即报错，后台任务还在跑，下次刷新可重连
    }
  }

  function disconnectSSE() {
    if (_evtSource) {
      _evtSource.close()
      _evtSource = null
    }
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
  }

  let _pollTimer = null

  function startPolling() {
    if (_pollTimer) clearInterval(_pollTimer)
    _pollTimer = setInterval(() => {
      if (progress.value.status === 'done' || progress.value.status === 'error') {
        clearInterval(_pollTimer)
        _pollTimer = null
      }
    }, 3000)
  }

  function hasActiveTask() {
    return currentTaskId.value && 
      (progress.value.status === 'analyzing' || 
       progress.value.status === 'searching' || 
       progress.value.status === 'building')
  }

  function reset() {
    disconnectSSE()
    progress.value = { status: '', phase: '', parts: [], results: [], current: 0, total: 0, message: '' }
    currentPlans.value = null
    currentTaskId.value = ''
    demand.value = ''
    savedFlag.value = false
    localStorage.removeItem(STORAGE_KEY)
  }

  return {
    messages, progress, currentPlans, currentTaskId, activeTab, demand, progressPct, savedFlag,
    addMessage, clearMessages, setProgress, connectSSE, disconnectSSE, hasActiveTask, reset, startPolling
  }
})
