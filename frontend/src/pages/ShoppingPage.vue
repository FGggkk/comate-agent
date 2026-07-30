<template>
  <div :class="['scroll', activeTab === 'shop' ? 'scroll-chat' : '']">
    <div class="back-bar">
      <button @click="$emit('back')" class="back-btn">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="13,4 7,10 13,16"/></svg>
        返回工作台
      </button>
    </div>

    <div class="tabs">
      <button :class="['tab', activeTab === 'shop' ? 'active' : '']" @click="switchTab('shop')">🛒 购物</button>
      <button :class="['tab', activeTab === 'history' ? 'active' : '']" @click="switchTab('history')">📋 历史</button>
    </div>

    <!-- 购物标签 -->
    <div v-if="activeTab === 'shop'" class="shop-section">
      <!-- 搜索进度（有任务无方案） -->
      <div v-if="store.currentTaskId && !store.currentPlans" class="progress-section">
        <div v-if="store.progress.phase === 'searching'" class="progress-wrap">
          <div class="progress-title">📦 搜索商品价格</div>
          <div class="progress-list">
            <div v-for="(p, i) in store.progress.parts" :key="i" class="progress-item">
              <span>{{ store.progress.results[i] ? '✅' : (i <= store.progress.current ? '🔄' : '⏳') }}</span>
              <span>{{ p.name }}</span>
            </div>
          </div>
          <div class="progress-bar-wrap">
            <div class="progress-bar"><div class="progress-fill" :style="{width: store.progress.total > 0 ? (store.progress.results.length/store.progress.total*100) + '%' : '0%'}"></div></div>
            <div class="progress-pct">{{ store.progress.total > 0 ? Math.round(store.progress.results.length/store.progress.total*100) : 0 }}%</div>
          </div>
        </div>
        <div v-else-if="store.progress.phase === 'building'" class="progress-wrap">
          <div class="progress-title">🧠 正在生成推荐方案</div>
          <div class="analyzing-anim"><span class="spinner"></span> AI 正在分析搜索结果，请稍候...</div>
          <div class="progress-bar-wrap">
            <div class="progress-bar"><div class="progress-fill building" style="width:100%"></div></div>
            <div class="progress-pct" style="color:var(--sprout)">⏳ 生成中</div>
          </div>
        </div>
        <div v-else class="progress-wrap">
          <div class="progress-title">⏳ {{ store.progress.message || '正在准备...' }}</div>
          <div class="analyzing-anim"><span class="spinner"></span> 请稍候</div>
        </div>
      </div>

      <!-- 方案展示 -->
      <div v-else-if="store.currentPlans && !showChat" class="result-section">
        <div style="text-align:center;padding:8px 0;">
          <div style="font-size:18px;font-weight:700;">{{ store.demand }}</div>
          <div style="font-size:13px;color:var(--sub);margin-top:2px;">{{ store.currentPlans.summary }}</div>
        </div>
        <div v-for="(plan, pi) in store.currentPlans.plans" :key="pi" class="plan-card" :class="'plan-' + pi">
          <div class="plan-header">
            <span class="plan-name">{{ plan.name }}</span>
            <span class="plan-total" v-if="plan.total">≈ ¥{{ Number(plan.total).toLocaleString() }}</span>
          </div>
          <div class="plan-desc">{{ plan.desc }}</div>
          <div class="plan-parts">
            <div v-for="(part, ci) in (plan.parts || [])" :key="ci" class="part-row">
              <div class="part-info">
                <span class="part-name">{{ part.name }}</span>
                <span class="part-price" v-if="part.price">¥{{ Number(part.price).toLocaleString() }}</span>
                <span class="part-note" v-else>未搜到价格</span>
              </div>
              <a v-if="part.url" :href="part.url" target="_blank" class="part-link">去购买 ↗</a>
            </div>
          </div>
        </div>
        <button @click="resetShop" class="btn-go" style="margin-top:10px;">🔄 重新搜索</button>
        <button @click="backToChat" class="btn-sm" style="margin-top:6px;width:100%;">💬 返回对话</button>
      </div>

      <!-- 对话（无任务时） -->
      <div v-else class="msg-list" ref="chatScrollRef">
        <div v-if="store.currentPlans" style="text-align:right;padding:4px;">
          <button @click="showChat = false" class="clear-btn">📋 查看方案</button>
          <button @click="clearChat" class="clear-btn" style="margin-left:4px;">清除会话</button>
        </div>
        <div v-else style="text-align:right;padding:4px;">
          <button @click="clearChat" class="clear-btn" v-if="store.messages.length > 1">清除会话</button>
        </div>
        <div v-for="(m, mi) in store.messages" :key="mi" :class="['msg-row', m.role]">
          <div v-if="m.role === 'assistant'" class="msg-orb">🛒</div>
          <div class="msg-bubble" :class="m.role">
            <template v-if="m.role === 'user'">{{ m.content }}</template>
            <template v-else-if="m.confirmCard">
              <div class="glass-card">
                <div class="glass-title">确认需求</div>
                <div class="confirm-field"><span>需求：</span>{{ m.detail.demand }}</div>
                <div class="confirm-field"><span>预算：</span>{{ m.detail.budget || '未指定' }}</div>
                <div class="confirm-field"><span>用途：</span>{{ m.detail.use || '未指定' }}</div>
                <div class="confirm-actions" style="margin-top:8px;">
                  <button v-if="!store.currentPlans" @click="startSearch(m)" :disabled="searching" class="btn-go" style="font-size:14px;padding:10px;">
                    {{ searching ? '⏳ 搜索中...' : '🔍 开始搜索' }}
                  </button>
                  <button v-else class="btn-go" style="font-size:14px;padding:10px;background:var(--sprout);opacity:0.7;" disabled>✅ 已生成方案</button>
                  <button @click="editMsg(mi)" class="btn-sm" style="margin-left:6px;">✎ 修改</button>
                </div>
              </div>
            </template>
            <template v-else>{{ m.content }}</template>
          </div>
          <button v-if="m.role === 'user' && !m.confirmCard" @click="deleteMsg(mi)" class="msg-del" title="删除">×</button>
        </div>
      </div>
      <!-- 搜索进度 -->
      <div class="chat-bottom" v-if="!store.currentPlans && !store.currentTaskId">
        <div class="quickbar">
          <button v-for="q in quickItems" :key="q.label" class="qa" @click="sendQuick(q)">{{ q.label }}</button>
        </div>
        <div class="inputbar">
          <input v-model="chatInput" @keydown.enter="sendChat" placeholder="说你的购物需求…" />
          <button @click="sendChat" :disabled="!chatInput.trim()" class="send-btn">
            <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 历史标签 -->
    <div v-if="activeTab === 'history'" class="history-scroll">
      <div class="section-title">📋 历史方案</div>
      <div v-if="historyList.length === 0" style="text-align:center;padding:40px 20px;color:var(--sub);font-size:14px;">还没有历史方案</div>
      <div v-else>
        <div v-for="h in historyList" :key="h.id" class="history-card" @click="viewHistory(h)">
          <div style="flex:1;min-width:0;">
            <div class="hc-title">{{ h.demand }}</div>
            <div class="hc-meta">{{ timeAgo(h.created_at) }} · {{ h.plans?.plans?.length || 0 }}套方案</div>
          </div>
          <button @click.stop="toggleFav(h)" class="fav-btn" :class="{active:h.favorited==='true'}">{{ h.favorited === 'true' ? '★' : '☆' }}</button>
          <button @click.stop="deleteHistory(h)" class="del-btn">×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useShoppingStore } from '../stores/shopping'
import { apiGenerateShoppingPlan, apiGetShoppingHistory, apiGetShoppingPlan, apiDeleteShoppingPlan, apiFavoriteShoppingPlan } from '../api/index'

const emit = defineEmits(['back'])
const store = useShoppingStore()

const chatInput = ref('')
const chatScrollRef = ref(null)
const activeTab = ref('shop')
const historyList = ref([])
const searching = ref(false)
const showChat = ref(false)

const quickItems = [
  { label: '💻 配电脑', demand: '5000元配一台打游戏的电脑' },
  { label: '📱 手机', demand: '3000元左右拍照好的手机' },
  { label: '🧥 外套', demand: '500元以内男士冬季外套' },
  { label: '🧹 家电', demand: '2000元左右洗衣机' },
]

onMounted(() => { loadHistory() })

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'history') loadHistory()
}

function timeAgo(s) {
  if (!s) return ''
  const d = Date.now() - new Date(s).getTime()
  const m = Math.floor(d / 60000)
  return m < 60 ? m + '分钟前' : Math.floor(m / 60) + '小时前'
}

function sendChat() {
  const text = chatInput.value.trim()
  if (!text) return
  chatInput.value = ''
  store.demand = text
  store.addMessage('user', text)
  let budget = '', use = ''
  const bm = text.match(/(\d+)\s*元/)
  if (bm) budget = bm[1] + '元'
  for (const kw of ['打游戏', '办公', '拍照', '设计', '编程', '学习', '家用']) {
    if (text.includes(kw)) { use = kw; break }
  }
  store.addMessage('assistant', '', { confirmCard: true, detail: { demand: text, budget, use } })
  nextTick(() => { if (chatScrollRef.value) chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight })
}

function sendQuick(q) { chatInput.value = q.demand; sendChat() }

function editMsg(i) {
  const m = store.messages[i]
  if (m?.detail?.demand) {
    chatInput.value = m.detail.demand
    // 删除用户消息 + 确认卡片
    store.messages = store.messages.slice(0, i - 1)
  }
}

function deleteMsg(i) {
  if (!confirm('删除这条消息？')) return
  // 如果是用户消息，连带删除下一条 AI 回复
  const count = store.messages[i]?.role === 'user' && store.messages[i + 1]?.role === 'assistant' ? 2 : 1
  store.messages = store.messages.filter((_, idx) => idx < i || idx >= i + count)
}

async function startSearch(m) {
  if (searching.value) return
  searching.value = true
  store.disconnectSSE()
  store.currentPlans = null
  store.currentTaskId = ''
  store.progress = { status: '', phase: '', parts: [], results: [], current: 0, total: 0, message: '' }
  store.setProgress('waiting', { message: '正在分析需求...' })
  showChat.value = false

  try {
    const data = await apiGenerateShoppingPlan(m.detail.demand)
    store.currentTaskId = data.task_id
    store.connectSSE(data.task_id)
  } catch (e) {
    store.setProgress('error', { message: e.message || '请求失败' })
    searching.value = false
  }
}

watch(() => store.progress.status, (val) => {
  if (val === 'done' || val === 'error') searching.value = false
})

watch(() => store.currentPlans, (val) => {
  if (val) loadHistory()
})

function resetShop() {
  store.reset()
  showChat.value = false
  store.addMessage('assistant', '嗨！告诉我你想买什么，我来帮你搜实时价格、出方案 😊')
}

function backToChat() {
  store.currentTaskId = ''
  store.progress = { status: '', phase: '', parts: [], results: [], current: 0, total: 0, message: '' }
  showChat.value = true
}

function clearChat() {
  if (!confirm('清除所有对话？')) return
  store.clearMessages()
}

async function loadHistory() {
  try { historyList.value = await apiGetShoppingHistory() || [] } catch {}
}

async function viewHistory(h) {
  const data = await apiGetShoppingPlan(h.id)
  if (data) {
    store.currentPlans = data.plans
    store.demand = h.demand
    activeTab.value = 'shop'
  }
}

async function toggleFav(h) {
  try {
    const data = await apiFavoriteShoppingPlan(h.id)
    h.favorited = data.favorited ? 'true' : 'false'
  } catch {}
}

async function deleteHistory(h) {
  if (!confirm('删除此方案？')) return
  try {
    await apiDeleteShoppingPlan(h.id)
    historyList.value = historyList.value.filter(x => x.id !== h.id)
  } catch {}
}
</script>

<style scoped>
.tabs { display: flex; margin: 8px 0 14px; background: var(--line); border-radius: var(--r-md); padding: 3px; }
.tabs .tab { flex: 1; padding: 8px; font-size: 14px; font-weight: 600; border: none; background: none; cursor: pointer; border-radius: var(--r-sm); color: var(--sub); transition: all .25s; z-index: 1; }
.tabs .tab.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 4px rgba(0,0,0,.08); }

/* 购物对话 */
.scroll-chat { display: flex; flex-direction: column; }
.shop-section { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.msg-list { flex: 1; overflow-y: auto; padding: 0 4px; min-height: 0; }
.msg-row { display: flex; gap: 8px; margin-bottom: 12px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }
.msg-orb { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.msg-bubble { max-width: 80%; padding: 10px 14px; border-radius: var(--r-lg); font-size: 14px; line-height: 1.5; }
.msg-bubble.ai { background: var(--honey-soft); color: var(--ink); }
.msg-bubble.user { background: var(--honey-deep); color: #fff; }

.msg-del { background: none; border: none; font-size: 16px; color: var(--sub); cursor: pointer; padding: 4px; opacity: 0; transition: opacity .15s; }
.msg-row:hover .msg-del { opacity: 1; }
.msg-del:hover { color: var(--berry); }

.quickbar { display: flex; gap: 6px; padding: 4px 0; flex-wrap: wrap; }
.qa { font-size: 12px; padding: 5px 10px; border: 1px solid var(--line); border-radius: 100px; background: var(--card); cursor: pointer; white-space: nowrap; }
.qa:hover { border-color: var(--honey); }

.chat-bottom { flex-shrink: 0; padding: 8px 0 0; background: var(--bg); }
.inputbar { display: flex; gap: 8px; }
.inputbar input { flex: 1; padding: 10px 14px; border: 1.5px solid var(--line); border-radius: var(--r-md); font-size: 15px; background: var(--card); outline: none; }
.inputbar input:focus { border-color: var(--honey); }
.send-btn { width: 42px; height: 42px; border: none; border-radius: var(--r-md); background: var(--honey-deep); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.send-btn svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; }
.send-btn:disabled { opacity: .4; }

/* 确认卡片 */
.glass-card { background: rgba(255,255,255,.6); backdrop-filter: blur(12px); border-radius: var(--r-lg); padding: 14px; border: 1px solid rgba(255,255,255,.8); }
.glass-title { font-size: 13px; font-weight: 600; color: var(--ink-soft); margin-bottom: 8px; }
.confirm-field { font-size: 14px; margin-bottom: 4px; }
.confirm-field span { color: var(--sub); margin-right: 6px; }
.confirm-actions { display: flex; gap: 6px; margin-top: 8px; }
.btn-go { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px; border: none; border-radius: var(--r-md); background: var(--honey-deep); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; flex: 1; }
.btn-go:disabled { opacity: .5; cursor: not-allowed; }
.btn-sm { padding: 8px 14px; border: 1px solid var(--line); border-radius: var(--r-sm); font-size: 13px; background: var(--card); cursor: pointer; }

/* 方案展示 */
.result-section { animation: fadeUp .25s ease; padding: 0 4px; }
.plan-card { border: 1px solid var(--line); border-radius: var(--r-lg); padding: 14px; margin-bottom: 12px; }
.plan-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.plan-name { font-size: 15px; font-weight: 700; }
.plan-total { font-size: 16px; font-weight: 700; color: var(--honey-deep); }
.plan-desc { font-size: 13px; color: var(--sub); margin-bottom: 10px; }
.part-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--line); }
.part-row:last-child { border-bottom: none; }
.part-info { display: flex; gap: 6px; align-items: baseline; }
.part-name { font-size: 14px; }
.part-price { font-size: 14px; font-weight: 600; }
.part-note { font-size: 12px; color: var(--sub); }
.part-link { font-size: 12px; color: var(--honey); text-decoration: none; padding: 3px 8px; border: 1px solid var(--honey-soft); border-radius: var(--r-sm); white-space: nowrap; }
.part-link:hover { background: var(--honey-soft); }

/* 进度 */
.progress-wrap { flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:20px; gap:12px; }
.progress-title { font-size:16px; font-weight:600; }
.progress-list { width:100%; max-width:300px; }
.progress-item { display:flex; align-items:center; gap:8px; padding:6px 0; font-size:14px; }
.progress-bar-wrap { width:100%; max-width:300px; display:flex; align-items:center; gap:10px; }
.progress-bar { flex:1; height:8px; background:var(--line); border-radius:4px; overflow:hidden; }
.progress-fill { height:100%; background:linear-gradient(90deg,var(--honey),var(--honey-deep)); border-radius:4px; transition:width .3s; }
.progress-fill.building { background:linear-gradient(90deg,var(--sprout),#5FBE63); }
.progress-pct { font-size:13px; font-weight:600; color:var(--honey-deep); }
.analyzing-anim { display:flex; align-items:center; gap:8px; font-size:14px; color:var(--ink-soft); }
.spinner { display:inline-block; width:18px; height:18px; border:2px solid var(--honey-soft); border-top-color:var(--honey-deep); border-radius:50%; animation:spin .6s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* 历史 */
.history-scroll { animation: fadeUp .25s ease; }
.section-title { font-size: 15px; font-weight: 600; color: var(--sub); margin-bottom: 10px; }
.history-card { display: flex; align-items: center; gap: 8px; padding: 12px; background: var(--card); border-radius: var(--r-lg); margin-bottom: 8px; cursor: pointer; }
.history-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.06); }
.hc-title { font-size: 14px; font-weight: 600; }
.hc-meta { font-size: 12px; color: var(--sub); margin-top: 2px; }
.fav-btn, .del-btn { width: 30px; height: 30px; border: none; border-radius: 50%; background: var(--line); cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.fav-btn.active { color: #e74c3c; background: #fff0f0; }
.del-btn { color: var(--berry); }
.clear-btn { font-size:12px; color:var(--sub); padding:3px 8px; border:1px solid var(--line); border-radius:var(--r-sm); background:var(--card); cursor:pointer; }
.clear-btn:hover { color:var(--berry); border-color:var(--berry-soft); }

@keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.back-bar { display: flex; align-items: center; padding: 4px 4px; }
.back-btn { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--ink-soft); padding: 6px 8px; background: none; border: none; cursor: pointer; }
.back-btn:hover { color: var(--ink); }
</style>
