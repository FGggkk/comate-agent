<template>
  <div class="flex flex-col h-full">
    <!-- SOUL Onboarding -->
    <div v-if="showOnboarding" class="scroll">
      <!-- ... onboarding unchanged ... -->
      <div v-if="onboardingStep === 'intro'" style="text-align:center;padding:20px 0;">
        <div class="hero-area">
          <div class="companion hero bob">
            <div class="companion-body">
              <span class="companion-eye l"></span>
              <span class="companion-eye r"></span>
              <span class="companion-cheek l"></span>
              <span class="companion-cheek r"></span>
              <span class="companion-mouth"></span>
            </div>
            <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
          </div>
        </div>
        <h2 style="font-size:20px;font-weight:700;margin:8px 0 4px;color:var(--ink);">选择你的陪伴伙伴</h2>
        <p style="font-size:14px;color:var(--sub);margin-bottom:20px;">每种风格都不同，你可以预览后再决定</p>
        <button @click="startOnboarding" class="btn-primary" style="max-width:200px;">开始选择</button>
      </div>
      <div v-else-if="onboardingStep === 'select'" style="display:flex;flex-direction:column;gap:10px;">
        <h3 style="font-size:16px;font-weight:600;margin-bottom:6px;">选择一种风格</h3>
        <div v-for="t in templates" :key="t.id"
          @click="selectedTemplate = t"
          :style="{padding:'14px',borderRadius:'var(--r-md)',border:'2px solid',cursor:'pointer',background: selectedTemplate?.id === t.id ? 'var(--sprout-soft)' : 'var(--card)', borderColor: selectedTemplate?.id === t.id ? '#7EC8A0' : 'var(--line)'}">
          <div style="font-weight:600;">{{ t.name }}</div>
          <div style="font-size:13px;color:var(--sub);margin-top:2px;">{{ t.slug }}</div>
        </div>
        <button @click="previewTemplate" :disabled="!selectedTemplate" class="btn-primary" style="margin-top:8px;">预览对话</button>
      </div>
      <div v-else-if="onboardingStep === 'preview'">
        <h3 style="font-size:16px;font-weight:600;margin-bottom:12px;">预览：{{ selectedTemplate?.name }}</h3>
        <div v-for="(msg, i) in previewMessages" :key="i">
          <MessageBubble :role="msg.role" :content="msg.content" />
        </div>
        <div style="display:flex;gap:10px;margin-top:14px;">
          <button @click="onboardingStep = 'select'" style="flex:1;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;color:var(--ink-soft);background:var(--card);">换一个</button>
          <button @click="confirmSoul" class="btn-primary" style="flex:1;">就这个了</button>
        </div>
      </div>
    </div>

    <!-- Chat -->
    <div v-else style="display:flex;flex-direction:column;height:100%;position:relative;">
      <!-- 会话列表遮罩 -->
      <div v-if="chatStore.showSessionList" class="session-overlay" @click="chatStore.closeSessionList()"></div>

      <!-- 会话列表侧栏 -->
      <div :class="['session-sidebar', chatStore.showSessionList ? 'open' : '']">
        <div class="session-sidebar-header">
          <span style="font-weight:700;font-size:15px;">历史对话</span>
          <button @click="chatStore.closeSessionList()" style="font-size:18px;color:var(--sub);padding:4px;">✕</button>
        </div>
        <button @click="newSession" class="session-new-btn">＋ 新对话</button>
        <div class="session-list">
          <div v-for="s in chatStore.sessions" :key="s.id"
            :class="['session-item', s.id === chatStore.currentSessionId ? 'active' : '']"
            @click="switchSession(s.id)">
            <div style="flex:1;overflow:hidden;">
              <div class="session-title">{{ s.title }}</div>
              <div class="session-time">{{ formatTime(s.updated_at) }}</div>
            </div>
            <button @click.stop="deleteSession(s.id)" class="session-del-btn" title="删除">🗑</button>
          </div>
          <div v-if="chatStore.sessions.length === 0" style="text-align:center;color:var(--sub);padding:20px;font-size:13px;">暂无对话记录</div>
        </div>
      </div>

      <!-- 顶部导航：会话按钮 + 当前标题 -->
      <div class="chat-topbar">
        <button @click="chatStore.toggleSessionList()" class="chat-menu-btn">☰</button>
        <div style="flex:1;text-align:center;font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
          {{ chatStore.currentSession?.title || '新对话' }}
        </div>
        <div style="width:32px;"></div>
      </div>

      <!-- 消息区 -->
      <div ref="scrollRef" style="flex:1;overflow-y:auto;padding:8px 14px;">
        <div v-if="chatStore.messages.length > 0" class="day-tag">{{ timeGreeting }}</div>

        <div v-for="(msg, i) in chatStore.messages" :key="i">
          <div v-if="shouldShowTimeSep(i)" class="day-tag">{{ formatTimeSep(msg.timestamp) }}</div>
          <MessageBubble v-if="msg.type === 'text'" :role="msg.role" :content="msg.content" />
          <MemoryCard v-else-if="msg.type === 'memory_card'" :summary="msg.summary" :layer="msg.layer" />
          <ActionButtons v-else-if="msg.type === 'actions'" :buttons="msg.buttons" @action="handleAction" />
        </div>

        <StatusIndicator v-if="chatStore.isStreaming" />

        <!-- 空状态 -->
        <div v-if="chatStore.messages.length === 0 && !chatStore.isStreaming" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;">
          <div :class="['companion', 'hero', heroSquished ? 'squish' : 'bob']" @click="squishHero" style="--s:80px;">
            <div class="companion-body">
              <span class="companion-eye l"></span>
              <span class="companion-eye r"></span>
              <span class="companion-cheek l"></span>
              <span class="companion-cheek r"></span>
              <span class="companion-mouth"></span>
            </div>
            <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
          </div>
          <div style="font-size:12px;color:#A89C88;margin-top:10px;background:rgba(255,255,255,.6);padding:5px 13px;border-radius:14px;">戳一下试试 👆</div>
        </div>
      </div>

      <!-- 底部 -->
      <QuickBar :items="quickItems" />
      <InputBar :disabled="chatStore.isStreaming" @send="handleSend" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useUserStore } from '../stores/user'
import { apiGetTemplates, apiPreview, apiConfirmSoul, apiSendMessage, apiListSessions, apiCreateSession, apiDeleteSession, apiGetMessages } from '../api/index'
import MessageBubble from '../components/MessageBubble.vue'
import MemoryCard from '../components/MemoryCard.vue'
import ActionButtons from '../components/ActionButtons.vue'
import StatusIndicator from '../components/StatusIndicator.vue'
import InputBar from '../components/InputBar.vue'
import QuickBar from '../components/QuickBar.vue'

const chatStore = useChatStore()
const userStore = useUserStore()
const scrollRef = ref(null)
const showOnboarding = ref(userStore.needsOnboarding)
const onboardingStep = ref('intro')
const templates = ref([])
const selectedTemplate = ref(null)
const previewMessages = ref([])
const heroSquished = ref(false)
const quickItems = [
  { label: '🔍 帮我分析', action: 'analyze' },
  { label: '📌 设定提醒', action: 'remind' },
  { label: '🎯 模拟面试', action: 'interview' },
]

const emit = defineEmits(['tab-change'])

function squishHero() {
  heroSquished.value = true
  setTimeout(() => { heroSquished.value = false }, 450)
}

// ── 会话管理 ──

async function loadSessions() {
  try {
    const res = await apiListSessions()
    if (res.sessions) chatStore.setSessions(res.sessions)
  } catch {}
}

async function loadMessages(sessionId) {
  if (!sessionId) return
  chatStore.clearHistory()
  try {
    const res = await apiGetMessages(sessionId)
    if (res.messages) {
      for (const m of res.messages) {
        if (m.type === 'text') {
          chatStore.addMessage({ type: 'text', role: m.role, content: m.content })
        }
      }
    }
  } catch {}
  nextTick(() => scrollToBottom())
}

async function newSession() {
  try {
    const res = await apiCreateSession('新对话')
    if (res.id) {
      chatStore.setCurrentSession(res.id)
      chatStore.clearHistory()
      chatStore.replaceSessions({ id: res.id, title: '新对话', updated_at: new Date().toISOString() })
      chatStore.closeSessionList()
    }
  } catch {}
}

async function switchSession(id) {
  chatStore.setCurrentSession(id)
  await loadMessages(id)
  chatStore.closeSessionList()
}

async function deleteSession(id) {
  if (!confirm('确定删除这个对话吗？')) return
  try {
    await apiDeleteSession(id)
    chatStore.removeSession(id)
    if (chatStore.currentSessionId === id) {
      chatStore.setCurrentSession('')
      chatStore.clearHistory()
      // 切到第一个会话
      if (chatStore.sessions.length > 0) {
        await switchSession(chatStore.sessions[0].id)
      }
    }
  } catch {}
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 86400000) return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  return `${d.getMonth()+1}月${d.getDate()}日`
}

// ── 对话 ──

function handleAction(action) {
  if (action === 'interview') emit('tab-change', 'interview')
  else if (action === 'remind') emit('tab-change', 'settings')
  else handleSend('帮我分析一下')
}

async function handleSend(text) {
  // 确保有会话
  let sessionId = chatStore.currentSessionId
  if (!sessionId) {
    const res = await apiCreateSession('新对话')
    if (res.id) {
      sessionId = res.id
      chatStore.setCurrentSession(sessionId)
      chatStore.replaceSessions({ id: sessionId, title: '新对话', updated_at: new Date().toISOString() })
    }
  }

  chatStore.addMessage({ type: 'text', role: 'user', content: text })
  chatStore.setStreaming(true)
  chatStore.addMessage({ type: 'text', role: 'agent', content: '' })
  try {
    const response = await apiSendMessage(text, sessionId)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      chatStore.addMessage({ type: 'text', role: 'agent', content: err.detail || '请求失败，请重新登录' })
      chatStore.finishStream()
      return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'memory_card') {
            chatStore.addMessage({ type: 'memory_card', summary: event.data.summary, layer: event.data.layer })
          } else if (event.type === 'text_chunk') {
            chatStore.appendToStream(event.data.text)
          } else if (event.type === 'action_buttons') {
            chatStore.addMessage({ type: 'actions', buttons: event.data.buttons })
          }
        } catch { continue }
      }
      nextTick(() => scrollToBottom())
    }
  } catch { chatStore.addMessage({ type: 'text', role: 'agent', content: '嗯，我在听。能再多说一点吗？' }) }
  finally {
    chatStore.finishStream()
    // 刷新会话列表
    loadSessions()
    nextTick(() => scrollToBottom())
  }
}

// ── 页面初始化 ──

onMounted(async () => {
  if (userStore.needsOnboarding) {
    templates.value = await apiGetTemplates()
    return
  }
  await loadSessions()
  if (chatStore.currentSessionId) {
    await loadMessages(chatStore.currentSessionId)
  } else if (chatStore.sessions.length > 0) {
    await switchSession(chatStore.sessions[0].id)
  }
})

function startOnboarding() { onboardingStep.value = 'select' }

async function previewTemplate() {
  if (!selectedTemplate.value) return
  onboardingStep.value = 'preview'
  const res = await apiPreview(selectedTemplate.value.slug)
  previewMessages.value = res.messages || []
}

async function confirmSoul() {
  if (!selectedTemplate.value) return
  await apiConfirmSoul(selectedTemplate.value.id)
  userStore.completeOnboarding()
  showOnboarding.value = false
  // 初始化加载
  await loadSessions()
}

const timeGreeting = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}年${now.getMonth()+1}月${now.getDate()}日 ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
})

function shouldShowTimeSep(i) {
  if (i === 0) return false
  const prev = chatStore.messages[i - 1]
  const curr = chatStore.messages[i]
  if (!prev.timestamp || !curr.timestamp) return false
  return (curr.timestamp - prev.timestamp) > 120000
}

function formatTimeSep(ts) {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function scrollToBottom() { if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight }
</script>

<style scoped>
/* 会话侧栏 */
.chat-topbar {
  display: flex; align-items: center; padding: 6px 10px;
  border-bottom: 1px solid var(--line); flex-shrink: 0;
  background: rgba(255,255,255,.6);
}
.chat-menu-btn {
  width: 32px; height: 32px; display: flex; align-items: center;
  justify-content: center; font-size: 18px; color: var(--ink-soft);
  border-radius: 8px;
}
.chat-menu-btn:active { background: var(--line); }

.session-overlay {
  position: absolute; inset: 0; z-index: 30;
  background: rgba(0,0,0,.25);
}
.session-sidebar {
  position: absolute; left: 0; top: 0; bottom: 0; width: 280px;
  z-index: 31; background: var(--card); box-shadow: 4px 0 20px rgba(0,0,0,.12);
  transform: translateX(-100%); transition: transform .25s ease;
  display: flex; flex-direction: column;
}
.session-sidebar.open { transform: translateX(0); }
.session-sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 14px 8px;
}
.session-new-btn {
  margin: 4px 12px 8px; padding: 8px; border-radius: var(--r-sm);
  background: var(--honey-soft); color: var(--honey-deep);
  font-size: 13px; font-weight: 600; text-align: center;
}
.session-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.session-item {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 10px; border-radius: var(--r-sm);
  cursor: pointer; margin-bottom: 2px;
}
.session-item:active { background: var(--cream-2); }
.session-item.active { background: var(--honey-soft); }
.session-title { font-size: 14px; font-weight: 500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.session-time { font-size: 11px; color: var(--sub); margin-top: 1px; }
.session-del-btn { font-size: 14px; padding: 4px; opacity: .4; }
.session-del-btn:active { opacity: 1; }
</style>