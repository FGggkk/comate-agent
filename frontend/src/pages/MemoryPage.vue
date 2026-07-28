<template>
  <div class="scroll">
    <div class="page-title">记忆</div>

    <div v-if="!loaded" style="text-align:center;color:var(--sub);padding:20px 0;">加载中...</div>

    <template v-else>
      <!-- 三层卡片 -->
      <div class="mem-layers">
        <div class="mlayer g"><div class="mn">先验层</div><div class="md">系统已知信息</div><div class="mc">{{ countLayer('priors') }}<small> 条</small></div></div>
        <div class="mlayer o"><div class="mn">共建层</div><div class="md">你主动告诉我的</div><div class="mc">{{ countLayer('co_created') }}<small> 条</small></div></div>
        <div class="mlayer p"><div class="mn">默契层</div><div class="md">长期互动沉淀</div><div class="mc">{{ countLayer('tacit') }}<small> 条</small></div></div>
      </div>

      <!-- 记忆列表：先验层 -->
      <div class="page-label" style="margin-top:16px;">🧠 先验层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="m in memoryStore.layers.priors" :key="m.id" class="mitem">
          <span class="mtype">先验</span>
          <span class="mtext">{{ m.summary }}</span>
        </div>
        <div v-if="memoryStore.layers.priors.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无先验记忆</div>
      </div>

      <!-- 记忆列表：共建层 -->
      <div class="page-label" style="margin-top:16px;">🤝 共建层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="m in memoryStore.layers.co_created" :key="m.id" style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);">
          <span class="mtext" style="flex:1;font-size:14px;">{{ m.summary }}</span>
          <button v-if="!m.user_confirmed" @click="confirmMemory(m.id)" style="font-size:12px;color:var(--sprout);padding:4px 8px;">确认</button>
          <button @click="deleteMemory(m.id)" style="font-size:12px;color:var(--berry);padding:4px 8px;">删除</button>
        </div>
        <div v-if="memoryStore.layers.co_created.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无共建记忆</div>
      </div>

      <!-- 记忆列表：默契层 -->
      <div class="page-label" style="margin-top:16px;">💭 默契层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-if="hasTacitProfile()" style="padding:4px 0 8px;">
          <div class="tacit-profile-text">{{ memoryStore.tacitProfile.summary || '伴行正在形成对你的长期理解。' }}</div>
          <div style="font-size:11px;color:var(--sub);margin-top:4px;">
            v{{ memoryStore.tacitProfile.version_no || 0 }} · 置信度 {{ formatConfidence(memoryStore.tacitProfile.confidence) }} · {{ formatTime(memoryStore.tacitProfile.last_analyzed_at || memoryStore.tacitProfile.updated_at) }}
          </div>
          <button v-if="profileSections().length || memoryStore.layers.tacit.length" @click="showTacitEvidence = !showTacitEvidence" class="tacit-evidence-btn">
            {{ showTacitEvidence ? '收起画像依据' : '查看画像依据' }}
          </button>
          <div v-if="showTacitEvidence" class="tacit-evidence">
            <div v-for="section in profileSections()" :key="section.key" style="margin-top:10px;">
              <div style="font-size:12px;color:var(--sub);font-weight:700;margin-bottom:4px;">{{ section.label }}</div>
              <div v-for="item in section.items" :key="item.claim" style="display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-bottom:1px solid var(--line);">
                <span style="flex:1;font-size:13px;line-height:1.45;color:var(--ink);">{{ item.claim }}</span>
                <span style="font-size:11px;color:var(--sub);white-space:nowrap;">{{ formatConfidence(item.confidence) }} · {{ item.evidence_count || 1 }}次</span>
              </div>
            </div>
            <div v-for="m in memoryStore.layers.tacit" :key="m.id" class="mitem">
              <span class="mtype warn">推断</span>
              <span class="mtext">{{ m.summary }}</span>
            </div>
          </div>
        </div>

        <div v-if="!hasTacitProfile()">
          <div v-for="m in memoryStore.layers.tacit" :key="m.id" class="mitem">
            <span class="mtype warn">推断</span>
            <span class="mtext">{{ m.summary }}</span>
          </div>
        </div>
        <div v-if="!hasTacitProfile() && memoryStore.layers.tacit.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无默契记忆</div>
      </div>

      <!-- 禁区 -->
      <div class="page-label" style="margin-top:16px;">🚫 禁区话题</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="f in memoryStore.forbiddenTopics" :key="f.id" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);">
          <span style="font-size:14px;">{{ f.topic }}</span>
          <button @click="removeForbidden(f.id)" style="font-size:12px;color:var(--berry);padding:4px 8px;">解除</button>
        </div>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <input v-model="newForbidden" placeholder="添加禁区话题..." class="form-input" style="flex:1;" />
          <button @click="addForbidden" class="btn-primary" style="width:auto;padding:10px 16px;font-size:13px;">添加</button>
        </div>
      </div>

      <!-- 未完待续 -->
      <div class="page-label" style="margin-top:16px;">📌 未完待续</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="a in memoryStore.pendingAnchors" :key="a.id" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);">
          <span style="font-size:14px;">{{ a.topic }}</span>
          <button @click="fulfillAnchor(a.id)" style="font-size:12px;color:var(--sprout);padding:4px 8px;">已完成</button>
        </div>
        <div v-if="memoryStore.pendingAnchors.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无待续话题</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useMemoryStore } from '../stores/memory'
import { apiGetMemories, apiUpdateMemory, apiDeleteMemory, apiAddForbidden, apiRemoveForbidden, apiFulfillAnchor } from '../api/index'

const props = defineProps({
  active: { type: Boolean, default: false },
})
const memoryStore = useMemoryStore()
const loaded = ref(false)
const loading = ref(false)
const newForbidden = ref('')
const showTacitEvidence = ref(false)

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
  if (active) await refreshMemories()
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
.tacit-profile-text {
  color: var(--ink);
  font-size: 15px;
  line-height: 1.75;
  white-space: pre-line;
}

.tacit-evidence-btn {
  margin-top: 10px;
  padding: 6px 0;
  color: var(--honey-deep);
  font-size: 12px;
  font-weight: 700;
}

.tacit-evidence {
  margin-top: 2px;
  padding-top: 2px;
}
</style>
