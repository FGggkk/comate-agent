<template>
  <div class="flex flex-col h-full">
    <!-- SOUL Onboarding -->
    <div v-if="showOnboarding" class="scroll">
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
    <div v-else style="display:flex;flex-direction:column;height:100%;">
      <!-- 消息区 -->
      <div ref="scrollRef" style="flex:1;overflow-y:auto;padding:8px 14px;">
        <div v-if="chatStore.messages.length > 0" class="day-tag">{{ timeGreeting }}</div>

        <template v-for="(msg, i) in chatStore.messages" :key="i">
          <!-- 时间分割：消息间隔超过 2 分钟 -->
          <div v-if="shouldShowTimeSep(i)" class="day-tag">{{ formatTimeSep(msg.timestamp) }}</div>
          <MessageBubble v-if="msg.type === 'text'" :role="msg.role" :content="msg.content" />
          <MemoryCard v-else-if="msg.type === 'memory_card'" :summary="msg.summary" :layer="msg.layer" />
          <ActionButtons v-else-if="msg.type === 'actions'" :buttons="msg.buttons" @action="handleAction" />
        </template>

        <StatusIndicator v-if="chatStore.isStreaming" />

        <!-- 空状态：垂直居中 -->
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

      <!-- 底部：快捷栏 + 输入框 -->
      <QuickBar :items="quickItems" />
      <InputBar :disabled="chatStore.isStreaming" @send="handleSend" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useUserStore } from '../stores/user'
import { apiGetTemplates, apiPreview, apiConfirmSoul, apiSendMessage } from '../api/index'
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

function squishHero() {
  heroSquished.value = true
  setTimeout(() => { heroSquished.value = false }, 450)
}

const emit = defineEmits(['tab-change'])

function handleAction(action) {
  if (action === 'interview') {
    emit('tab-change', 'interview')
  } else if (action === 'remind') {
    emit('tab-change', 'settings')
  } else {
    handleSend('帮我分析一下')
  }
}

onMounted(async () => {
  if (userStore.needsOnboarding) templates.value = await apiGetTemplates()
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
}

async function handleSend(text) {
  chatStore.addMessage({ type: 'text', role: 'user', content: text })
  chatStore.setStreaming(true)
  chatStore.addMessage({ type: 'text', role: 'agent', content: '' })
  try {
    const response = await apiSendMessage(text)
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
    nextTick(() => scrollToBottom())
  }
}

const timeGreeting = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  const d = now.getDate()
  const h = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  return `${y}年${m}月${d}日 ${h}:${min}`
})

function shouldShowTimeSep(i) {
  if (i === 0) return false
  const prev = chatStore.messages[i - 1]
  const curr = chatStore.messages[i]
  if (!prev.timestamp || !curr.timestamp) return false
  return (curr.timestamp - prev.timestamp) > 120_000 // 2 分钟
}

function formatTimeSep(ts) {
  const d = new Date(ts)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

function scrollToBottom() { if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight }
</script>
