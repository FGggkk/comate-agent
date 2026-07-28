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
          <MessageBubble :role="msg.role" :content="msg.content" :soul="selectedTemplate" />
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
              <div style="display:flex;align-items:center;gap:4px;">
                <input v-if="renamingSessionId === s.id" v-model="renameText" @keydown.enter="confirmRename(s)" @blur="confirmRename(s)" @click.stop class="session-rename-input" autofocus />
                <div v-else class="session-title">{{ s.title }}</div>
                <button v-if="renamingSessionId !== s.id" @click.stop="startRename(s)" class="session-rename-btn" title="重命名">✏️</button>
              </div>
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
          <MessageBubble
            v-if="msg.type === 'text'"
            :role="msg.role"
            :content="msg.content"
            :soul="msg.soul || {}"
            @edit="startEdit(msg,i)"
            @delete="confirmDelete(msg,i)"
          />
          <MemoryCard v-else-if="msg.type === 'memory_card'" :summary="msg.summary" :layer="msg.layer" />
          <ActionButtons
            v-else-if="msg.type === 'actions' && !msg.handled"
            :buttons="msg.buttons"
            :prompt="msg.prompt"
            :candidate-summary="msg.candidateSummary"
            :processing="msg.processing"
            @action="handleAction($event, msg)"
          />
          <div v-else-if="msg.type === 'error'" class="error-msg">
            <span style="color:#e74c3c;font-size:13px;">⚠ {{ msg.content }}</span>
          </div>
        </div>

        <StatusIndicator v-if="chatStore.isStreaming" />

        <!-- 空状态 -->
        <div v-if="chatStore.messages.length === 0 && !chatStore.isStreaming" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;">
          <button :class="['chat-hero-orb', heroSquished ? 'squish' : '']" @click="squishHero" aria-label="戳一下伴行">
            <SoulOrb :template="activeSoul || {}" size="lg" />
          </button>
          <div style="font-size:12px;color:#A89C88;margin-top:10px;background:rgba(255,255,255,.6);padding:5px 13px;border-radius:14px;">戳一下试试 👆</div>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div v-if="editingMsgIndex >= 0" class="edit-bar">
        <div style="flex:1;display:flex;gap:6px;">
          <input v-model="editingText" @keydown.enter="confirmEdit" class="form-input" style="flex:1;" placeholder="编辑消息..." autofocus />
          <button @click="confirmEdit" class="btn-primary" style="width:auto;padding:10px 14px;font-size:13px;">发送</button>
          <button @click="cancelEdit" style="padding:10px 14px;font-size:13px;color:var(--sub);">取消</button>
        </div>
      </div>

      <!-- 底部 -->
      <QuickBar :items="quickItems" @action="handleQuickAction" />
      <InputBar v-if="editingMsgIndex < 0" :disabled="chatStore.isStreaming" @send="handleSend" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useUserStore } from '../stores/user'
import { apiGetTemplates, apiPreview, apiConfirmSoul, apiSendMessage, apiListSessions, apiCreateSession, apiDeleteSession, apiGetMessages, apiEditMessage, apiDeleteMessage, apiUpdateSession, apiGetSoulInventory, apiCreateMemory, apiCreateMemoryReminder } from '../api/index'
import MessageBubble from '../components/MessageBubble.vue'
import MemoryCard from '../components/MemoryCard.vue'
import ActionButtons from '../components/ActionButtons.vue'
import StatusIndicator from '../components/StatusIndicator.vue'
import InputBar from '../components/InputBar.vue'
import QuickBar from '../components/QuickBar.vue'
import SoulOrb from '../components/SoulOrb.vue'

const props = defineProps({
  currentSoul: { type: Object, default: null },
})

const chatStore = useChatStore()
const userStore = useUserStore()
const scrollRef = ref(null)
const showOnboarding = ref(userStore.needsOnboarding)
const onboardingStep = ref('intro')
const templates = ref([])
const selectedTemplate = ref(null)
const previewMessages = ref([])
const heroSquished = ref(false)
const activeSoul = computed(() => props.currentSoul || null)
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

function snapshotSoul(soul) {
  return soul ? JSON.parse(JSON.stringify(soul)) : null
}

async function getReplySoulSnapshot() {
  try {
    const res = await apiGetSoulInventory()
    return snapshotSoul(res.current || activeSoul.value)
  } catch {
    return snapshotSoul(activeSoul.value)
  }
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
  const soulByMessageId = new Map(
    chatStore.messages
      .filter((m) => m.id && m.soul)
      .map((m) => [m.id, m.soul])
  )
  chatStore.clearHistory()
  try {
    const res = await apiGetMessages(sessionId)
    if (res.messages) {
      for (const m of res.messages) {
        if (m.type === 'text') {
          chatStore.addMessage({
            id: m.id,
            type: 'text',
            role: m.role,
            content: m.content,
            soul: m.metadata?.soul || soulByMessageId.get(m.id) || null,
            timestamp: m.created_at ? new Date(m.created_at).getTime() : undefined,
          })
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

function formatTimeSep(ts) {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function shouldShowTimeSep(i) {
  if (i === 0) return false
  const prev = chatStore.messages[i - 1]
  const curr = chatStore.messages[i]
  if (!prev.timestamp || !curr.timestamp) return false
  return (curr.timestamp - prev.timestamp) > 120000
}

// ── 对话 ──

function handleQuickAction(action) {
  if (action === 'analyze') handleSend('帮我分析一下')
  else if (action === 'remind') emit('tab-change', 'settings')
  else if (action === 'interview') emit('tab-change', 'interview')
}

async function handleAction(payload, actionMessage = null) {
  const action = typeof payload === 'string' ? payload : payload?.action
  if (action === 'confirm_memory_candidate') {
    if (actionMessage?.processing || actionMessage?.handled) return
    if (actionMessage) {
      actionMessage.processing = true
      actionMessage.handled = true
    }
    const candidate = payload?.candidate
    if (!candidate?.summary) {
      if (actionMessage) {
        actionMessage.processing = false
        actionMessage.handled = false
      }
      return
    }
    try {
      const res = await apiCreateMemory({
        summary: candidate.summary,
        memory_type: candidate.memory_type || 'general',
        content: candidate.content || {},
      })
      const failed = res?.success === false
      if (actionMessage) actionMessage.handled = true
      chatStore.addMessage({
        type: 'text',
        role: 'agent',
        content: failed ? (res.message || '这条记忆保存失败了，稍后再试。') : '好，我记住了。',
        soul: snapshotSoul(activeSoul.value),
      })
      if (!failed && res?.reminder_candidate) {
        chatStore.addMessage({
          type: 'actions',
          prompt: '这件事有时间点，要不要我提前提醒你？',
          candidateSummary: res.reminder_candidate.label || res.reminder_candidate.content,
          buttons: [
            { label: '需要提醒', action: 'confirm_event_reminder', memory_id: res.id },
            { label: '只记住，不提醒', action: 'dismiss_event_reminder' },
          ],
        })
      }
    } catch {
      chatStore.addMessage({
        type: 'text',
        role: 'agent',
        content: '这条记忆保存失败了，稍后可以在记忆页手动添加。',
        soul: snapshotSoul(activeSoul.value),
      })
    } finally {
      if (actionMessage) actionMessage.processing = false
      nextTick(() => scrollToBottom())
    }
    return
  }
  if (action === 'dismiss_memory_candidate') {
    if (actionMessage?.processing || actionMessage?.handled) return
    if (actionMessage) actionMessage.handled = true
    chatStore.addMessage({
      type: 'text',
      role: 'agent',
      content: '好的，这条我先不记。',
      soul: snapshotSoul(activeSoul.value),
    })
    nextTick(() => scrollToBottom())
    return
  }
  if (action === 'confirm_event_reminder') {
    if (actionMessage?.processing || actionMessage?.handled) return
    if (!payload?.memory_id) return
    if (actionMessage) {
      actionMessage.processing = true
      actionMessage.handled = true
    }
    try {
      const res = await apiCreateMemoryReminder(payload?.memory_id)
      const failed = res?.success === false
      const reminderTime = failed ? '' : formatTime(res?.reminder?.remind_at)
      chatStore.addMessage({
        type: 'text',
        role: 'agent',
        content: failed ? (res.message || '提醒创建失败了，稍后可以在设置页手动添加。') : `好，我会在${reminderTime}提醒你。`,
        soul: snapshotSoul(activeSoul.value),
      })
    } catch {
      chatStore.addMessage({
        type: 'text',
        role: 'agent',
        content: '提醒创建失败了，稍后可以在设置页手动添加。',
        soul: snapshotSoul(activeSoul.value),
      })
    } finally {
      if (actionMessage) actionMessage.processing = false
      nextTick(() => scrollToBottom())
    }
    return
  }
  if (action === 'dismiss_event_reminder') {
    if (actionMessage?.processing || actionMessage?.handled) return
    if (actionMessage) actionMessage.handled = true
    chatStore.addMessage({
      type: 'text',
      role: 'agent',
      content: '好的，这件事我只记住，不提醒。',
      soul: snapshotSoul(activeSoul.value),
    })
    nextTick(() => scrollToBottom())
    return
  }
  if (action === 'interview' || action === 'start_interview') emit('tab-change', 'interview')
  else if (action === 'remind' || action === 'set_reminder') emit('tab-change', 'settings')
  else if (action === 'view_memory') emit('tab-change', 'memory')
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

  const replySoul = await getReplySoulSnapshot()
  chatStore.addMessage({ type: 'text', role: 'user', content: text })
  chatStore.setStreaming(true)
  chatStore.addMessage({ type: 'text', role: 'agent', content: '', soul: replySoul })
  try {
    const response = await apiSendMessage(text, sessionId)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      chatStore.addMessage({ type: 'text', role: 'agent', content: err.detail || '请求失败，请重新登录', soul: replySoul })
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
          switch (event.type) {
            case 'soul_snapshot':
              chatStore.setLastAgentSoul(snapshotSoul(event.data))
              break
            case 'memory_card':
              chatStore.addMessage({ type: 'memory_card', summary: event.data.summary, layer: event.data.layer })
              break
            case 'text_chunk':
              chatStore.appendToStream(event.data.text)
              await new Promise(r => setTimeout(r, 0))
              break
            case 'action_buttons':
              chatStore.addMessage({
                type: 'actions',
                buttons: event.data.buttons,
                prompt: event.data.prompt,
                candidateSummary: event.data.candidate_summary,
              })
              break
            case 'status':
              // 状态事件可选使用，目前 StreamingIndicator 已覆盖
              break
            case 'error':
              chatStore.addMessage({ type: 'error', role: 'system', content: event.data.message || '出错了' })
              break
            case 'done':
              // 流正常结束，finishStream() 会在 finally 中处理
              break
          }
        } catch { continue }
      }
      nextTick(() => scrollToBottom())
    }
  } catch { chatStore.addMessage({ type: 'text', role: 'agent', content: '嗯，我在听。能再多说一点吗？', soul: replySoul }) }
  finally {
    chatStore.finishStream()
    // 刷新会话列表；保留当前页面消息快照，避免新回复刚生成就被历史重载冲掉。
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

function scrollToBottom() { if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight }

// ── 消息编辑/删除 ──
const editingMsgIndex = ref(-1)
const editingText = ref('')

function startEdit(msg, index) {
  if (msg.role !== 'user') return
  editingMsgIndex.value = index
  editingText.value = msg.content
}

function cancelEdit() {
  editingMsgIndex.value = -1
  editingText.value = ''
}

async function confirmEdit() {
  const msg = chatStore.messages[editingMsgIndex.value]
  if (!msg || !editingText.value.trim()) return
  const idx = editingMsgIndex.value
  cancelEdit()
  // 从 API 编辑（删除后续消息）
  try {
    await apiEditMessage(msg.id, editingText.value.trim())
  } catch {}
  // 重新加载会话
  await loadMessages(chatStore.currentSessionId)
  // 自动发送编辑后的消息
  handleSend(editingText.value.trim())
}

async function confirmDelete(msg, index) {
  if (!msg.id) return // 尚未保存的消息不能删除
  if (!confirm('确定删除这条消息及其后的所有回复？')) return
  try {
    await apiDeleteMessage(msg.id)
  } catch (e) {
    console.error('delete error:', e)
  }
  await loadMessages(chatStore.currentSessionId)
}

// ── 会话重命名 ──
const renamingSessionId = ref('')
const renameText = ref('')

function startRename(session) {
  renamingSessionId.value = session.id
  renameText.value = session.title
}

function cancelRename() {
  renamingSessionId.value = ''
  renameText.value = ''
}

async function confirmRename(session) {
  if (!renameText.value.trim()) return
  try {
    await apiUpdateSession(session.id, { title: renameText.value.trim() })
    session.title = renameText.value.trim()
  } catch {}
  cancelRename()
}
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
.session-rename-btn { font-size: 12px; padding: 2px; opacity: .3; flex-shrink:0; }
.session-rename-btn:active { opacity: 1; }
.edit-bar {
  padding: 6px 12px; border-top: 1px solid var(--line);
  background: var(--honey-soft); flex-shrink: 0;
}
.session-rename-input {
  width: 100%; padding: 2px 6px; font-size: 14px; font-weight: 500;
  border: 1.5px solid var(--honey); border-radius: 6px; outline: none;
  background: var(--paper);
}
.chat-hero-orb {
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: chat-hero-bob 3.2s ease-in-out infinite;
}
.chat-hero-orb.squish {
  animation: chat-hero-squish .45s cubic-bezier(.34,1.56,.64,1);
}
@keyframes chat-hero-bob {
  0%,100% { transform: translateY(0) rotate(-1.5deg); }
  50% { transform: translateY(-5px) rotate(1.5deg); }
}
@keyframes chat-hero-squish {
  0% { transform: scale(1,1); }
  30% { transform: scale(1.12,.84); }
  55% { transform: scale(.94,1.08); }
  100% { transform: scale(1,1); }
}
</style>
