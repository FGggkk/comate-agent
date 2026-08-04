<template>
  <Teleport to="body">
    <button
      v-if="windowState === 'hidden'"
      class="rag-edge-handle"
      :style="edgeHandleStyle"
      title="显示公司知识问答"
      aria-label="显示公司知识问答"
      @click="restoreBubble"
    >⌁</button>

    <button
      v-else-if="windowState === 'bubble'"
      class="rag-bubble"
      :style="bubbleStyle"
      title="打开公司知识问答"
      aria-label="打开公司知识问答"
      @pointerdown="startBubbleDrag"
      @click="openPanel"
    >
      <span class="rag-bubble-mark">▦</span>
      <span class="rag-bubble-pulse"></span>
    </button>

    <section
      v-else
      :class="['rag-floating-window', compact ? 'is-compact' : '']"
      :style="panelStyle"
      role="dialog"
      aria-label="公司知识问答"
    >
      <header class="rag-window-head" @pointerdown="startPanelDrag">
        <div class="rag-window-title">
          <span class="rag-window-mark">▦</span>
          <div>
            <b>公司知识</b>
            <small>{{ activeType?.label || '公司制度' }}</small>
          </div>
        </div>
        <div class="rag-window-actions">
          <button title="切换窗口尺寸" aria-label="切换窗口尺寸" @click="toggleCompact">{{ compact ? '↗' : '↙' }}</button>
          <button title="收起为悬浮球" aria-label="收起为悬浮球" @click="minimizeToBubble">−</button>
          <button title="隐藏入口" aria-label="隐藏入口" @click="hideWindow">×</button>
        </div>
      </header>

      <main ref="messageListRef" class="rag-window-body">
        <section v-if="!messages.length" class="rag-empty">
          <div class="rag-empty-mark">▦</div>
          <div class="rag-card-grid">
            <button v-for="card in quickCards" :key="card.id" class="rag-quick-card" @click="useQuickCard(card)">
              <span class="rag-card-icon">{{ card.icon }}</span>
              <span><b>{{ card.title }}</b><small>{{ card.desc }}</small></span>
            </button>
          </div>
        </section>

        <article v-for="message in messages" :key="message.localId" :class="['rag-message', message.role]">
          <div class="rag-message-label">{{ message.role === 'user' ? '我' : (activeType?.label || '公司制度') }}</div>
          <div v-if="message.role === 'agent'" class="rag-message-copy" v-html="renderMarkdown(message.content)"></div>
          <div v-else class="rag-message-copy user-copy">{{ message.content }}</div>
          <section v-if="message.role === 'agent' && message.citations?.length" class="rag-citations">
            <button
              class="rag-sources-toggle"
              :aria-expanded="isSourcesExpanded(message.localId)"
              @click="toggleSources(message.localId)"
            >
              <span>参考来源（{{ message.citations.length }}）</span>
              <i>{{ isSourcesExpanded(message.localId) ? '收起' : '展开' }}</i>
            </button>
            <div v-if="isSourcesExpanded(message.localId)" class="rag-citation-list">
              <button
                v-for="(source, index) in message.citations"
                :key="source.chunk_id || `${message.localId}-${index}`"
                class="rag-citation"
                @click="toggleCitation(message.localId, index)"
              >
                <span>
                  <b>{{ source.title }}</b>
                  <small>{{ source.section_path || '未标注章节' }} · {{ source.version }} · {{ source.effective_at || '未标注生效日期' }}</small>
                </span>
                <i>{{ expandedCitation?.messageId === message.localId && expandedCitation?.index === index ? '收起' : '片段' }}</i>
              </button>
              <p v-if="expandedCitation?.messageId === message.localId" class="rag-citation-excerpt">
                {{ message.citations[expandedCitation.index]?.excerpt }}
              </p>
            </div>
          </section>
        </article>

        <div v-if="isSubmitting" class="rag-typing"><i></i><i></i><i></i></div>
      </main>

      <p v-if="notice" :class="['rag-notice', notice.type]">{{ notice.text }}</p>

      <footer class="rag-composer">
        <textarea
          ref="inputRef"
          v-model="draft"
          :disabled="isSubmitting"
          rows="2"
          placeholder="问问公司制度..."
          @keydown.enter.exact.prevent="sendQuestion"
        />
        <div class="rag-composer-actions">
          <span class="rag-input-status">{{ voiceStatusText }}</span>
          <div>
            <button
              :class="['rag-icon-button', voiceState === 'recording' ? 'is-recording' : '']"
              :disabled="isSubmitting || voiceState === 'connecting'"
              :title="voiceButtonLabel"
              :aria-label="voiceButtonLabel"
              @click="$emit('voice')"
            >{{ voiceState === 'recording' || voiceState === 'responding' ? '■' : '♩' }}</button>
            <button class="rag-send-button" :disabled="isSubmitting || !draft.trim()" title="发送问题" aria-label="发送问题" @click="sendQuestion">↑</button>
          </div>
        </div>
      </footer>
    </section>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import { apiGetCompanyKnowledgeTypes, apiListCompanyKnowledgeMessages, apiQueryCompanyKnowledge } from '../api/index'

const props = defineProps({
  sessionId: { type: String, default: '' },
  ensureSession: { type: Function, required: true },
  refreshPermission: { type: Function, required: true },
  voiceState: { type: String, default: 'idle' },
  voiceHint: { type: String, default: '' },
})
const emit = defineEmits(['voice', 'access-revoked'])

const STATE_KEY = 'comate_rag_floating_state'
const BUBBLE_KEY = 'comate_rag_floating_bubble'
const PANEL_KEY = 'comate_rag_floating_panel'
const SIZE_KEY = 'comate_rag_floating_compact'
const windowState = ref(readState())
const compact = ref(localStorage.getItem(SIZE_KEY) === 'true')
const bubblePosition = ref(readPosition(BUBBLE_KEY, () => ({ x: Math.max(16, window.innerWidth - 76), y: Math.max(16, window.innerHeight - 104) })))
const panelPosition = ref(readPosition(PANEL_KEY, () => ({ x: Math.max(16, window.innerWidth - 430), y: Math.max(16, window.innerHeight - 580) })))
const messageListRef = ref(null)
const inputRef = ref(null)
const messages = ref([])
const draft = ref('')
const inputMode = ref('text')
const types = ref([])
const activeTypeKey = ref('policy')
const isSubmitting = ref(false)
const notice = ref(null)
const expandedSources = ref({})
const expandedCitation = ref(null)

let drag = null
let bubbleWasDragged = false

const activeType = computed(() => types.value.find((item) => item.key === activeTypeKey.value) || null)
const isMobile = () => window.matchMedia('(max-width: 720px)').matches
const panelStyle = computed(() => {
  if (isMobile()) return {}
  return { left: `${panelPosition.value.x}px`, top: `${panelPosition.value.y}px` }
})
const bubbleStyle = computed(() => {
  if (isMobile()) return {}
  return { left: `${bubblePosition.value.x}px`, top: `${bubblePosition.value.y}px` }
})
const edgeHandleStyle = computed(() => isMobile() ? {} : { top: `${Math.min(window.innerHeight - 86, Math.max(86, bubblePosition.value.y))}px` })
const quickCards = computed(() => {
  if (!activeType.value) return []
  return [
    { id: 'attendance', icon: '◷', title: '请假与考勤', desc: '申请与出勤规则', prompt: '请说明请假与考勤的制度要求。' },
    { id: 'expense', icon: '▤', title: '费用报销', desc: '报销流程与材料', prompt: '请说明费用报销的制度要求。' },
    { id: 'travel', icon: '⌁', title: '出差与差旅', desc: '申请与费用规范', prompt: '请说明出差与差旅的制度要求。' },
    { id: 'security', icon: '◇', title: '办公与信息安全', desc: '日常办公规范', prompt: '请说明办公与信息安全的制度要求。' },
  ]
})
const voiceButtonLabel = computed(() => ({ recording: '结束录音', responding: '停止语音识别', connecting: '正在连接语音服务' }[props.voiceState] || '语音输入'))
const voiceStatusText = computed(() => props.voiceHint || ({ recording: '正在录音', responding: '正在识别', connecting: '正在连接语音' }[props.voiceState] || 'Enter 发送，Shift + Enter 换行'))

function readState() {
  const state = localStorage.getItem(STATE_KEY)
  return ['bubble', 'panel', 'hidden'].includes(state) ? state : 'bubble'
}

function readPosition(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '')
    if (Number.isFinite(parsed?.x) && Number.isFinite(parsed?.y)) return parsed
  } catch {}
  return fallback()
}

function saveState() {
  localStorage.setItem(STATE_KEY, windowState.value)
  localStorage.setItem(BUBBLE_KEY, JSON.stringify(bubblePosition.value))
  localStorage.setItem(PANEL_KEY, JSON.stringify(panelPosition.value))
  localStorage.setItem(SIZE_KEY, String(compact.value))
}

function clearPersistedState() {
  ;[STATE_KEY, BUBBLE_KEY, PANEL_KEY, SIZE_KEY].forEach((key) => localStorage.removeItem(key))
}

async function confirmPermission() {
  const enabled = await props.refreshPermission()
  if (!enabled) {
    clearPersistedState()
    emit('access-revoked')
    return false
  }
  return true
}

async function openPanel() {
  if (bubbleWasDragged) {
    bubbleWasDragged = false
    return
  }
  if (!await confirmPermission()) return
  windowState.value = 'panel'
  saveState()
  await Promise.all([loadTypes(), loadHistory()])
  nextTick(() => inputRef.value?.focus())
}

function minimizeToBubble() {
  windowState.value = 'bubble'
  saveState()
}

function hideWindow() {
  windowState.value = 'hidden'
  saveState()
}

function restoreBubble() {
  windowState.value = 'bubble'
  saveState()
}

function toggleCompact() {
  compact.value = !compact.value
  clampPositions()
  saveState()
}

async function loadTypes() {
  try {
    const result = await apiGetCompanyKnowledgeTypes()
    types.value = (result.items || []).filter((item) => item.query_enabled && item.user_visible)
    if (!types.value.some((item) => item.key === activeTypeKey.value)) activeTypeKey.value = types.value[0]?.key || 'policy'
  } catch {
    showNotice('知识范围暂时无法加载。', 'error')
  }
}

async function loadHistory() {
  if (!props.sessionId) {
    messages.value = []
    return
  }
  try {
    const result = await apiListCompanyKnowledgeMessages(props.sessionId)
    if (result?.success === false) {
      handleApiFailure(result)
      return
    }
    messages.value = (result.messages || []).map((item) => ({
      localId: item.id,
      id: item.id,
      role: item.role,
      content: item.content,
      citations: item.metadata?.company_knowledge?.citations || [],
    }))
    scrollToBottom()
  } catch {
    showNotice('历史问答暂时无法加载。', 'error')
  }
}

function useQuickCard(card) {
  draft.value = card.prompt
  nextTick(() => inputRef.value?.focus())
}

async function sendQuestion() {
  const question = draft.value.trim()
  if (!question || isSubmitting.value || !await confirmPermission()) return
  const sessionId = props.sessionId || await props.ensureSession()
  if (!sessionId) {
    showNotice('创建会话失败，请稍后再试。', 'error')
    return
  }

  const userMessage = createMessage('user', question)
  const agentMessage = createMessage('agent', '')
  const questionInputMode = inputMode.value
  messages.value.push(userMessage, agentMessage)
  draft.value = ''
  inputMode.value = 'text'
  notice.value = null
  isSubmitting.value = true
  scrollToBottom()

  try {
    const response = await apiQueryCompanyKnowledge({
      message: question,
      session_id: sessionId,
      knowledge_type: activeTypeKey.value,
      input_mode: questionInputMode,
    })
    const contentType = response.headers.get('content-type') || ''
    if (!response.ok || !contentType.includes('text/event-stream')) {
      const payload = await response.json().catch(() => ({}))
      if (response.status === 403 || payload?.data?.code === 'rag_disabled') {
        clearPersistedState()
        emit('access-revoked')
        return
      }
      throw new Error(payload.message || payload.detail || '制度问答暂时不可用，请稍后再试。')
    }
    await consumeStream(response, userMessage, agentMessage)
  } catch (error) {
    agentMessage.content = error.message || '制度问答暂时不可用，请稍后再试。'
    showNotice(agentMessage.content, 'error')
  } finally {
    if (!agentMessage.content) agentMessage.content = '暂时无法生成制度答复，请稍后再试。'
    isSubmitting.value = false
    scrollToBottom()
  }
}

async function consumeStream(response, userMessage, agentMessage) {
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
        if (event.type === 'message_saved') {
          const target = event.data?.role === 'user' ? userMessage : agentMessage
          target.id = event.data?.id || target.id
          target.localId = target.id || target.localId
        } else if (event.type === 'sources') {
          agentMessage.citations = event.data?.items || []
        } else if (event.type === 'text_chunk') {
          agentMessage.content += event.data?.text || ''
        } else if (event.type === 'error') {
          const message = event.data?.message || '制度问答暂时不可用，请稍后再试。'
          if (!agentMessage.content) agentMessage.content = message
          showNotice(message, 'error')
        }
      } catch {}
    }
    scrollToBottom()
  }
}

function createMessage(role, content) {
  return { localId: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`, role, content, citations: [] }
}

function handleApiFailure(result) {
  if (result?.data?.code === 'rag_disabled') {
    clearPersistedState()
    emit('access-revoked')
    return
  }
  showNotice(result?.message || '历史问答暂时无法加载。', 'error')
}

function showNotice(text, type = 'info') {
  notice.value = { text, type }
}

function toggleCitation(messageId, index) {
  expandedCitation.value = expandedCitation.value?.messageId === messageId && expandedCitation.value?.index === index
    ? null
    : { messageId, index }
}

function isSourcesExpanded(messageId) {
  return expandedSources.value[messageId] === true
}

function toggleSources(messageId) {
  const expanded = !isSourcesExpanded(messageId)
  expandedSources.value = { ...expandedSources.value, [messageId]: expanded }
  if (!expanded && expandedCitation.value?.messageId === messageId) expandedCitation.value = null
}

function renderMarkdown(text) {
  return text ? marked.parse(text) : ''
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  })
}

function startBubbleDrag(event) {
  if (isMobile()) return
  beginDrag('bubble', event, bubblePosition.value)
}

function startPanelDrag(event) {
  if (isMobile() || event.target.closest('button')) return
  beginDrag('panel', event, panelPosition.value)
}

function beginDrag(kind, event, position) {
  if (event.button !== 0) return
  drag = { kind, startX: event.clientX, startY: event.clientY, originX: position.x, originY: position.y }
  bubbleWasDragged = false
  window.addEventListener('pointermove', moveDrag)
  window.addEventListener('pointerup', endDrag, { once: true })
}

function moveDrag(event) {
  if (!drag) return
  const target = drag.kind === 'bubble' ? bubblePosition : panelPosition
  const x = drag.originX + event.clientX - drag.startX
  const y = drag.originY + event.clientY - drag.startY
  target.value = clampPosition(drag.kind, x, y)
  if (Math.abs(event.clientX - drag.startX) > 4 || Math.abs(event.clientY - drag.startY) > 4) bubbleWasDragged = true
}

function endDrag() {
  window.removeEventListener('pointermove', moveDrag)
  drag = null
  clampPositions()
  saveState()
}

function clampPosition(kind, x, y) {
  const width = kind === 'bubble' ? 56 : (compact.value ? 348 : 412)
  const height = kind === 'bubble' ? 56 : (compact.value ? 470 : 590)
  return {
    x: Math.max(10, Math.min(window.innerWidth - width - 10, x)),
    y: Math.max(10, Math.min(window.innerHeight - height - 10, y)),
  }
}

function clampPositions() {
  if (isMobile()) return
  bubblePosition.value = clampPosition('bubble', bubblePosition.value.x, bubblePosition.value.y)
  panelPosition.value = clampPosition('panel', panelPosition.value.x, panelPosition.value.y)
}

function applyVoiceTranscript(text) {
  const transcript = (text || '').trim()
  if (!transcript) {
    showNotice('未识别到有效语音内容。', 'error')
    return
  }
  draft.value = transcript
  inputMode.value = 'voice'
  showNotice('语音已转为文字，可修改后发送。')
  nextTick(() => inputRef.value?.focus())
}

function setVoiceHint(text) {
  if (text) showNotice(text, 'error')
}

watch(() => props.sessionId, () => {
  if (windowState.value === 'panel') loadHistory()
})
watch(windowState, saveState)

onMounted(() => {
  clampPositions()
  window.addEventListener('resize', clampPositions)
  if (windowState.value === 'panel') {
    loadTypes()
    loadHistory()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', moveDrag)
  window.removeEventListener('resize', clampPositions)
})

defineExpose({ applyVoiceTranscript, setVoiceHint, clearPersistedState, loadHistory })
</script>

<style scoped>
.rag-bubble, .rag-edge-handle, .rag-floating-window { position:fixed; z-index:80; }
.rag-bubble { width:56px; height:56px; display:grid; place-items:center; border:1px solid #D2E3DB; border-radius:50%; background:#FDFDFB; color:#2F745B; box-shadow:0 10px 26px rgba(32,74,61,.24); touch-action:none; }
.rag-bubble-mark { position:relative; z-index:1; font-size:22px; line-height:1; }
.rag-bubble-pulse { position:absolute; width:11px; height:11px; right:3px; top:3px; border:2px solid #fff; border-radius:50%; background:#EE875F; }
.rag-edge-handle { right:0; width:28px; height:60px; display:grid; place-items:center; border:1px solid #D2E3DB; border-right:0; border-radius:8px 0 0 8px; background:#FDFDFB; color:#2F745B; box-shadow:0 8px 22px rgba(32,74,61,.18); font-size:18px; }
.rag-floating-window { width:412px; height:590px; display:flex; flex-direction:column; overflow:hidden; border:1px solid #D5E5DC; border-radius:8px; background:#FCFCF9; box-shadow:0 18px 52px rgba(25,57,47,.28); }
.rag-floating-window.is-compact { width:348px; height:470px; }
.rag-window-head { flex-shrink:0; display:flex; align-items:center; justify-content:space-between; min-height:54px; padding:0 10px 0 13px; border-bottom:1px solid #DCE9E2; background:#F3F8F4; cursor:grab; user-select:none; }
.rag-window-head:active { cursor:grabbing; }
.rag-window-title { min-width:0; display:flex; align-items:center; gap:8px; }
.rag-window-mark, .rag-empty-mark { display:grid; place-items:center; background:#DCEFE3; color:#2F745B; }
.rag-window-mark { width:28px; height:28px; border-radius:6px; font-size:14px; }
.rag-window-title b, .rag-window-title small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rag-window-title b { color:#25493D; font-size:14px; }
.rag-window-title small { margin-top:1px; color:#74867D; font-size:11px; }
.rag-window-actions { display:flex; gap:2px; }
.rag-window-actions button, .rag-icon-button, .rag-send-button { display:inline-grid; place-items:center; border:1px solid transparent; }
.rag-window-actions button { width:28px; height:28px; border-radius:5px; color:#60746A; font-size:17px; }
.rag-window-actions button:hover { background:#E0EBE4; color:#25493D; }
.rag-window-body { flex:1; min-height:0; overflow-y:auto; padding:14px; }
.rag-empty { min-height:100%; display:flex; flex-direction:column; justify-content:center; gap:18px; }
.rag-empty-mark { width:44px; height:44px; margin:0 auto; border-radius:7px; font-size:22px; }
.rag-card-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.rag-quick-card { min-height:72px; display:flex; align-items:center; gap:8px; padding:9px; border:1px solid #DCE7DF; border-radius:6px; background:#fff; text-align:left; }
.rag-quick-card:hover { border-color:#96BAA8; background:#F5FAF6; }
.rag-card-icon { width:27px; height:27px; flex-shrink:0; display:grid; place-items:center; border-radius:6px; background:#FDE9D8; color:#B65D35; font-size:15px; }
.rag-quick-card b, .rag-quick-card small { display:block; }
.rag-quick-card b { color:#25493D; font-size:12px; }
.rag-quick-card small { margin-top:3px; color:#7B8B83; font-size:10px; line-height:1.3; }
.rag-message { max-width:88%; margin-bottom:12px; overflow:hidden; border-radius:7px; padding:9px 10px; background:#F1F7F3; color:#24463B; }
.rag-message.user { margin-left:auto; background:#EAF2EC; border-bottom-right-radius:2px; }
.rag-message.agent { margin-right:auto; border:1px solid #DCE9E2; border-bottom-left-radius:2px; background:#fff; }
.rag-message-label { margin-bottom:5px; color:#648173; font-size:10px; font-weight:700; }
.rag-message-copy { font-size:13px; line-height:1.62; overflow-wrap:anywhere; }
.user-copy { white-space:pre-wrap; }
.rag-message-copy :deep(p + p) { margin-top:6px; }
.rag-message-copy :deep(ul), .rag-message-copy :deep(ol) { margin:5px 0; padding-left:18px; }
.rag-citations { margin-top:9px; padding-top:7px; border-top:1px solid #E1EBE4; }
.rag-sources-toggle { display:flex; align-items:center; justify-content:space-between; width:100%; padding:1px 0; color:#2F745B; font-size:11px; text-align:left; }
.rag-sources-toggle i { color:#5C8E78; font-size:10px; font-style:normal; }
.rag-citation-list { margin-top:6px; border-top:1px solid #EAF1EC; }
.rag-citation { width:100%; display:flex; align-items:center; justify-content:space-between; gap:7px; padding:5px 0; color:#2F745B; text-align:left; }
.rag-citation span { min-width:0; display:flex; flex-direction:column; }
.rag-citation b, .rag-citation small { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rag-citation b { color:#315A4A; font-size:11px; }
.rag-citation small { margin-top:2px; color:#7B8B83; font-size:10px; }
.rag-citation i { flex-shrink:0; color:#2F745B; font-size:10px; font-style:normal; }
.rag-citation-excerpt { margin-top:3px; padding:7px; border-radius:5px; background:#F5F8F5; color:#52675D; font-size:11px; line-height:1.5; white-space:pre-wrap; overflow-wrap:anywhere; }
.rag-typing { display:flex; gap:4px; padding:8px 2px; }
.rag-typing i { width:6px; height:6px; border-radius:50%; background:#5C987D; animation:rag-bounce 1s infinite; }
.rag-typing i:nth-child(2) { animation-delay:.14s; }.rag-typing i:nth-child(3) { animation-delay:.28s; }
.rag-notice { flex-shrink:0; margin:0; padding:6px 12px; border-top:1px solid #E2EBE5; color:#5D7368; background:#F6FAF7; font-size:11px; line-height:1.4; }
.rag-notice.error { color:#A84C4A; background:#FFF3F1; }
.rag-composer { flex-shrink:0; padding:9px; border-top:1px solid #DCE9E2; background:#F9FBF9; }
.rag-composer textarea { display:block; box-sizing:border-box; width:100%; min-height:47px; max-height:112px; resize:vertical; border:1px solid #D5E2D9; border-radius:6px; outline:none; padding:8px; background:#fff; color:#25493D; font:13px/1.45 inherit; }
.rag-composer textarea:focus { border-color:#83AD99; box-shadow:0 0 0 2px rgba(80,138,113,.12); }
.rag-composer-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:6px; }
.rag-input-status { min-width:0; color:#7B8B83; font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rag-composer-actions > div { display:flex; gap:6px; }
.rag-icon-button, .rag-send-button { width:30px; height:30px; border-radius:50%; font-size:15px; }
.rag-icon-button { border-color:#D5E2D9; background:#fff; color:#4E7E69; }
.rag-icon-button.is-recording { border-color:#C7695D; background:#C7695D; color:#fff; animation:rag-pulse 1.2s ease-in-out infinite; }
.rag-send-button { background:#2F745B; color:#fff; font-size:18px; line-height:1; }
.rag-icon-button:disabled, .rag-send-button:disabled { opacity:.45; cursor:not-allowed; }
@keyframes rag-bounce { 0%,60%,100% { transform:translateY(0); opacity:.4; } 30% { transform:translateY(-4px); opacity:1; } }
@keyframes rag-pulse { 50% { box-shadow:0 0 0 4px rgba(199,105,93,.16); } }
@media (max-width:720px) {
  .rag-bubble { right:16px; bottom:86px; left:auto !important; top:auto !important; }
  .rag-edge-handle { top:auto !important; right:0; bottom:104px; }
  .rag-floating-window, .rag-floating-window.is-compact { right:0; bottom:0; left:0 !important; top:auto !important; width:auto; height:min(74dvh,620px); border-right:0; border-bottom:0; border-left:0; border-radius:10px 10px 0 0; }
  .rag-window-head { cursor:default; }
}
</style>
