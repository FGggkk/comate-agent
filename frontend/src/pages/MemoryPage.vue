<template>
  <div class="memory-root">
    <div v-if="!activeSection" class="scroll">
      <div class="memory-hero">
        <svg viewBox="0 0 120 20" width="120" height="20" class="memory-hero-waves">
          <path d="M0 10 Q30 1 60 10 T120 10" stroke="var(--honey-soft)" fill="none" stroke-width="2"/>
          <path d="M0 14 Q30 5 60 14 T120 14" stroke="var(--sprout-soft)" fill="none" stroke-width="1.5" opacity=".72"/>
        </svg>
        <div class="memory-hero-icon">
          <svg viewBox="0 0 32 32" width="28" height="28" fill="none" stroke="var(--honey-deep)" stroke-width="1.6">
            <path d="M8 5h16a2 2 0 0 1 2 2v20l-10-6-10 6V7a2 2 0 0 1 2-2z"/>
            <path d="M12 11h8M12 16h6"/>
          </svg>
        </div>
        <div class="memory-title">记忆</div>
        <div class="memory-sub">整理事实，也沉淀默契</div>
      </div>

      <div v-if="!loaded" class="memory-loading">加载中...</div>

      <template v-else>
        <div class="memory-entry-list">
          <button
            v-for="entry in memoryEntries"
            :key="entry.id"
            :class="['memory-entry', `entry-${entry.id}`]"
            @click="openSection(entry.id)"
          >
            <span class="entry-icon" v-html="entry.icon"></span>
            <span class="entry-body">
              <span class="entry-title">{{ entry.label }}</span>
              <span class="entry-desc">{{ entry.desc }}</span>
            </span>
            <span class="entry-count">
              <strong>{{ entry.count }}</strong>
              <small>{{ entry.unit }}</small>
            </span>
            <svg class="entry-arrow" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8">
              <polyline points="7,4 13,10 7,16"/>
            </svg>
          </button>
        </div>

        <section class="portrait-panel">
          <div class="portrait-head">
            <div class="portrait-orb">
              <SoulOrb :template="profileOrbTemplate" size="lg" />
            </div>
            <div class="portrait-info">
              <div class="portrait-kicker">用户画像</div>
              <div class="portrait-title">{{ profileTitle }}</div>
              <div class="portrait-meta">
                v{{ memoryStore.tacitProfile.version_no || 0 }} · 置信度 {{ formatConfidence(memoryStore.tacitProfile.confidence) }} · {{ formatTime(memoryStore.tacitProfile.last_analyzed_at || memoryStore.tacitProfile.updated_at) }}
              </div>
            </div>
          </div>
          <p class="portrait-summary">{{ profileSummary }}</p>
          <div v-if="portraitChips.length" class="portrait-chips">
            <span v-for="chip in portraitChips" :key="chip">{{ chip }}</span>
          </div>
          <button class="portrait-evidence-link" @click="openSection('tacit')">
            查看画像依据
          </button>
        </section>
      </template>
    </div>

    <div v-else class="scroll detail-scroll">
      <div class="detail-top">
        <button class="back-btn" @click="activeSection = ''">
          <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8">
            <polyline points="13,4 7,10 13,16"/>
          </svg>
          返回记忆
        </button>
        <div>
          <div class="detail-title">{{ currentEntry?.label }}</div>
          <div class="detail-desc">{{ currentEntry?.desc }}</div>
        </div>
      </div>

      <section v-if="activeSection === 'priors'" class="detail-card">
        <MemoryRow v-for="m in memoryStore.layers.priors" :key="m.id" label="先验" :text="m.summary" />
        <EmptyState v-if="memoryStore.layers.priors.length === 0" text="暂无先验记忆" />
      </section>

      <section v-else-if="activeSection === 'co_created'" class="detail-card co-created-detail">
        <div class="memory-add-form">
          <textarea
            v-model="newMemorySummary"
            placeholder="新增共建记忆..."
            class="edit-input add-memory-input"
            rows="2"
          />
          <div class="type-picker">
            <button
              v-for="item in memoryTypeOptions"
              :key="item.value"
              type="button"
              :class="{ active: newMemoryType === item.value }"
              @click="newMemoryType = item.value"
            >
                {{ item.label }}
            </button>
          </div>
          <div class="memory-add-actions">
            <button class="btn-primary add-btn" :disabled="saving" @click="addCoCreatedMemory">添加</button>
          </div>
        </div>
        <div class="detail-tools">
          <input v-model="memorySearch" placeholder="搜索共建记忆..." class="form-input" />
          <div class="segmented">
            <button
              v-for="item in coCreatedFilters"
              :key="item.id"
              :class="{ active: coCreatedFilter === item.id }"
              @click="coCreatedFilter = item.id"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
        <div v-if="notice" class="inline-notice">{{ notice }}</div>
        <div v-if="errorMessage" class="inline-error">{{ errorMessage }}</div>

        <div v-if="filteredCoCreatedMemories.length" class="memory-list-scroll">
          <div v-for="m in filteredCoCreatedMemories" :key="m.id" class="memory-row editable stacked">
            <div class="row-main">
              <span :class="['row-tag', m.user_confirmed ? '' : 'pending']">{{ m.user_confirmed ? '已确认' : '待确认' }}</span>
              <div class="row-content">
                <textarea
                  v-if="editingMemoryId === m.id"
                  v-model="editingSummary"
                  class="edit-input"
                  rows="3"
                />
                <span v-else class="row-text">{{ m.summary }}</span>
                <div class="row-meta">
                  <span>{{ memoryTypeLabel(m.memory_type) }}</span>
                  <span>{{ scopeLabel(m.scope) }}</span>
                  <span v-for="tag in memoryTags(m)" :key="`${m.id}-${tag}`">{{ tag }}</span>
                </div>
              </div>
            </div>
            <div class="row-actions">
              <template v-if="editingMemoryId === m.id">
                <button class="action-confirm" :disabled="saving" @click="saveMemoryEdit(m.id)">保存</button>
                <button class="action-neutral" :disabled="saving" @click="cancelMemoryEdit">取消</button>
              </template>
              <template v-else>
                <button v-if="!m.user_confirmed" class="action-confirm" :disabled="saving" @click="confirmMemory(m.id)">确认</button>
                <button class="action-neutral" :disabled="saving" @click="startMemoryEdit(m)">编辑</button>
                <button class="action-delete" :disabled="saving" @click="deleteMemory(m.id)">删除</button>
              </template>
            </div>
          </div>
        </div>
        <EmptyState v-if="memoryStore.layers.co_created.length === 0" text="暂无共建记忆" />
        <EmptyState v-else-if="filteredCoCreatedMemories.length === 0" text="没有匹配的共建记忆" />
      </section>

      <section v-else-if="activeSection === 'tacit'" class="detail-card tacit-detail">
        <div class="portrait-head compact">
          <div class="portrait-orb small">
            <SoulOrb :template="profileOrbTemplate" size="md" />
          </div>
          <div class="portrait-info">
            <div class="portrait-kicker">用户画像</div>
            <div class="portrait-title">{{ profileTitle }}</div>
            <div class="portrait-meta">
              v{{ memoryStore.tacitProfile.version_no || 0 }} · 置信度 {{ formatConfidence(memoryStore.tacitProfile.confidence) }}
            </div>
          </div>
        </div>
        <p class="portrait-summary detail">{{ profileSummary }}</p>

        <button
          v-if="profileSections().length || memoryStore.layers.tacit.length"
          class="tacit-evidence-btn"
          @click="showTacitEvidence = !showTacitEvidence"
        >
          {{ showTacitEvidence ? '收起画像依据' : '展开画像依据' }}
        </button>

        <div v-if="showTacitEvidence" class="tacit-evidence">
          <div v-for="section in profileSections()" :key="section.key" class="evidence-section">
            <div class="evidence-title">{{ section.label }}</div>
            <div v-for="item in section.items" :key="item.claim" class="evidence-row">
              <span>{{ item.claim }}</span>
              <small>{{ formatConfidence(item.confidence) }} · {{ item.evidence_count || 1 }}次</small>
            </div>
          </div>
          <MemoryRow v-for="m in memoryStore.layers.tacit" :key="m.id" label="推断" :text="m.summary" warn />
        </div>
        <EmptyState v-if="!hasTacitProfile() && memoryStore.layers.tacit.length === 0" text="暂无默契记忆" />
      </section>

      <section v-else-if="activeSection === 'forbidden'" class="detail-card">
        <div class="inline-form">
          <input v-model="newForbidden" placeholder="添加禁区话题..." class="form-input" />
          <button class="btn-primary add-btn" :disabled="saving" @click="addForbidden">添加</button>
        </div>
        <input v-if="memoryStore.forbiddenTopics.length" v-model="forbiddenSearch" placeholder="搜索禁区话题..." class="form-input search-input" />
        <div v-if="notice" class="inline-notice">{{ notice }}</div>
        <div v-if="errorMessage" class="inline-error">{{ errorMessage }}</div>
        <div v-for="f in filteredForbiddenTopics" :key="f.id" class="memory-row editable">
          <div class="row-main">
            <span class="row-tag forbidden">禁区</span>
            <span class="row-text">{{ f.topic }}</span>
          </div>
          <button class="action-delete" :disabled="saving" @click="removeForbidden(f.id)">解除</button>
        </div>
        <EmptyState v-if="memoryStore.forbiddenTopics.length === 0" text="暂无禁区话题" />
        <EmptyState v-else-if="filteredForbiddenTopics.length === 0" text="没有匹配的禁区话题" />
      </section>

      <section v-else-if="activeSection === 'documents'" class="detail-card document-detail">
        <div class="document-tabs">
          <button
            v-for="doc in documentTabs"
            :key="doc.type"
            :class="{ active: activeDocumentType === doc.type }"
            @click="selectDocument(doc.type)"
          >
            {{ doc.file }}
          </button>
        </div>

        <div class="document-toolbar">
          <button class="action-neutral" :disabled="documentBusy" @click="rebuildCurrentDocument">重建</button>
          <button class="action-neutral" :disabled="documentBusy" @click="exportCurrentDocument">导出文件</button>
          <button class="action-neutral" :disabled="documentBusy" @click="importCurrentDocument">从文件导入</button>
          <button class="action-confirm" :disabled="documentBusy" @click="saveCurrentDocument">保存并同步</button>
        </div>

        <div v-if="documentNotice" class="inline-notice">{{ documentNotice }}</div>
        <div v-if="documentError" class="inline-error">{{ documentError }}</div>

        <div class="document-meta">
          <span>{{ documentStatusLabel(selectedDocument?.sync_status, selectedDocument?.file_status?.state) }}</span>
          <span>v{{ selectedDocument?.version_no || 0 }}</span>
          <span>{{ documentContent.length }}/{{ selectedDocument?.char_limit || 0 }}</span>
        </div>
        <div class="document-path">{{ selectedDocumentPath }}</div>

        <textarea
          v-model="documentContent"
          class="document-editor"
          spellcheck="false"
          :placeholder="documentBusy ? '加载中...' : '暂无文档内容'"
        />
      </section>

    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref, onMounted, watch } from 'vue'
import { useMemoryStore } from '../stores/memory'
import {
  apiGetMemories,
  apiCreateMemory,
  apiUpdateMemory,
  apiDeleteMemory,
  apiAddForbidden,
  apiRemoveForbidden,
  apiGetMemoryDocuments,
  apiGetMemoryDocument,
  apiRebuildMemoryDocuments,
  apiUpdateMemoryDocument,
  apiExportMemoryDocument,
  apiImportMemoryDocument,
} from '../api/index'
import SoulOrb from '../components/SoulOrb.vue'

const props = defineProps({
  active: { type: Boolean, default: false },
  currentSoul: { type: Object, default: null },
})
const memoryStore = useMemoryStore()
const loaded = ref(false)
const loading = ref(false)
const activeSection = ref('')
const newForbidden = ref('')
const newMemorySummary = ref('')
const newMemoryType = ref('general')
const memorySearch = ref('')
const forbiddenSearch = ref('')
const coCreatedFilter = ref('all')
const editingMemoryId = ref('')
const editingSummary = ref('')
const saving = ref(false)
const notice = ref('')
const errorMessage = ref('')
const showTacitEvidence = ref(false)
const activeDocumentType = ref('USER')
const documentContent = ref('')
const documentBusy = ref(false)
const documentNotice = ref('')
const documentError = ref('')

const MemoryRow = defineComponent({
  props: {
    label: { type: String, default: '' },
    text: { type: String, default: '' },
    warn: { type: Boolean, default: false },
  },
  setup(rowProps) {
    return () => h('div', { class: 'memory-row' }, [
      h('span', { class: ['row-tag', rowProps.warn ? 'warn' : ''] }, rowProps.label),
      h('span', { class: 'row-text' }, rowProps.text),
    ])
  },
})

const EmptyState = defineComponent({
  props: { text: { type: String, default: '' } },
  setup(emptyProps) {
    return () => h('div', { class: 'empty-state' }, emptyProps.text)
  },
})

const icons = {
  priors: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M16 4c5 3 9 3.5 9 3.5V15c0 6-4.2 10.2-9 13-4.8-2.8-9-7-9-13V7.5S11 7 16 4z"/><path d="M12 16l3 3 6-7"/></svg>',
  co_created: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M11 17l-3 3a5 5 0 0 0 7 7l3-3"/><path d="M21 15l3-3a5 5 0 0 0-7-7l-3 3"/><path d="M13 19l6-6"/></svg>',
  tacit: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 22c-3-2-5-5-5-9a9 9 0 0 1 18 0c0 4-2 7-5 9"/><path d="M12 25h8M13 29h6"/><path d="M13 13c1.8-2 4.2-2 6 0"/></svg>',
  forbidden: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="16" cy="16" r="11"/><path d="M8 24L24 8"/></svg>',
  documents: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 4h10l5 5v19H9z"/><path d="M19 4v6h5"/><path d="M13 15h7M13 20h7M13 25h4"/></svg>',
}

const memoryEntries = computed(() => [
  { id: 'priors', label: '先验层', desc: '系统规则与安全边界', count: countLayer('priors'), unit: '条', icon: icons.priors },
  { id: 'co_created', label: '共建层', desc: '你确认留下的事实', count: countLayer('co_created'), unit: '条', icon: icons.co_created },
  { id: 'tacit', label: '默契层', desc: '跨会话形成的人物画像', count: countLayer('tacit'), unit: '份', icon: icons.tacit },
  { id: 'forbidden', label: '禁区话题', desc: '不主动触碰的边界', count: memoryStore.forbiddenTopics.length, unit: '条', icon: icons.forbidden },
  { id: 'documents', label: '记忆文档', desc: 'USER.md 与 MEMORY.md', count: countDocuments(), unit: '份', icon: icons.documents },
])

const currentEntry = computed(() => memoryEntries.value.find(item => item.id === activeSection.value))

const documentTabs = [
  { type: 'USER', file: 'USER.md' },
  { type: 'MEMORY', file: 'MEMORY.md' },
  { type: 'BOUNDARY', file: 'BOUNDARY.md' },
  { type: 'DELTA', file: 'DELTA.md' },
]

const selectedDocument = computed(() => {
  return (memoryStore.documents || []).find(item => item.doc_type === activeDocumentType.value) || null
})

const selectedDocumentPath = computed(() => {
  return selectedDocument.value?.file_status?.path || selectedDocument.value?.file_path || `${activeDocumentType.value}.md`
})

const coCreatedFilters = [
  { id: 'all', label: '全部' },
  { id: 'confirmed', label: '已确认' },
  { id: 'pending', label: '待确认' },
]

const memoryTypeOptions = [
  { value: 'general', label: '一般' },
  { value: 'preference', label: '偏好' },
  { value: 'routine', label: '习惯' },
  { value: 'event', label: '事件' },
  { value: 'insight', label: '洞察' },
  { value: 'boundary', label: '边界' },
]

const filteredCoCreatedMemories = computed(() => {
  const keyword = normalizeKeyword(memorySearch.value)
  return (memoryStore.layers.co_created || [])
    .filter(item => {
      if (coCreatedFilter.value === 'confirmed') return item.user_confirmed
      if (coCreatedFilter.value === 'pending') return !item.user_confirmed
      return true
    })
    .filter(item => {
      if (!keyword) return true
      return normalizeKeyword([
        item.summary,
        item.memory_type,
        item.scope,
        ...(item.topic_tags || []),
      ].join(' ')).includes(keyword)
    })
})

const filteredForbiddenTopics = computed(() => {
  const keyword = normalizeKeyword(forbiddenSearch.value)
  if (!keyword) return memoryStore.forbiddenTopics
  return memoryStore.forbiddenTopics.filter(item => normalizeKeyword(item.topic).includes(keyword))
})

const profileSummary = computed(() => {
  return memoryStore.tacitProfile?.summary || '伴行正在认识你的节奏、偏好和处事方式。多聊几次后，这里会慢慢长出更像你的画像。'
})

const profileTitle = computed(() => {
  if (!hasTacitProfile()) return '正在认识你'
  if ((memoryStore.tacitProfile?.confidence || 0) >= 0.75) return '越来越像你的侧影'
  return '正在长成你的样子'
})

const portraitChips = computed(() => {
  const sections = profileSections()
  return sections
    .map(section => section.items[0]?.claim)
    .filter(Boolean)
    .map(claim => compactClaim(claim))
    .slice(0, 3)
})

const profileOrbTemplate = computed(() => {
  const text = `${profileSummary.value} ${portraitChips.value.join(' ')}`
  let colors = props.currentSoul?.orb?.colors || ['#FFD8B8', '#FFB088']
  let expression = props.currentSoul?.orb?.expression || 'smile'
  if (!hasTacitProfile()) {
    colors = ['#FFE9CF', '#FFB766']
    expression = 'calm'
  } else if (/健身|运动|跑步|身体/.test(text)) {
    colors = ['#D6F0CC', '#8AD583']
    expression = 'smile'
  } else if (/面试|求职|压力|焦虑|紧张/.test(text)) {
    colors = ['#D5ECFB', '#7DBDEB']
    expression = 'calm'
  } else if (/边界|禁区|不主动/.test(text)) {
    colors = ['#F6F3FF', '#B79BE8']
    expression = 'firm'
  }
  return {
    name: '你的画像小球',
    orb: { colors, expression },
  }
})

function openSection(id) {
  activeSection.value = id
  clearFeedback()
  cancelMemoryEdit()
  if (id === 'tacit') showTacitEvidence.value = true
  if (id === 'documents') {
    clearDocumentFeedback()
    loadActiveDocument()
  }
}

function countLayer(layer) {
  const base = (memoryStore.layers[layer] || []).length
  return layer === 'tacit' && hasTacitProfile() ? base + 1 : base
}

function countDocuments() {
  return (memoryStore.documents || []).filter(item => item.id).length
}

function hasTacitProfile() {
  return !!(memoryStore.tacitProfile?.summary || profileSections().length)
}

function profileSections() {
  const dimensions = memoryStore.tacitProfile?.dimensions || {}
  return Object.entries(dimensions)
    .map(([key, section]) => ({
      key,
      label: section.label || key,
      items: (section.items || []).filter(item => item?.claim),
    }))
    .filter(section => section.items.length > 0)
}

function compactClaim(value) {
  return String(value || '')
    .replace(/^用户(近期)?/, '')
    .replace(/^会关注/, '')
    .replace(/^明确提到过/, '')
    .replace(/[。；].*$/, '')
    .slice(0, 18)
}

function formatConfidence(value) {
  const numeric = Number(value || 0)
  return `${Math.round(numeric * 100)}%`
}

function formatTime(value) {
  if (!value) return '尚未更新'
  try {
    return new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '尚未更新'
  }
}

function normalizeKeyword(value) {
  return String(value || '').trim().toLowerCase()
}

function memoryTypeLabel(value) {
  const map = {
    general: '一般',
    preference: '偏好',
    profile: '画像',
    event: '事件',
    routine: '习惯',
    boundary: '边界',
    insight: '洞察',
  }
  return map[value] || value || '一般'
}

function scopeLabel(value) {
  const map = {
    global: '长期',
    topic: '主题',
    session: '会话',
    ephemeral: '短期',
  }
  return map[value] || '长期'
}

function memoryTags(item) {
  return Array.isArray(item.topic_tags) ? item.topic_tags.slice(0, 4) : []
}

function startMemoryEdit(item) {
  clearFeedback()
  editingMemoryId.value = item.id
  editingSummary.value = item.summary || ''
}

function cancelMemoryEdit() {
  editingMemoryId.value = ''
  editingSummary.value = ''
}

function clearFeedback() {
  notice.value = ''
  errorMessage.value = ''
}

function clearDocumentFeedback() {
  documentNotice.value = ''
  documentError.value = ''
}

async function runAction(action, successText) {
  if (saving.value) return
  saving.value = true
  clearFeedback()
  try {
    await action()
    notice.value = successText
    await refreshMemories()
  } catch (error) {
    errorMessage.value = error?.message || '操作失败'
  } finally {
    saving.value = false
  }
}

async function refreshMemories() {
  if (loading.value) return
  loading.value = true
  try {
    const [data, documents] = await Promise.all([
      apiGetMemories(),
      apiGetMemoryDocuments(),
    ])
    memoryStore.load(data)
    memoryStore.loadDocuments(documents)
    loaded.value = true
  } finally {
    loading.value = false
  }
}

async function refreshDocuments() {
  const documents = await apiGetMemoryDocuments()
  memoryStore.loadDocuments(documents)
}

onMounted(async () => {
  await refreshMemories()
})

watch(() => props.active, async (active) => {
  if (active) {
    activeSection.value = ''
    clearFeedback()
    cancelMemoryEdit()
    await refreshMemories()
  }
})

async function addForbidden() {
  if (!newForbidden.value.trim()) return
  const topic = newForbidden.value.trim()
  await runAction(async () => {
    await apiAddForbidden(topic, '')
    newForbidden.value = ''
  }, '已加入禁区')
}

async function addCoCreatedMemory() {
  const summary = newMemorySummary.value.trim()
  if (!summary) {
    errorMessage.value = '记忆内容不能为空'
    return
  }
  await runAction(async () => {
    const result = await apiCreateMemory({
      summary,
      memory_type: newMemoryType.value || 'general',
    })
    if (result?.success === false) {
      throw new Error(result.message || '新增记忆失败')
    }
    newMemorySummary.value = ''
    newMemoryType.value = 'general'
  }, '已新增记忆')
}

async function removeForbidden(id) {
  await runAction(() => apiRemoveForbidden(id), '已解除禁区')
}

async function confirmMemory(id) {
  await runAction(() => apiUpdateMemory(id, { user_confirmed: true }), '已确认记忆')
}

async function deleteMemory(id) {
  await runAction(() => apiDeleteMemory(id), '已删除记忆')
}

async function saveMemoryEdit(id) {
  const summary = editingSummary.value.trim()
  if (!summary) {
    errorMessage.value = '记忆内容不能为空'
    return
  }
  await runAction(async () => {
    await apiUpdateMemory(id, { summary })
    cancelMemoryEdit()
  }, '已保存记忆')
}

async function loadActiveDocument() {
  if (documentBusy.value) return
  documentBusy.value = true
  clearDocumentFeedback()
  try {
    const document = await apiGetMemoryDocument(activeDocumentType.value)
    documentContent.value = document?.content || ''
    await refreshDocuments()
  } catch (error) {
    documentError.value = error?.message || '文档加载失败'
  } finally {
    documentBusy.value = false
  }
}

async function selectDocument(type) {
  if (activeDocumentType.value === type) return
  activeDocumentType.value = type
  await loadActiveDocument()
}

async function runDocumentAction(action, successText) {
  if (documentBusy.value) return
  documentBusy.value = true
  clearDocumentFeedback()
  try {
    const result = await action()
    if (result?.success === false) {
      throw new Error(result.message || '文档操作失败')
    }
    if (result?.detail) {
      throw new Error(result.detail)
    }
    documentNotice.value = successText
    const document = await apiGetMemoryDocument(activeDocumentType.value)
    documentContent.value = document?.content || ''
    await refreshDocuments()
  } catch (error) {
    documentError.value = error?.message || '文档操作失败'
  } finally {
    documentBusy.value = false
  }
}

async function rebuildCurrentDocument() {
  await runDocumentAction(
    () => apiRebuildMemoryDocuments(activeDocumentType.value, false),
    '已重建文档',
  )
}

async function exportCurrentDocument() {
  await runDocumentAction(
    () => apiExportMemoryDocument(activeDocumentType.value),
    '已导出文件',
  )
}

async function importCurrentDocument() {
  await runDocumentAction(
    () => apiImportMemoryDocument(activeDocumentType.value),
    '已导入文件',
  )
}

async function saveCurrentDocument() {
  await runDocumentAction(
    () => apiUpdateMemoryDocument(activeDocumentType.value, documentContent.value, true),
    '已保存文档',
  )
}

function documentStatusLabel(syncStatus, fileState) {
  if (fileState === 'file_changed') return '文件有更新'
  if (fileState === 'missing_file') return '未导出'
  if (fileState === 'missing_document') return '待生成'
  if (fileState === 'unreadable_file') return '文件不可读'
  const map = {
    synced: '已同步',
    stale: '待刷新',
    conflict: '有冲突',
    import_pending: '待导入',
    export_pending: '待导出',
  }
  return map[syncStatus] || '未同步'
}

</script>

<style scoped>
.memory-root {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.memory-hero {
  text-align: center;
  padding: 18px 0 16px;
  position: relative;
  overflow: hidden;
}

.memory-hero-waves {
  width: 100%;
  height: 16px;
  margin-bottom: 8px;
}

.memory-hero-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 10px;
  background: var(--honey-soft);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.memory-hero-icon svg {
  width: 28px;
  height: 28px;
}

.memory-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}

.memory-sub {
  font-size: 13px;
  color: var(--sub);
  margin-top: 2px;
}

.memory-loading,
.empty-state {
  color: var(--sub);
  font-size: 13px;
  padding: 12px 0;
  text-align: center;
}

.memory-entry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 4px;
}

.memory-entry {
  min-height: 78px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 14px;
  border-radius: var(--r-lg);
  border: 1.5px solid transparent;
  transition: transform .2s ease, box-shadow .2s ease;
  text-align: left;
}

.memory-entry:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,.06);
}

.memory-entry:active {
  transform: scale(.98);
}

.entry-priors {
  background: rgba(255,255,255,.64);
  border-color: rgba(239,230,212,.95);
  color: var(--sub);
}

.entry-co_created {
  background: #FFF8F3;
  border-color: #FFD8B8;
  color: #FF9F45;
}

.entry-tacit {
  background: #F6F3FF;
  border-color: #D4C8F0;
  color: #9B6FD8;
}

.entry-forbidden {
  background: #FFF3F3;
  border-color: #F5C8C8;
  color: #E88D8D;
}

.entry-documents {
  background: #F1FBF6;
  border-color: #BFE8D0;
  color: #55AD72;
}

.entry-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.entry-icon :deep(svg) {
  width: 32px;
  height: 32px;
}

.entry-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.entry-title {
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
}

.entry-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 2px;
}

.entry-count {
  min-width: 44px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  color: var(--ink-soft);
}

.entry-count strong {
  font-size: 19px;
  line-height: 1;
}

.entry-count small {
  margin-top: 2px;
  color: var(--sub);
  font-size: 10px;
}

.entry-arrow {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--sub);
  opacity: .55;
}

.portrait-panel {
  margin: 18px 4px 0;
  padding: 16px;
  border-radius: var(--r-lg);
  background: rgba(255,255,255,.72);
  border: 1px solid rgba(255,255,255,.9);
  box-shadow: var(--shadow-sm);
}

.portrait-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.portrait-head.compact {
  margin-bottom: 12px;
}

.portrait-orb {
  width: 92px;
  height: 92px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: profile-orb-bob 3.2s ease-in-out infinite;
}

.portrait-orb.small {
  width: 58px;
  height: 58px;
}

@keyframes profile-orb-bob {
  0%,100% { transform: translateY(0) rotate(-1.5deg); }
  50% { transform: translateY(-5px) rotate(1.5deg); }
}

.portrait-info {
  flex: 1;
  min-width: 0;
}

.portrait-kicker {
  color: var(--sub);
  font-size: 11px;
  font-weight: 700;
}

.portrait-title {
  margin-top: 2px;
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
}

.portrait-meta {
  margin-top: 4px;
  color: var(--sub);
  font-size: 11px;
  line-height: 1.35;
}

.portrait-summary {
  margin-top: 12px;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-line;
}

.portrait-summary.detail {
  margin-top: 0;
}

.portrait-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.portrait-chips span {
  max-width: 100%;
  padding: 5px 9px;
  border-radius: 12px;
  background: var(--cream-2);
  color: var(--ink-soft);
  font-size: 11px;
  font-weight: 600;
}

.portrait-evidence-link,
.tacit-evidence-btn {
  margin-top: 10px;
  padding: 6px 0;
  color: var(--honey-deep);
  font-size: 12px;
  font-weight: 700;
}

.detail-scroll {
  padding-top: 10px;
}

.detail-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 7px 8px;
  border-radius: var(--r-sm);
  color: var(--ink-soft);
  font-size: 13px;
}

.back-btn:active {
  background: var(--line);
}

.back-btn svg {
  width: 17px;
  height: 17px;
}

.detail-title {
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
}

.detail-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 1px;
}

.detail-card {
  background: var(--card);
  border-radius: var(--r-md);
  padding: 10px 14px;
  box-shadow: var(--shadow-sm);
}

.tacit-detail {
  padding: 14px;
}

.memory-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}

.memory-row:last-child {
  border-bottom: none;
}

.memory-row.editable {
  justify-content: space-between;
  align-items: flex-start;
}

.row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.row-tag {
  flex-shrink: 0;
  margin-top: 1px;
  padding: 3px 8px;
  border-radius: 8px;
  background: var(--cream-2);
  color: var(--ink-soft);
  font-size: 10px;
  font-weight: 700;
}

.row-tag.pending {
  color: var(--honey-deep);
  background: var(--honey-soft);
}

.row-tag.warn,
.row-tag.forbidden {
  color: var(--berry);
  background: var(--berry-soft);
}

.row-text {
  flex: 1;
  min-width: 0;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
}

.row-actions {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.action-confirm,
.action-delete,
.action-neutral {
  flex-shrink: 0;
  padding: 4px 6px;
  font-size: 12px;
  border-radius: 8px;
}

.action-confirm {
  color: var(--sprout);
}

.action-delete {
  color: var(--berry);
}

.action-neutral {
  color: var(--ink-soft);
}

.co-created-detail {
  max-height: calc(100vh - 176px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.memory-add-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 10px;
}

.add-memory-input {
  min-height: 68px;
}

.type-picker {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.type-picker button {
  min-width: 0;
  min-height: 36px;
  padding: 8px 6px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,.78);
  color: var(--ink-soft);
  font-size: 13px;
  font-weight: 700;
  text-align: center;
}

.type-picker button.active {
  border-color: var(--honey-deep);
  background: var(--honey-soft);
  color: var(--honey-deep);
}

.memory-add-actions {
  display: flex;
  justify-content: flex-end;
}

.memory-list-scroll {
  flex: 1;
  min-height: 220px;
  max-height: none;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 0 8px 0 0;
  margin-top: 8px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  scrollbar-width: thin;
  scrollbar-color: rgba(166,145,109,.42) rgba(255,255,255,.5);
}

.memory-list-scroll .memory-row:first-child {
  padding-top: 10px;
}

.memory-list-scroll::-webkit-scrollbar {
  width: 6px;
}

.memory-list-scroll::-webkit-scrollbar-track {
  background: rgba(255,255,255,.58);
  border-radius: 999px;
}

.memory-list-scroll::-webkit-scrollbar-thumb {
  background: rgba(166,145,109,.46);
  border-radius: 999px;
}

@media (max-width: 420px) {
  .type-picker {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .memory-add-actions .add-btn {
    width: 100%;
  }
}

.detail-tools {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 4px;
}

.segmented {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 3px;
  border-radius: 10px;
  background: var(--cream-2);
}

.segmented button {
  min-height: 30px;
  border-radius: 8px;
  color: var(--sub);
  font-size: 12px;
  font-weight: 700;
}

.segmented button.active {
  background: var(--card);
  color: var(--honey-deep);
  box-shadow: var(--shadow-sm);
}

.row-content {
  flex: 1;
  min-width: 0;
}

.row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}

.row-meta span {
  max-width: 100%;
  padding: 2px 6px;
  border-radius: 7px;
  background: var(--cream-2);
  color: var(--sub);
  font-size: 10px;
  line-height: 1.4;
  word-break: break-word;
}

.edit-input {
  width: 100%;
  min-height: 74px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255,255,255,.9);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
}

.edit-input:focus {
  border-color: var(--honey-deep);
  box-shadow: 0 0 0 3px rgba(255,159,69,.14);
}

.inline-notice,
.inline-error {
  margin: 8px 0 2px;
  padding: 7px 9px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.4;
}

.inline-notice {
  color: var(--sprout);
  background: var(--sprout-soft);
}

.inline-error {
  color: var(--berry);
  background: var(--berry-soft);
}

.inline-form {
  display: flex;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 2px;
}

.inline-form .form-input {
  flex: 1;
  min-width: 0;
}

.document-detail {
  max-height: calc(100vh - 176px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.document-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 5px;
  padding: 4px;
  border-radius: 12px;
  background: var(--cream-2);
}

.document-tabs button {
  min-height: 34px;
  padding: 7px 5px;
  border-radius: 9px;
  color: var(--sub);
  font-size: 11px;
  font-weight: 800;
}

.document-tabs button.active {
  background: var(--card);
  color: var(--sprout);
  box-shadow: var(--shadow-sm);
}

.document-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.document-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.document-meta span {
  padding: 3px 7px;
  border-radius: 8px;
  background: var(--cream-2);
  color: var(--ink-soft);
  font-size: 10px;
  font-weight: 700;
}

.document-path {
  padding: 7px 9px;
  border-radius: 9px;
  background: rgba(255,255,255,.7);
  color: var(--sub);
  font-size: 11px;
  line-height: 1.4;
  word-break: break-all;
}

.document-editor {
  flex: 1;
  min-height: 320px;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255,255,255,.92);
  color: var(--ink);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  resize: none;
  outline: none;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(112,166,125,.42) rgba(255,255,255,.5);
}

.document-editor:focus {
  border-color: var(--sprout);
  box-shadow: 0 0 0 3px rgba(91,179,112,.14);
}

.search-input {
  margin: 8px 0 2px;
}

.add-btn {
  width: auto;
  flex-shrink: 0;
  padding: 10px 14px;
  font-size: 13px;
}

.tacit-evidence {
  margin-top: 4px;
}

.evidence-section {
  margin-top: 10px;
}

.evidence-title {
  color: var(--sub);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
}

.evidence-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}

.evidence-row span {
  flex: 1;
  min-width: 0;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.evidence-row small {
  flex-shrink: 0;
  color: var(--sub);
  font-size: 11px;
  white-space: nowrap;
}
</style>

<style>
.memory-root {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.memory-root .memory-hero {
  text-align: center;
  padding: 18px 0 16px;
  position: relative;
  overflow: hidden;
}

.memory-root .memory-hero-waves {
  width: 100%;
  height: 16px;
  margin-bottom: 8px;
}

.memory-root .memory-hero-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 10px;
  background: var(--honey-soft);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.memory-root .memory-hero-icon svg {
  width: 28px;
  height: 28px;
}

.memory-root .memory-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}

.memory-root .memory-sub {
  font-size: 13px;
  color: var(--sub);
  margin-top: 2px;
}

.memory-root .memory-entry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 4px;
}

.memory-root .memory-entry {
  width: 100%;
  min-height: 78px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: var(--r-lg);
  border: 1.5px solid transparent;
  text-align: left;
}

.memory-root .entry-priors {
  background: rgba(255,255,255,.64);
  border-color: rgba(239,230,212,.95);
  color: var(--sub);
}

.memory-root .entry-co_created {
  background: #FFF8F3;
  border-color: #FFD8B8;
  color: #FF9F45;
}

.memory-root .entry-tacit {
  background: #F6F3FF;
  border-color: #D4C8F0;
  color: #9B6FD8;
}

.memory-root .entry-forbidden {
  background: #FFF3F3;
  border-color: #F5C8C8;
  color: #E88D8D;
}

.memory-root .entry-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.memory-root .entry-icon svg {
  width: 32px;
  height: 32px;
}

.memory-root .entry-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.memory-root .entry-title {
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
}

.memory-root .entry-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 2px;
}

.memory-root .entry-count {
  min-width: 44px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  color: var(--ink-soft);
}

.memory-root .entry-count strong {
  font-size: 19px;
  line-height: 1;
}

.memory-root .entry-count small {
  margin-top: 2px;
  color: var(--sub);
  font-size: 10px;
}

.memory-root .entry-arrow {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--sub);
  opacity: .55;
}

.memory-root .portrait-panel,
.memory-root .detail-card {
  background: rgba(255,255,255,.72);
  border-radius: var(--r-lg);
  border: 1px solid rgba(255,255,255,.9);
  box-shadow: var(--shadow-sm);
}

.memory-root .portrait-panel {
  margin: 18px 4px 0;
  padding: 16px;
}

.memory-root .portrait-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.memory-root .portrait-head.compact {
  margin-bottom: 12px;
}

.memory-root .portrait-orb {
  width: 92px;
  height: 92px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: profile-orb-bob 3.2s ease-in-out infinite;
}

.memory-root .portrait-orb.small {
  width: 58px;
  height: 58px;
}

.memory-root .portrait-info {
  flex: 1;
  min-width: 0;
}

.memory-root .portrait-kicker {
  color: var(--sub);
  font-size: 11px;
  font-weight: 700;
}

.memory-root .portrait-title {
  margin-top: 2px;
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
}

.memory-root .portrait-meta {
  margin-top: 4px;
  color: var(--sub);
  font-size: 11px;
  line-height: 1.35;
}

.memory-root .portrait-summary {
  margin-top: 12px;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-line;
}

.memory-root .portrait-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.memory-root .portrait-chips span {
  max-width: 100%;
  padding: 5px 9px;
  border-radius: 12px;
  background: var(--cream-2);
  color: var(--ink-soft);
  font-size: 11px;
  font-weight: 600;
}

.memory-root .portrait-evidence-link,
.memory-root .tacit-evidence-btn {
  margin-top: 10px;
  padding: 6px 0;
  color: var(--honey-deep);
  font-size: 12px;
  font-weight: 700;
}

.memory-root .detail-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.memory-root .back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 7px 8px;
  border-radius: var(--r-sm);
  color: var(--ink-soft);
  font-size: 13px;
}

.memory-root .back-btn svg {
  width: 17px;
  height: 17px;
}

.memory-root .detail-title {
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
}

.memory-root .detail-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 1px;
}

.memory-root .detail-card {
  padding: 10px 14px;
}

.memory-root .memory-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}

.memory-root .memory-row:last-child {
  border-bottom: none;
}

.memory-root .memory-row.editable {
  justify-content: space-between;
  align-items: flex-start;
}

.memory-root .row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.memory-root .row-tag {
  flex-shrink: 0;
  margin-top: 1px;
  padding: 3px 8px;
  border-radius: 8px;
  background: var(--cream-2);
  color: var(--ink-soft);
  font-size: 10px;
  font-weight: 700;
}

.memory-root .row-text {
  flex: 1;
  min-width: 0;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
}

@keyframes profile-orb-bob {
  0%,100% { transform: translateY(0) rotate(-1.5deg); }
  50% { transform: translateY(-5px) rotate(1.5deg); }
}
</style>
