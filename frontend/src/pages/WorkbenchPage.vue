<template>
  <div class="workbench-root">
    <!-- 工具首页 -->
    <div v-if="!activeTool" class="scroll">
      <div class="hero">
        <svg viewBox="0 0 120 20" class="hero-waves">
          <path d="M0 10 Q30 0 60 10 T120 10" stroke="var(--honey-soft)" fill="none" stroke-width="2"/>
          <path d="M0 14 Q30 4 60 14 T120 14" stroke="var(--sprout-soft)" fill="none" stroke-width="1.5" opacity=".6"/>
        </svg>
        <div class="hero-icon">
          <svg viewBox="0 0 32 32" fill="none" stroke="var(--honey-deep)" stroke-width="1.5">
            <rect x="4" y="8" width="24" height="20" rx="3"/>
            <path d="M8 8V6a2 2 0 012-2h12a2 2 0 012 2v2"/>
            <line x1="16" y1="14" x2="16" y2="22"/>
            <line x1="12" y1="18" x2="20" y2="18"/>
          </svg>
        </div>
        <div class="hero-title">工作台</div>
        <div class="hero-sub">选择工具，开始你的任务</div>
      </div>

      <div class="tool-grid">
        <div v-for="t in tools" :key="t.id" class="tool-card" :class="'card-' + t.id" @click="openTool(t.id)">
          <div class="card-icon" v-html="t.icon"></div>
          <div class="card-info">
            <div class="card-title">{{ t.label }}</div>
            <div class="card-desc">{{ t.desc }}</div>
          </div>
        </div>
      </div>

      <div v-if="recentItems.length > 0" class="recent-section">
        <div class="recent-header">
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="var(--sub)" stroke-width="1.5">
            <circle cx="10" cy="10" r="8"/>
            <polyline points="10,5 10,10 14,12"/>
          </svg>
          <span>最近使用</span>
        </div>
        <div v-for="item in showAllRecent ? recentItems : recentItems.slice(0, 3)" :key="item.id" class="recent-item" @click="openRecent(item)">
          <div class="recent-dot" :style="{background: item.color}"></div>
          <div class="recent-body">
            <div class="recent-title">{{ item.title }}</div>
            <div class="recent-meta">{{ item.toolLabel }} · {{ item.time }}</div>
          </div>
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="var(--sub)" stroke-width="1.5" class="recent-arrow">
            <polyline points="7,4 14,10 7,16"/>
          </svg>
        </div>
      </div>
      <div v-if="hasMoreRecent" style="text-align:center;margin-top:8px;">
        <button class="more-btn" @click="showAllRecent = !showAllRecent">{{ showAllRecent ? '收起' : '查看更多' }}</button>
      </div>
    </div>

    <!-- 工具页（KeepAlive 保持各工具状态） -->
    <KeepAlive v-else>
      <InterviewPage v-if="activeTool === 'interview'" :embedded="true" :origin="toolOrigin" @back="handleToolBack" />
      <FinancePage v-else-if="activeTool === 'finance'" :origin="toolOrigin" @back="handleToolBack" />
      <TravelPage v-else-if="activeTool === 'travel'" :origin="toolOrigin" @back="handleToolBack" />
      <ShoppingPage v-else-if="activeTool === 'shopping'" :origin="toolOrigin" @back="handleToolBack" />
      <div v-else class="placeholder-page">
        <div class="back-bar">
          <button @click="handleToolBack" class="back-btn">
            <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5">
              <polyline points="13,4 7,10 13,16"/>
            </svg>
            返回工作台
          </button>
        </div>
        <div class="placeholder-body">
          <div class="placeholder-icon" v-html="currentTool?.icon || ''"></div>
          <div class="placeholder-title">{{ currentTool?.label || '工具' }}</div>
          <div class="placeholder-desc">正在开发中，敬请期待</div>
        </div>
      </div>
    </KeepAlive>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import InterviewPage from './InterviewPage.vue'
import FinancePage from './FinancePage.vue'
import TravelPage from './TravelPage.vue'
import ShoppingPage from './ShoppingPage.vue'

const props = defineProps({
  openToolRequest: { type: Object, default: null },
})
const emit = defineEmits(['back-to-chat'])

const activeTool = ref('')
/** 工具打开来源：'home' 工作台首页 | 'chat' 从聊天跳转 */
const toolOrigin = ref('home')

const tools = [
  {
    id: 'interview', label: '面试训练', desc: '模拟面试 + AI 评估',
    color: '#FF9F45', bgColor: '#FFF5EE',
    icon: '<svg viewBox="0 0 32 32" fill="none" stroke="#FF9F45" stroke-width="1.5"><circle cx="16" cy="10" r="5"/><path d="M10 24c0-3.3 2.7-6 6-6s6 2.7 6 6"/><rect x="5" y="18" width="22" height="10" rx="2" opacity=".3"/></svg>',
  },
  {
    id: 'travel', label: '旅游规划', desc: '行程定制 + 预算管理',
    color: '#5FBE63', bgColor: '#F0FAF4',
    icon: '<svg viewBox="0 0 32 32" fill="none" stroke="#5FBE63" stroke-width="1.5"><circle cx="16" cy="16" r="10"/><path d="M6 16h20M16 6c3 3.3 3 10.7 3 14M16 6c-3 3.3-3 10.7-3 14"/><line x1="16" y1="6" x2="16" y2="26"/></svg>',
  },
  {
    id: 'shopping', label: '购物计划', desc: '比价清单 + 智能推荐',
    color: '#E88D8D', bgColor: '#FFF0F0',
    icon: '<svg viewBox="0 0 32 32" fill="none" stroke="#E88D8D" stroke-width="1.5"><path d="M6 8h20l-2 14H8L6 8z"/><circle cx="10" cy="26" r="2"/><circle cx="22" cy="26" r="2"/><path d="M10 12V8c0-3.3 2.7-6 6-6s6 2.7 6 6v4"/></svg>',
  },
  {
    id: 'finance', label: '记账', desc: '收支记录 + 分类统计',
    color: '#9B6FD8', bgColor: '#F5F0FF',
    icon: '<svg viewBox="0 0 32 32" fill="none" stroke="#9B6FD8" stroke-width="1.5"><rect x="4" y="6" width="24" height="20" rx="2"/><line x1="4" y1="12" x2="28" y2="12"/><line x1="12" y1="12" x2="12" y2="26"/><circle cx="16" cy="18" r="2"/></svg>',
  },
]

const currentTool = computed(() => tools.find(t => t.id === activeTool.value))

const recentItems = ref([])
const hasMoreRecent = ref(false)
const showAllRecent = ref(false)

onMounted(loadRecent)

async function loadRecent() {
  try {
    const token = localStorage.getItem('comate_token')
    const headers = { 'Authorization': `Bearer ${token}` }
    const now = new Date()

    // 带重试的 fetch（本地开发代理偶发连接中断时兜底）
    const fetchJson = async (url) => {
      for (let i = 0; i < 2; i++) {
        try {
          const res = await fetch(url, { headers })
          if (res.ok) return await res.json()
        } catch (e) {
          if (i === 0) console.warn('[recent] 请求失败，重试:', url, e.message)
          await new Promise(r => setTimeout(r, 300))
        }
      }
      return null
    }

    // 面试记录
    const interviewData = await fetchJson('/api/interview') || {}
    const sessions = (interviewData.data?.sessions || interviewData.sessions || []).map(s => ({
      id: s.id, toolId: 'interview', toolLabel: '面试训练', color: '#FF9F45',
      title: s.title || s.target_role || '未命名',
      sortTime: s.created_at || '',
      time: s.created_at ? new Date(s.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
    }))

    // 记账记录（最近 2 条）
    const finData = await fetchJson(`/api/finance/records?year=${now.getFullYear()}&month=${now.getMonth() + 1}`)
    const records = finData?.data || finData || []
    const financeItems = records.slice(0, 2).map(r => ({
      id: r.id, toolId: 'finance', toolLabel: '记账', color: '#9B6FD8',
      title: `${r.type === 'income' ? '+' : '-'}¥${(r.amount / 100).toFixed(2)} ${r.category}`,
      sortTime: r.created_at || r.record_date || '',
      time: r.created_at ? new Date(r.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : (r.record_date || ''),
    }))

    // 购物方案（最近 2 条）
    const shopData = await fetchJson('/api/shopping/history')
    const shopPlans = shopData?.data || shopData || []
    const shoppingItems = shopPlans.slice(0, 2).map(p => ({
      id: p.id, toolId: 'shopping', toolLabel: '购物计划', color: '#E88D8D',
      title: `🛒 ${p.demand}`,
      sortTime: p.created_at || '',
      time: p.created_at ? new Date(p.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
    }))

    // 旅游规划（最近 2 条）
    const travelData = await fetchJson('/api/travel/plans')
    const travelPlans = travelData?.data || travelData || []
    const travelItems = travelPlans.slice(0, 2).map(p => ({
      id: p.id, toolId: 'travel', toolLabel: '旅游规划', color: '#5FBE63',
      title: `✈️ ${p.destination}${p.title ? ' · ' + p.title : ''}`,
      sortTime: p.updated_at || p.created_at || '',
      time: (p.updated_at || p.created_at) ? new Date(p.updated_at || p.created_at).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
    }))

    // 合并、排序、截取 6 条
    const all = [...sessions, ...financeItems, ...shoppingItems, ...travelItems].sort((a, b) => (b.sortTime || '').localeCompare(a.sortTime || ''))
    recentItems.value = all
    hasMoreRecent.value = all.length > 3
  } catch {}
}

function openRecent(item) {
  openTool(item.toolId, 'home')
}

function openTool(toolId, origin = 'home') {
  if (!tools.some(t => t.id === toolId)) return
  toolOrigin.value = origin
  activeTool.value = toolId
}

/** 工具页返回：从聊天跳转的回到聊天，其余回工作台首页 */
function handleToolBack() {
  const fromChat = toolOrigin.value === 'chat'
  activeTool.value = ''
  if (fromChat) emit('back-to-chat')
}

watch(
  () => props.openToolRequest,
  (request) => openTool(request?.toolId, 'chat'),
  { immediate: true }
)
</script>

<style scoped>
.hero { text-align: center; padding: 24px 0 18px; position: relative; overflow: hidden; }
.hero-waves { width: 100%; height: 16px; margin-bottom: 10px; }
.hero-icon {
  width: 48px; height: 48px; margin: 0 auto 10px;
  background: var(--honey-soft); border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
}
.hero-icon svg { width: 28px; height: 28px; }
.hero-title { font-size: 22px; font-weight: 700; color: var(--ink); }
.hero-sub { font-size: 13px; color: var(--sub); margin-top: 2px; }
.tool-grid { display: flex; flex-direction: column; gap: 8px; padding: 0 4px; }
.tool-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; border-radius: var(--r-lg);
  cursor: pointer; transition: all .2s ease;
  border: 1.5px solid transparent;
}
.tool-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,.06); }
.tool-card:active { transform: scale(.98); }
.card-interview { background: #FFF8F3; border-color: #FFD8B8; }
.card-travel { background: #F3FBF5; border-color: #B8E8C8; }
.card-shopping { background: #FFF3F3; border-color: #F5C8C8; }
.card-finance { background: #F6F3FF; border-color: #D4C8F0; }
.card-icon { width: 44px; height: 44px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.card-icon svg { width: 32px; height: 32px; }
.card-info { flex: 1; min-width: 0; }
.card-title { font-size: 15px; font-weight: 600; color: var(--ink); }
.card-desc { font-size: 12px; color: var(--sub); margin-top: 1px; }
.recent-section { margin-top: 22px; padding: 0 4px; }
.recent-header { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--sub); margin-bottom: 8px; }
.recent-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--r-md); cursor: pointer; transition: background .15s; margin-top: 4px; }
.recent-item:hover { background: var(--honey-soft); }
.recent-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.recent-body { flex: 1; min-width: 0; }
.recent-title { font-size: 14px; font-weight: 500; color: var(--ink); }
.recent-meta { font-size: 12px; color: var(--sub); margin-top: 1px; }
.recent-arrow { flex-shrink: 0; opacity: .4; }
.more-btn { font-size: 13px; color: var(--honey); padding: 6px 16px; border: 1px solid var(--honey-soft); border-radius: var(--r-sm); background: none; cursor: pointer; transition: background .15s; }
.more-btn:hover { background: var(--honey-soft); }
.placeholder-page { display: flex; flex-direction: column; height: 100%; }
.back-bar { display: flex; align-items: center; padding: 4px 4px; }
.back-btn { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--ink-soft); padding: 6px 8px; background: none; border: none; cursor: pointer; }
.back-btn:hover { color: var(--ink); }
.placeholder-body { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px; }
.placeholder-icon svg { width: 64px; height: 64px; opacity: .4; }
.placeholder-title { font-size: 18px; font-weight: 600; color: var(--ink); margin-top: 12px; }
.placeholder-desc { font-size: 14px; color: var(--sub); margin-top: 4px; }
</style>
