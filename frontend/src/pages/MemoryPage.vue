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

      <section v-else-if="activeSection === 'co_created'" class="detail-card">
        <div v-for="m in memoryStore.layers.co_created" :key="m.id" class="memory-row editable">
          <div class="row-main">
            <span :class="['row-tag', m.user_confirmed ? '' : 'pending']">{{ m.user_confirmed ? '已确认' : '待确认' }}</span>
            <span class="row-text">{{ m.summary }}</span>
          </div>
          <div class="row-actions">
            <button v-if="!m.user_confirmed" class="action-confirm" @click="confirmMemory(m.id)">确认</button>
            <button class="action-delete" @click="deleteMemory(m.id)">删除</button>
          </div>
        </div>
        <EmptyState v-if="memoryStore.layers.co_created.length === 0" text="暂无共建记忆" />
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
          <button class="btn-primary add-btn" @click="addForbidden">添加</button>
        </div>
        <div v-for="f in memoryStore.forbiddenTopics" :key="f.id" class="memory-row editable">
          <div class="row-main">
            <span class="row-tag forbidden">禁区</span>
            <span class="row-text">{{ f.topic }}</span>
          </div>
          <button class="action-delete" @click="removeForbidden(f.id)">解除</button>
        </div>
        <EmptyState v-if="memoryStore.forbiddenTopics.length === 0" text="暂无禁区话题" />
      </section>

      <section v-else-if="activeSection === 'anchors'" class="detail-card">
        <div v-for="a in memoryStore.pendingAnchors" :key="a.id" class="memory-row editable">
          <div class="row-main">
            <span class="row-tag anchor">待续</span>
            <span class="row-text">{{ a.topic }}</span>
          </div>
          <button class="action-confirm" @click="fulfillAnchor(a.id)">已完成</button>
        </div>
        <EmptyState v-if="memoryStore.pendingAnchors.length === 0" text="暂无待续话题" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref, onMounted, watch } from 'vue'
import { useMemoryStore } from '../stores/memory'
import { apiGetMemories, apiUpdateMemory, apiDeleteMemory, apiAddForbidden, apiRemoveForbidden, apiFulfillAnchor } from '../api/index'
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
const showTacitEvidence = ref(false)

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
  anchors: '<svg viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M11 4l10 10"/><path d="M9 17l6-6 6 6-6 11z"/><path d="M4 28h24"/></svg>',
}

const memoryEntries = computed(() => [
  { id: 'priors', label: '先验层', desc: '系统规则与安全边界', count: countLayer('priors'), unit: '条', icon: icons.priors },
  { id: 'co_created', label: '共建层', desc: '你确认留下的事实', count: countLayer('co_created'), unit: '条', icon: icons.co_created },
  { id: 'tacit', label: '默契层', desc: '跨会话形成的人物画像', count: countLayer('tacit'), unit: '份', icon: icons.tacit },
  { id: 'forbidden', label: '禁区话题', desc: '不主动触碰的边界', count: memoryStore.forbiddenTopics.length, unit: '条', icon: icons.forbidden },
  { id: 'anchors', label: '未完待续', desc: '短期保留的对话断点', count: memoryStore.pendingAnchors.length, unit: '个', icon: icons.anchors },
])

const currentEntry = computed(() => memoryEntries.value.find(item => item.id === activeSection.value))

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
  if (id === 'tacit') showTacitEvidence.value = true
}

function countLayer(layer) {
  const base = (memoryStore.layers[layer] || []).length
  return layer === 'tacit' && hasTacitProfile() ? base + 1 : base
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

async function refreshMemories() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await apiGetMemories()
    memoryStore.load(data)
    loaded.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await refreshMemories()
})

watch(() => props.active, async (active) => {
  if (active) {
    activeSection.value = ''
    await refreshMemories()
  }
})

async function addForbidden() {
  if (!newForbidden.value.trim()) return
  await apiAddForbidden(newForbidden.value, '')
  newForbidden.value = ''
  await refreshMemories()
}

async function removeForbidden(id) {
  await apiRemoveForbidden(id)
  await refreshMemories()
}

async function confirmMemory(id) {
  await apiUpdateMemory(id, { user_confirmed: true })
  await refreshMemories()
}

async function deleteMemory(id) {
  await apiDeleteMemory(id)
  await refreshMemories()
}

async function fulfillAnchor(id) {
  await apiFulfillAnchor(id)
  await refreshMemories()
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

.entry-anchors {
  background: #F3FBF5;
  border-color: #B8E8C8;
  color: #5FBE63;
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

.row-tag.anchor {
  color: var(--sprout);
  background: var(--sprout-soft);
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
  gap: 4px;
}

.action-confirm,
.action-delete {
  flex-shrink: 0;
  padding: 4px 6px;
  font-size: 12px;
}

.action-confirm {
  color: var(--sprout);
}

.action-delete {
  color: var(--berry);
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

.memory-root .entry-anchors {
  background: #F3FBF5;
  border-color: #B8E8C8;
  color: #5FBE63;
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
