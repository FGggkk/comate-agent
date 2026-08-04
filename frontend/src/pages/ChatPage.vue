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
          <div v-else-if="msg.type === 'thinking_trace'" class="thinking-trace">
            <button class="thinking-header" @click="msg.collapsed = !msg.collapsed">
              <span>{{ msg.active ? '正在整理思考过程' : '思考过程' }}</span>
              <span>{{ msg.memories?.length || 0 }} 条线索 {{ msg.collapsed ? '展开' : '收起' }}</span>
            </button>
            <div v-if="!msg.collapsed" class="thinking-body">
              <MemoryCard
                v-for="(memory, memoryIndex) in msg.memories"
                :key="`${memory.layer}-${memory.summary}-${memoryIndex}`"
                :summary="memory.summary"
                :layer="memory.layer"
              />
            </div>
          </div>
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
        <div v-if="voiceToolStatus" class="voice-tool-status" role="status">
          <span class="voice-tool-status-icon">⌛</span>
          <span>{{ voiceToolStatus }}</span>
        </div>

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
      <Transition name="writing-panel">
        <section v-if="showWritingPanel && editingMsgIndex < 0" class="writing-panel" aria-label="帮我写作">
          <div class="writing-panel-head">
            <div class="writing-panel-title">
              <span>✍️</span>
              <strong>帮我写作</strong>
            </div>
            <button class="writing-close-btn" @click="showWritingPanel = false" aria-label="收起写作面板">×</button>
          </div>
          <div class="writing-grid">
            <button
              v-for="item in writingScenarios"
              :key="item.id"
              :class="['writing-card', activeWritingScenario === item.id ? 'active' : '']"
              @click="applyWritingScenario(item)"
            >
              <span class="writing-icon">{{ item.icon }}</span>
              <span class="writing-copy">
                <span class="writing-card-title">{{ item.title }}</span>
                <span class="writing-card-desc">{{ item.desc }}</span>
              </span>
            </button>
          </div>
        </section>
      </Transition>
      <Transition name="writing-panel">
        <section v-if="showReminderPanel && editingMsgIndex < 0" class="reminder-panel" aria-label="设定提醒">
          <div class="reminder-panel-head">
            <div class="reminder-panel-title">
              <span>📌</span>
              <strong>设定提醒</strong>
            </div>
            <button class="writing-close-btn" @click="showReminderPanel = false" aria-label="收起提醒面板">×</button>
          </div>
          <div class="reminder-form">
            <input
              v-model="reminderDraft.content"
              class="reminder-input"
              placeholder="提醒我做什么..."
              :disabled="reminderSaving"
            />
            <input
              v-model="reminderDraft.time"
              class="reminder-input time"
              type="datetime-local"
              :disabled="reminderSaving"
            />
          </div>
          <div class="reminder-shortcuts">
            <button v-for="item in reminderShortcuts" :key="item.id" @click="applyReminderShortcut(item)">
              {{ item.label }}
            </button>
          </div>
          <div class="reminder-actions">
            <span :class="['reminder-msg', reminderMsgType]">{{ reminderMsg }}</span>
            <button class="reminder-save-btn" :disabled="reminderSaving" @click="createReminderFromCard">
              {{ reminderSaving ? '保存中...' : '保存提醒' }}
            </button>
          </div>
        </section>
      </Transition>
      <InputBar
        v-if="editingMsgIndex < 0"
        ref="inputBarRef"
        :disabled="chatStore.isStreaming || voiceState !== 'idle'"
        :voice-state="voiceState"
        :voice-reply-enabled="voiceReplyEnabled"
        @send="handleSend"
        @voice="toggleVoice"
        @voice-reply-toggle="toggleVoiceReply"
      />
      <RagFloatingChat
        v-if="ragEnabled"
        ref="ragFloatingRef"
        :session-id="chatStore.currentSessionId"
        :ensure-session="ensureSession"
        :refresh-permission="refreshRagPermission"
        :voice-state="voiceState"
        :voice-hint="ragVoiceHint"
        @voice="toggleRagVoice"
        @access-revoked="handleRagAccessRevoked"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useUserStore } from '../stores/user'
import { apiGetTemplates, apiPreview, apiConfirmSoul, apiSendMessage, apiListSessions, apiCreateSession, apiDeleteSession, apiGetMessages, apiEditMessage, apiDeleteMessage, apiUpdateSession, apiGetSoulInventory, apiCreateMemory, apiCreateMemoryReminder, apiCreateReminder, apiGetProfile, apiVoiceRealtimeUrl } from '../api/index'
import MessageBubble from '../components/MessageBubble.vue'
import MemoryCard from '../components/MemoryCard.vue'
import ActionButtons from '../components/ActionButtons.vue'
import StatusIndicator from '../components/StatusIndicator.vue'
import InputBar from '../components/InputBar.vue'
import QuickBar from '../components/QuickBar.vue'
import SoulOrb from '../components/SoulOrb.vue'
import RagFloatingChat from '../components/RagFloatingChat.vue'

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
const inputBarRef = ref(null)
const showWritingPanel = ref(false)
const activeWritingScenario = ref('')
const ragFloatingRef = ref(null)
const ragEnabled = ref(false)
const ragVoiceHint = ref('')
const showReminderPanel = ref(false)
const reminderSaving = ref(false)
const reminderMsg = ref('')
const reminderMsgType = ref('')
const reminderDraft = ref({
  content: '',
  time: '',
})
const activeSoul = computed(() => props.currentSoul || null)
const voiceState = ref('idle')
const voiceReplyEnabled = ref(false)

let voiceSocket = null
let voiceSessionId = ''
let voiceInputContext = null
let voicePlaybackContext = null
let voiceMediaStream = null
let voiceSource = null
let voiceProcessor = null
let voiceSilentGain = null
let voicePlaybackAt = 0
let voiceUserMessage = null
let voiceAgentMessage = null
let voiceUserTranscript = ''
let voiceAgentTranscript = ''
let voiceReplySoul = null
let voiceReplyMode = 'text'
let voiceHasAudio = false
let voiceErrorReported = false
let voicePurpose = 'chat'
const voicePlaybackSources = new Set()
const voiceToolStatus = ref('')
const voiceToolResponseIds = new Set()
const voiceResponseTranscripts = new Map()
const quickItems = [
  { label: '✍️ 帮我写作', action: 'writing' },
  { label: '📌 设定提醒', action: 'remind' },
  { label: '🎯 模拟面试', action: 'workbench:interview' },
  { label: '🧳 旅游规划', action: 'workbench:travel' },
  { label: '💰 记账', action: 'workbench:finance' },
]
const writingScenarios = [
  {
    id: 'create',
    icon: '🪄',
    title: '创作',
    desc: '从零起草',
    draft: '帮我创作一段内容。\n主题：\n用途：\n希望风格：自然、有画面感\n补充信息：',
  },
  {
    id: 'polish',
    icon: '✨',
    title: '润色',
    desc: '改顺改清楚',
    draft: '帮我润色下面这段话，要求更清楚、自然、有礼貌：\n\n',
  },
  {
    id: 'email',
    icon: '📧',
    title: '发邮件',
    desc: '正式不生硬',
    draft: '帮我写一封邮件。\n收件人：\n主题：\n背景：\n希望语气：正式、清楚、自然\n我想表达：',
  },
  {
    id: 'leader',
    icon: '💬',
    title: '与领导交流',
    desc: '稳妥表达诉求',
    draft: '帮我组织一段发给领导的话。\n背景：\n我的诉求：\n需要注意的分寸：\n语气：稳妥、清楚、不卑不亢',
  },
  {
    id: 'social',
    icon: '📮',
    title: '朋友圈/小红书',
    desc: '日常分享文案',
    draft: '帮我写一段朋友圈/小红书文案。\n主题：\n想表达的感受：\n希望风格：轻松、真诚、不夸张\n素材：',
  },
  {
    id: 'mentor',
    icon: '🎓',
    title: '给导师汇报',
    desc: '进展问题计划',
    draft: '帮我写一段给导师的汇报。\n最近进展：\n遇到的问题：\n下一步计划：\n希望语气：简洁、尊重、有条理',
  },
  {
    id: 'summary',
    icon: '🧾',
    title: '工作总结',
    desc: '提炼成果',
    draft: '帮我写一份工作总结。\n时间范围：\n主要工作：\n成果数据：\n遇到的问题：\n下一步计划：',
  },
  {
    id: 'reply',
    icon: '↩️',
    title: '消息回复',
    desc: '得体回应',
    draft: '帮我回复这条消息。\n对方原话：\n我的态度：\n希望语气：自然、得体、不过度热情\n需要表达：',
  },
]
const reminderShortcuts = [
  { id: 'half-hour', label: '30 分钟后', offsetMinutes: 30 },
  { id: 'tonight', label: '今晚 8 点', hour: 20, minute: 0, dayOffset: 0 },
  { id: 'tomorrow', label: '明早 9 点', hour: 9, minute: 0, dayOffset: 1 },
]

const emit = defineEmits(['tab-change', 'reminder-created', 'open-workbench-tool'])

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
            type: m.type,
            role: m.role,
            content: m.content,
            citations: m.metadata?.company_knowledge?.citations || [],
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
  cleanupVoiceResources()
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
  if (id !== chatStore.currentSessionId) cleanupVoiceResources()
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
      cleanupVoiceResources()
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

function formatReminderTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const time = `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  if (sameDay(d, now)) return `今天 ${time}`
  if (sameDay(d, tomorrow)) return `明天 ${time}`
  return `${d.getMonth() + 1}月${d.getDate()}日 ${time}`
}

function toDatetimeLocal(date) {
  const d = new Date(date)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function nextReminderDefault() {
  const date = new Date(Date.now() + 60 * 60 * 1000)
  date.setMinutes(Math.ceil(date.getMinutes() / 5) * 5, 0, 0)
  return toDatetimeLocal(date)
}

function reminderTimeFromShortcut(item) {
  const date = new Date()
  if (item.offsetMinutes) {
    date.setMinutes(date.getMinutes() + item.offsetMinutes, 0, 0)
    return toDatetimeLocal(date)
  }
  date.setDate(date.getDate() + (item.dayOffset || 0))
  date.setHours(item.hour, item.minute || 0, 0, 0)
  if (date <= new Date()) date.setDate(date.getDate() + 1)
  return toDatetimeLocal(date)
}

function shouldShowTimeSep(i) {
  if (i === 0) return false
  const prev = chatStore.messages[i - 1]
  const curr = chatStore.messages[i]
  if (!prev.timestamp || !curr.timestamp) return false
  return (curr.timestamp - prev.timestamp) > 120000
}

// ── 对话 ──

function toggleWritingPanel() {
  showWritingPanel.value = !showWritingPanel.value
  if (showWritingPanel.value) {
    showReminderPanel.value = false
    nextTick(() => inputBarRef.value?.focus())
  }
}

function applyWritingScenario(item) {
  if (!item?.draft) return
  activeWritingScenario.value = item.id
  nextTick(() => {
    inputBarRef.value?.applyDraft(item.draft, { mode: 'replace' })
  })
}

function applyReminderDraft(draft) {
  if (!draft) return
  if (draft.content) reminderDraft.value.content = draft.content
  if (draft.remind_at) reminderDraft.value.time = toDatetimeLocal(new Date(draft.remind_at))
  if (draft.estimated_time) {
    reminderMsg.value = '时间已预填，可以按需要修改'
    reminderMsgType.value = ''
  }
}

function openReminderPanel(draft = null) {
  showReminderPanel.value = true
  showWritingPanel.value = false
  reminderMsg.value = ''
  reminderMsgType.value = ''
  applyReminderDraft(draft)
  if (!reminderDraft.value.time) reminderDraft.value.time = nextReminderDefault()
}

function toggleReminderPanel() {
  if (showReminderPanel.value) {
    showReminderPanel.value = false
  } else {
    openReminderPanel()
  }
}

function applyReminderShortcut(item) {
  reminderDraft.value.time = reminderTimeFromShortcut(item)
}

async function createReminderFromCard() {
  const content = reminderDraft.value.content.trim()
  const timeValue = reminderDraft.value.time
  reminderMsg.value = ''
  reminderMsgType.value = ''
  if (!content) {
    reminderMsg.value = '先写提醒内容'
    reminderMsgType.value = 'error'
    return
  }
  if (!timeValue) {
    reminderMsg.value = '先选提醒时间'
    reminderMsgType.value = 'error'
    return
  }
  const remindAt = new Date(timeValue)
  if (Number.isNaN(remindAt.getTime()) || remindAt <= new Date()) {
    reminderMsg.value = '时间需要晚于现在'
    reminderMsgType.value = 'error'
    return
  }
  reminderSaving.value = true
  try {
    const res = await apiCreateReminder(content, remindAt.toISOString())
    const failed = res?.success === false
    if (failed) {
      reminderMsg.value = res.message || '提醒创建失败'
      reminderMsgType.value = 'error'
      return
    }
    reminderMsg.value = res?.already_exists
      ? `已经有这个提醒了，${formatReminderTime(res?.remind_at || remindAt.toISOString())}`
      : `已保存，${formatReminderTime(res?.remind_at || remindAt.toISOString())}提醒你`
    reminderMsgType.value = 'success'
    reminderDraft.value.content = ''
    reminderDraft.value.time = nextReminderDefault()
    emit('reminder-created')
    setTimeout(() => {
      if (reminderMsgType.value === 'success') showReminderPanel.value = false
    }, 900)
  } catch {
    reminderMsg.value = '提醒创建失败，请稍后再试'
    reminderMsgType.value = 'error'
  } finally {
    reminderSaving.value = false
  }
}

function handleQuickAction(action) {
  const toolId = getWorkbenchToolId(action)
  if (toolId) {
    openWorkbenchTool(toolId)
    return
  }
  if (action === 'writing') toggleWritingPanel()
  else if (action === 'remind') toggleReminderPanel()
  else if (action === 'interview') openWorkbenchTool('interview')
}

function getWorkbenchToolId(action) {
  return typeof action === 'string' && action.startsWith('workbench:') ? action.slice('workbench:'.length) : ''
}

function openWorkbenchTool(toolId) {
  if (!toolId) return
  emit('open-workbench-tool', toolId)
}

async function handleAction(payload, actionMessage = null) {
  const action = typeof payload === 'string' ? payload : payload?.action
  if (action === 'remind' || action === 'set_reminder') {
    if (actionMessage?.processing || actionMessage?.handled) return
    if (actionMessage) actionMessage.handled = true
    openReminderPanel(payload?.reminder)
    nextTick(() => scrollToBottom())
    return
  }
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
      const alreadyExists = !failed && res?.already_exists
      const savedMessage = alreadyExists
        ? '这条我已经记着了。'
        : res?.superseded_count > 0
        ? '好，我记住了，也更新了相关旧记忆。'
        : '好，我记住了。'
      if (actionMessage) actionMessage.handled = true
      chatStore.addMessage({
        type: 'text',
        role: 'agent',
        content: failed ? (res.message || '这条记忆保存失败了，稍后再试。') : savedMessage,
        soul: snapshotSoul(activeSoul.value),
      })
      if (!failed && !alreadyExists && res?.reminder_candidate) {
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
  if (action === 'interview' || action === 'start_interview') {
    openWorkbenchTool('interview')
    return
  }
  if (action === 'writing') toggleWritingPanel()
  else if (action === 'view_memory') emit('tab-change', 'memory')
  else handleSend('给我一些建议')
}

async function ensureSession() {
  let sessionId = chatStore.currentSessionId
  if (!sessionId) {
    const res = await apiCreateSession('新对话')
    if (res.id) {
      sessionId = res.id
      chatStore.setCurrentSession(sessionId)
      chatStore.replaceSessions({ id: sessionId, title: '新对话', updated_at: new Date().toISOString() })
    }
  }
  return sessionId
}

function clearRagFloatingState() {
  ;[
    'comate_rag_floating_state',
    'comate_rag_floating_bubble',
    'comate_rag_floating_panel',
    'comate_rag_floating_compact',
  ].forEach((key) => localStorage.removeItem(key))
}

async function refreshRagPermission() {
  try {
    const profile = await apiGetProfile()
    ragEnabled.value = profile?.user?.rag_enabled === true
  } catch {
    ragEnabled.value = false
  }
  if (!ragEnabled.value) clearRagFloatingState()
  return ragEnabled.value
}

function handleRagAccessRevoked() {
  if (voicePurpose === 'rag_floating_chat' && voiceState.value !== 'idle') cancelVoiceResponse()
  clearRagFloatingState()
  ragEnabled.value = false
}

async function handleSend(text, options = {}) {
  showWritingPanel.value = false
  showReminderPanel.value = false
  const sessionId = await ensureSession()
  if (!sessionId) {
    chatStore.addMessage({ type: 'error', role: 'system', content: '创建会话失败，请稍后再试。' })
    return
  }

  const replySoul = await getReplySoulSnapshot()
  if (options.addUserMessage !== false) {
    chatStore.addMessage({ type: 'text', role: 'user', content: text })
  }
  chatStore.setStreaming(true)
  chatStore.addMessage({ type: 'text', role: 'agent', content: '', soul: replySoul })
  try {
    const response = await apiSendMessage(text, sessionId, {
      persistUserMessage: options.persistUserMessage !== false,
      sourceMessageId: options.sourceMessageId,
    })
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
            case 'message_saved':
              chatStore.attachMessageId(event.data)
              break
            case 'soul_snapshot':
              chatStore.setLastAgentSoul(snapshotSoul(event.data))
              break
            case 'memory_card':
              chatStore.addThinkingMemory({ summary: event.data.summary, layer: event.data.layer })
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

// ── 实时语音 ──

function updateVoiceUserMessage(content) {
  if (!voiceUserMessage) {
    chatStore.addMessage({ type: 'text', role: 'user', content: content || '正在识别…' })
    voiceUserMessage = chatStore.messages[chatStore.messages.length - 1]
  } else {
    voiceUserMessage.content = content || '正在识别…'
  }
}

function updateVoiceAgentMessage(content) {
  if (!voiceAgentMessage) {
    chatStore.addMessage({
      type: 'text',
      role: 'agent',
      content: content || '正在生成回复…',
      soul: voiceReplySoul,
    })
    voiceAgentMessage = chatStore.messages[chatStore.messages.length - 1]
  } else {
    voiceAgentMessage.content = content || '正在生成回复…'
  }
}

function resetVoiceToolState() {
  voiceToolStatus.value = ''
  voiceToolResponseIds.clear()
  voiceResponseTranscripts.clear()
}

function getVoiceResponseId(event) {
  const responseId = event?.response?.id || event?.response_id
  return typeof responseId === 'string' && responseId ? responseId : ''
}

function getVoiceToolStatus(name) {
  const labels = {
    get_weather: '正在查询天气…',
    get_current_time: '正在查询时间…',
    search_web: '正在搜索资料…',
  }
  return labels[name] || '正在查询信息…'
}

function discardVoiceAgentMessage() {
  if (!voiceAgentMessage) return
  const index = chatStore.messages.indexOf(voiceAgentMessage)
  if (index >= 0) chatStore.messages.splice(index, 1)
  voiceAgentMessage = null
  voiceAgentTranscript = ''
}

function updateVoiceAgentTranscript(event, content, replace = false) {
  const responseId = getVoiceResponseId(event)
  if (!responseId) {
    voiceAgentTranscript = replace && content ? content : voiceAgentTranscript + content
    updateVoiceAgentMessage(voiceAgentTranscript)
    return
  }
  if (voiceToolResponseIds.has(responseId)) return

  const previous = voiceResponseTranscripts.get(responseId) || ''
  const transcript = replace && content ? content : previous + content
  voiceResponseTranscripts.set(responseId, transcript)
  voiceAgentTranscript = transcript
  updateVoiceAgentMessage(transcript)
}

function float32ToPcm16(input, inputSampleRate) {
  const targetSampleRate = 16000
  const ratio = inputSampleRate / targetSampleRate
  const outputLength = Math.max(1, Math.floor(input.length / ratio))
  const output = new ArrayBuffer(outputLength * 2)
  const view = new DataView(output)

  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio)
    const end = Math.min(input.length, Math.floor((index + 1) * ratio))
    let sum = 0
    for (let sampleIndex = start; sampleIndex < Math.max(start + 1, end); sampleIndex += 1) {
      sum += input[sampleIndex] || 0
    }
    const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)))
    view.setInt16(index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return output
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index])
  }
  return window.btoa(binary)
}

function base64ToUint8Array(value) {
  const binary = window.atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

async function startVoiceCapture() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前浏览器不支持麦克风录音')
  }
  const AudioContextConstructor = window.AudioContext || window.webkitAudioContext
  if (!AudioContextConstructor) {
    throw new Error('当前浏览器不支持语音处理')
  }

  voiceMediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  })
  voiceInputContext = new AudioContextConstructor()
  await voiceInputContext.resume()
  voiceSource = voiceInputContext.createMediaStreamSource(voiceMediaStream)
  voiceProcessor = voiceInputContext.createScriptProcessor(4096, 1, 1)
  voiceSilentGain = voiceInputContext.createGain()
  voiceSilentGain.gain.value = 0

  voiceProcessor.onaudioprocess = (event) => {
    if (voiceState.value !== 'recording' || voiceSocket?.readyState !== WebSocket.OPEN) return
    const sourceSamples = event.inputBuffer.getChannelData(0)
    const pcm = float32ToPcm16(sourceSamples, voiceInputContext.sampleRate)
    voiceHasAudio = true
    voiceSocket.send(JSON.stringify({ type: 'audio.append', audio: arrayBufferToBase64(pcm) }))
  }

  voiceSource.connect(voiceProcessor)
  voiceProcessor.connect(voiceSilentGain)
  voiceSilentGain.connect(voiceInputContext.destination)
}

function stopVoiceCapture() {
  if (voiceProcessor) {
    voiceProcessor.onaudioprocess = null
    voiceProcessor.disconnect()
  }
  voiceSource?.disconnect()
  voiceSilentGain?.disconnect()
  voiceMediaStream?.getTracks().forEach((track) => track.stop())
  if (voiceInputContext && voiceInputContext.state !== 'closed') voiceInputContext.close()
  voiceProcessor = null
  voiceSource = null
  voiceSilentGain = null
  voiceMediaStream = null
  voiceInputContext = null
}

async function enqueueVoiceAudio(encodedAudio) {
  try {
    const AudioContextConstructor = window.AudioContext || window.webkitAudioContext
    if (!AudioContextConstructor) return
    if (!voicePlaybackContext || voicePlaybackContext.state === 'closed') {
      voicePlaybackContext = new AudioContextConstructor()
    }
    await voicePlaybackContext.resume()
    const bytes = base64ToUint8Array(encodedAudio)
    const pcm = new Int16Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
    const buffer = voicePlaybackContext.createBuffer(1, pcm.length, 24000)
    const channel = buffer.getChannelData(0)
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 0x8000

    const source = voicePlaybackContext.createBufferSource()
    source.buffer = buffer
    source.connect(voicePlaybackContext.destination)
    voicePlaybackSources.add(source)
    source.onended = () => voicePlaybackSources.delete(source)
    const startAt = Math.max(voicePlaybackContext.currentTime, voicePlaybackAt)
    source.start(startAt)
    voicePlaybackAt = startAt + buffer.duration
  } catch (error) {
    console.warn('voice playback failed:', error)
  }
}

function stopVoicePlayback() {
  voicePlaybackSources.forEach((source) => {
    try { source.stop() } catch {}
  })
  voicePlaybackSources.clear()
  voicePlaybackAt = 0
}

function closeVoiceSocket() {
  if (!voiceSocket) return
  voiceSocket.onclose = null
  voiceSocket.onerror = null
  try { voiceSocket.close() } catch {}
  voiceSocket = null
  voiceSessionId = ''
}

function cleanupVoiceResources() {
  stopVoiceCapture()
  stopVoicePlayback()
  closeVoiceSocket()
  if (voiceState.value !== 'idle') chatStore.finishStream()
  voiceState.value = 'idle'
  voiceReplyEnabled.value = false
  voiceReplyMode = 'text'
  voicePurpose = 'chat'
  resetVoiceToolState()
}

function reportVoiceError(message) {
  if (voiceErrorReported) return
  voiceErrorReported = true
  const isRagVoice = voicePurpose === 'rag_floating_chat'
  stopVoiceCapture()
  stopVoicePlayback()
  closeVoiceSocket()
  chatStore.finishStream()
  voiceState.value = 'idle'
  voiceReplyEnabled.value = false
  voiceReplyMode = 'text'
  voicePurpose = 'chat'
  resetVoiceToolState()
  if (isRagVoice) {
    ragVoiceHint.value = message || '语音服务暂时不可用。'
    ragFloatingRef.value?.setVoiceHint(ragVoiceHint.value)
  } else {
    chatStore.addMessage({ type: 'error', role: 'system', content: message || '语音服务暂时不可用。' })
  }
  nextTick(() => scrollToBottom())
}

function handleVoiceEvent(event) {
  const eventType = event?.type
  if (eventType === 'voice.error') {
    reportVoiceError(event.message)
    return
  }
  if (eventType === 'voice.transcript_ready' && voicePurpose === 'rag_floating_chat') {
    const transcript = (event.data?.text || '').trim()
    stopVoiceCapture()
    stopVoicePlayback()
    closeVoiceSocket()
    voiceState.value = 'idle'
    voiceReplyEnabled.value = false
    voiceReplyMode = 'text'
    voicePurpose = 'chat'
    resetVoiceToolState()
    if (transcript) {
      ragFloatingRef.value?.applyVoiceTranscript(transcript)
      ragVoiceHint.value = ''
    } else {
      ragVoiceHint.value = '未识别到有效语音内容'
      ragFloatingRef.value?.setVoiceHint(ragVoiceHint.value)
    }
    return
  }
  if (eventType === 'voice.messages_saved') {
    const saved = event.data || {}
    if (voiceUserMessage && saved.user?.id) voiceUserMessage.id = saved.user.id
    if (voiceAgentMessage && saved.agent?.id) voiceAgentMessage.id = saved.agent.id
    if (saved.session?.id) {
      chatStore.replaceSessions({
        id: saved.session.id,
        title: saved.session.title || '新对话',
        updated_at: saved.session.updated_at || new Date().toISOString(),
      })
      loadSessions()
    }
    return
  }
  if (eventType === 'response.function_call_arguments.done') {
    const responseId = getVoiceResponseId(event)
    if (responseId) voiceToolResponseIds.add(responseId)
    voiceToolStatus.value = getVoiceToolStatus(event.name)
    discardVoiceAgentMessage()
  } else if (eventType === 'conversation.item.input_audio_transcription.delta') {
    voiceUserTranscript += event.delta || event.text || ''
    updateVoiceUserMessage(voiceUserTranscript)
  } else if (eventType === 'conversation.item.input_audio_transcription.completed') {
    voiceUserTranscript = event.transcript || voiceUserTranscript
    updateVoiceUserMessage(voiceUserTranscript)
  } else if (eventType === 'response.audio_transcript.delta' || eventType === 'response.text.delta') {
    updateVoiceAgentTranscript(event, event.delta || event.text || '')
  } else if (eventType === 'response.audio_transcript.done' || eventType === 'response.text.done') {
    updateVoiceAgentTranscript(event, event.transcript || event.text || '', true)
  } else if (eventType === 'response.audio.delta') {
    updateVoiceAgentMessage(voiceAgentTranscript)
    if (voiceReplyMode === 'audio') enqueueVoiceAudio(event.delta)
  } else if (eventType === 'response.done') {
    const responseId = getVoiceResponseId(event)
    if (responseId && voiceToolResponseIds.has(responseId)) {
      voiceResponseTranscripts.delete(responseId)
      nextTick(() => scrollToBottom())
      return
    }
    stopVoiceCapture()
    voiceState.value = 'idle'
    voiceReplyEnabled.value = false
    voiceReplyMode = 'text'
    resetVoiceToolState()
    chatStore.finishStream()
  }
  nextTick(() => scrollToBottom())
}

function openVoiceSocket(sessionId) {
  if (voiceSocket?.readyState === WebSocket.OPEN && voiceSessionId === sessionId) {
    return Promise.resolve()
  }
  closeVoiceSocket()
  const token = localStorage.getItem('comate_token')
  if (!token) return Promise.reject(new Error('登录已失效，请重新登录'))

  return new Promise((resolve, reject) => {
    let settled = false
    const failConnection = (message) => {
      if (settled) return
      settled = true
      reject(new Error(message))
    }
    const timeout = window.setTimeout(() => failConnection('连接语音服务超时'), 15000)
    voiceSocket = new WebSocket(apiVoiceRealtimeUrl(sessionId), ['comate-auth', token])
    voiceSessionId = sessionId
    voiceSocket.onmessage = (message) => {
      let event
      try { event = JSON.parse(message.data) } catch { return }
      if (event.type === 'voice.ready' && !settled) {
        settled = true
        window.clearTimeout(timeout)
        resolve()
      }
      if (event.type === 'voice.error' && !settled) {
        window.clearTimeout(timeout)
        failConnection(event.message || '语音服务连接失败')
      }
      handleVoiceEvent(event)
    }
    voiceSocket.onerror = () => {
      window.clearTimeout(timeout)
      if (!settled) failConnection('语音服务连接失败')
      else if (voiceState.value !== 'idle') reportVoiceError('语音服务连接中断')
    }
    voiceSocket.onclose = () => {
      window.clearTimeout(timeout)
      if (!settled) failConnection('语音服务已关闭')
      else if (voiceState.value !== 'idle') reportVoiceError('语音服务已断开')
    }
  })
}

async function startVoice(purpose = 'chat') {
  if (chatStore.isStreaming) return
  voiceErrorReported = false
  voicePurpose = purpose
  voiceState.value = 'connecting'
  voiceUserMessage = null
  voiceAgentMessage = null
  voiceUserTranscript = ''
  voiceAgentTranscript = ''
  voiceHasAudio = false
  resetVoiceToolState()
  voiceReplyMode = purpose === 'rag_floating_chat' ? 'text' : (voiceReplyEnabled.value ? 'audio' : 'text')
  voiceReplySoul = await getReplySoulSnapshot()
  try {
    const sessionId = await ensureSession()
    if (!sessionId) throw new Error('创建会话失败，请稍后再试')
    await openVoiceSocket(sessionId)
    await startVoiceCapture()
    voiceState.value = 'recording'
  } catch (error) {
    reportVoiceError(error.message)
  }
}

function finishVoiceRecording() {
  const isRagVoice = voicePurpose === 'rag_floating_chat'
  stopVoiceCapture()
  if (!voiceHasAudio) {
    voiceState.value = 'idle'
    voiceReplyEnabled.value = false
    voiceReplyMode = 'text'
    voicePurpose = 'chat'
    resetVoiceToolState()
    if (isRagVoice) {
      ragVoiceHint.value = '没有采集到声音，请检查麦克风后重试。'
      ragFloatingRef.value?.setVoiceHint(ragVoiceHint.value)
    }
    else chatStore.addMessage({ type: 'error', role: 'system', content: '没有采集到声音，请检查麦克风后重试。' })
    return
  }
  if (voiceSocket?.readyState !== WebSocket.OPEN) {
    reportVoiceError('语音服务连接已断开')
    return
  }
  voiceState.value = 'responding'
  if (isRagVoice) ragVoiceHint.value = '正在识别…'
  else {
    updateVoiceUserMessage('正在识别…')
    chatStore.setStreaming(true)
  }
  voiceSocket.send(JSON.stringify({
    type: 'audio.commit',
    reply_mode: voiceReplyMode,
    transcription_only: isRagVoice,
  }))
}

function cancelVoiceResponse() {
  const isRagVoice = voicePurpose === 'rag_floating_chat'
  if (voiceSocket?.readyState === WebSocket.OPEN) {
    voiceSocket.send(JSON.stringify({ type: 'response.cancel' }))
  }
  stopVoicePlayback()
  voiceState.value = 'idle'
  voiceReplyEnabled.value = false
  voiceReplyMode = 'text'
  voicePurpose = 'chat'
  resetVoiceToolState()
  if (isRagVoice) ragVoiceHint.value = '已取消语音输入'
  else chatStore.finishStream()
}

function toggleVoiceReply() {
  if (voiceState.value !== 'idle' || chatStore.isStreaming) return
  voiceReplyEnabled.value = !voiceReplyEnabled.value
}

function toggleVoice() {
  if (voiceState.value === 'connecting') return
  if (voiceState.value === 'recording') {
    finishVoiceRecording()
  } else if (voiceState.value === 'responding') {
    cancelVoiceResponse()
  } else {
    startVoice()
  }
}

function toggleRagVoice() {
  if (chatStore.isStreaming || voiceState.value === 'connecting') return
  if (voiceState.value === 'recording') {
    finishVoiceRecording()
  } else if (voiceState.value === 'responding') {
    cancelVoiceResponse()
  } else {
    ragVoiceHint.value = ''
    startVoice('rag_floating_chat')
  }
}

// ── 页面初始化 ──

onMounted(async () => {
  if (userStore.needsOnboarding) {
    templates.value = await apiGetTemplates()
    return
  }
  await Promise.all([loadSessions(), refreshRagPermission()])
  if (chatStore.currentSessionId) {
    await loadMessages(chatStore.currentSessionId)
  } else if (chatStore.sessions.length > 0) {
    await switchSession(chatStore.sessions[0].id)
  }
})

onBeforeUnmount(() => {
  cleanupVoiceResources()
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
  await Promise.all([loadSessions(), refreshRagPermission()])
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
  const newText = editingText.value.trim()
  if (!msg || !newText) return
  if (!msg.id) {
    alert('这条消息还在保存中，稍后再试。')
    return
  }
  cancelEdit()
  // 从 API 编辑（删除后续消息）
  try {
    const res = await apiEditMessage(msg.id, newText)
    if (res?.success === false) {
      alert(res.message || '编辑失败，请稍后再试。')
      return
    }
  } catch {
    alert('编辑失败，请稍后再试。')
    return
  }
  // 重新加载会话
  await loadMessages(chatStore.currentSessionId)
  // 自动发送编辑后的消息
  await handleSend(newText, {
    addUserMessage: false,
    persistUserMessage: false,
    sourceMessageId: msg.id,
  })
}

async function confirmDelete(msg, index) {
  if (!msg.id) {
    alert('这条消息还在保存中，稍后再试。')
    return
  }
  if (!confirm('确定删除这条消息及其后的所有回复？')) return
  try {
    const res = await apiDeleteMessage(msg.id)
    if (res?.success === false) {
      alert(res.message || '删除失败，请稍后再试。')
      return
    }
  } catch (e) {
    console.error('delete error:', e)
    alert('删除失败，请稍后再试。')
    return
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
.writing-panel {
  flex-shrink: 0;
  margin: 4px 12px 6px;
  padding: 10px;
  border: 1px solid rgba(226, 214, 195, .86);
  border-radius: 14px;
  background: rgba(255, 252, 247, .94);
  box-shadow: 0 8px 24px rgba(104, 84, 55, .08);
}
.writing-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.writing-panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink);
  font-size: 14px;
}
.writing-panel-title strong {
  font-weight: 700;
}
.writing-close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--sub);
  font-size: 22px;
  line-height: 1;
}
.writing-close-btn:active {
  background: var(--cream-2);
  color: var(--ink);
}
.writing-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-height: 252px;
  overflow-y: auto;
  padding-right: 2px;
}
.writing-card {
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, .86);
  text-align: left;
  box-shadow: var(--shadow-sm);
}
.writing-card.active {
  border-color: #FF9F7A;
  background: #FFF3EB;
}
.writing-icon {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--honey-soft);
  font-size: 15px;
}
.writing-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.writing-card-title {
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
  line-height: 17px;
  overflow-wrap: anywhere;
}
.writing-card-desc {
  color: var(--sub);
  font-size: 11px;
  line-height: 15px;
  overflow-wrap: anywhere;
}
.writing-panel-enter-active,
.writing-panel-leave-active {
  transition: opacity .18s ease, transform .18s ease;
}
.writing-panel-enter-from,
.writing-panel-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
.reminder-panel {
  flex-shrink: 0;
  margin: 4px 12px 6px;
  padding: 10px;
  border: 1px solid rgba(226, 214, 195, .86);
  border-radius: 14px;
  background: rgba(255, 252, 247, .96);
  box-shadow: 0 8px 24px rgba(104, 84, 55, .08);
}
.reminder-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.reminder-panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink);
  font-size: 14px;
}
.reminder-panel-title strong {
  font-weight: 700;
}
.reminder-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}
.reminder-input {
  min-width: 0;
  height: 36px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.88);
  color: var(--ink);
  font-size: 13px;
  outline: none;
}
.reminder-input.time {
  width: 168px;
}
.reminder-shortcuts {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 8px 0 2px;
}
.reminder-shortcuts button {
  flex-shrink: 0;
  padding: 5px 9px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.82);
  color: var(--ink-soft);
  font-size: 12px;
}
.reminder-shortcuts button:active {
  background: var(--honey-soft);
  border-color: var(--honey);
}
.reminder-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 32px;
  margin-top: 6px;
}
.reminder-msg {
  min-width: 0;
  flex: 1;
  color: var(--sub);
  font-size: 12px;
  line-height: 16px;
}
.reminder-msg.error {
  color: var(--berry);
}
.reminder-msg.success {
  color: var(--sprout);
}
.reminder-save-btn {
  flex-shrink: 0;
  padding: 7px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #FFB78A, #FF8F6E);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 4px 10px rgba(255,130,80,.2);
}
.reminder-save-btn:disabled {
  opacity: .62;
}
@media (max-width: 520px) {
  .reminder-form {
    grid-template-columns: 1fr;
  }
  .reminder-input.time {
    width: 100%;
  }
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
.thinking-trace {
  margin: 6px 0 8px 52px;
  max-width: calc(100% - 76px);
}
.thinking-header {
  width: 100%;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(255,255,255,.72);
  border: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  text-align: left;
}
.thinking-header span:last-child {
  flex-shrink: 0;
  color: var(--honey-deep);
}
.thinking-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}
.voice-tool-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 6px auto 10px;
  color: var(--sub);
  font-size: 12px;
  line-height: 18px;
}
.voice-tool-status-icon {
  color: var(--honey-deep);
  font-size: 14px;
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
