<template>
  <div :class="['scroll', activeTab === 'chat' ? 'scroll-chat' : '']">
    <div class="back-bar">
      <button @click="$emit('back')" class="back-btn">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="13,4 7,10 13,16"/></svg>
        {{ props.origin === 'chat' ? '返回聊天' : '返回工作台' }}
      </button>
    </div>

    <!-- 标签切换 -->
    <div class="tabs">
      <button :class="['tab', activeTab === 'chat' ? 'active' : '']" @click="activeTab = 'chat'">💬 会话</button>
      <button :class="['tab', activeTab === 'bill' ? 'active' : '']" @click="activeTab = 'bill'">📊 账单</button>
      <div class="tab-slider" :style="{transform: `translateX(${activeTab === 'chat' ? 0 : 100}%)`}"></div>
    </div>

    <!-- 会话标签 -->
    <div v-if="activeTab === 'chat'" class="chat-section">
      <!-- 消息区 -->
      <div class="msg-list" ref="chatScrollRef">
        <div v-for="(m, mi) in messages" :key="m.id" :class="['msg-row', m.role === 'user' ? 'user' : 'ai']">
          <div v-if="m.role === 'assistant'" class="msg-orb">
            <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="var(--honey)" stroke-width="1.5">
              <circle cx="10" cy="10" r="8"/><path d="M6 14c0-2.2 1.8-4 4-4s4 1.8 4 4"/>
            </svg>
          </div>
          <div style="position:relative;max-width:80%;">
            <div :class="['msg-bubble', m.role]">
              <template v-if="m.role === 'user'">
                {{ m.content }}
                <div class="msg-menu-trigger" @click.stop="toggleMsgMenu(mi)">
                  <span class="msg-dots">⋯</span>
                </div>
              </template>
              <template v-else-if="m.parsed">
                <div class="confirm-card">
                  <div style="font-size:13px;font-weight:600;">{{ categoryIcon(m.parsed.category) }} {{ m.parsed.category }}</div>
                  <div :class="['confirm-amount', m.parsed.type]">{{ m.parsed.type === 'income' ? '+' : '-' }}¥{{ (m.parsed.amount / 100).toFixed(2) }}</div>
                  <div v-if="m.parsed.note" class="confirm-note">{{ m.parsed.note }}</div>
                  <div v-if="!m.confirmed" class="confirm-actions">
                    <button @click="confirmRecord(m)" class="btn-sm primary">✓ 确认</button>
                    <button @click="editRecord(m)" class="btn-sm">✎ 修改</button>
                    <button @click="cancelRecord(m)" class="btn-sm cancel">取消</button>
                  </div>
                  <div v-else class="confirmed-badge">✓ 已记账</div>
                </div>
              </template>
              <template v-else>{{ m.content }}</template>
            </div>
            <!-- 菜单遮罩 -->
            <div v-if="openMsgMenu === mi" class="menu-overlay" @click="openMsgMenu = -1"></div>
            <!-- 消息操作菜单 -->
            <div v-if="openMsgMenu === mi" class="msg-menu" @click.stop>
              <button @click="resendMsg(mi)" class="msg-menu-item">重新回答</button>
              <button @click="deleteMsgPair(mi)" class="msg-menu-item" style="color:var(--berry);">删除</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部固定区 -->
      <div class="chat-bottom">
        <div class="quickbar">
          <button v-for="q in quickItems" :key="q.label" class="qa" @click="quickRecord(q)">{{ q.label }}</button>
        </div>
        <div class="inputbar">
          <input v-model="chatInput" @keydown.enter="sendChat" placeholder="说点什么…" />
          <button @click="sendChat" :disabled="!chatInput.trim()" class="send-btn">
            <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 账单标签 -->
    <div v-if="activeTab === 'bill'" class="bill-section">
      <div class="summary-card">
        <div class="balance">{{ summary.balance >= 0 ? '+' : '' }}¥{{ (summary.balance / 100).toFixed(2) }}</div>
        <div class="income-expense">
          <span class="income">收入 ¥{{ (summary.total_income / 100).toFixed(2) }}</span>
          <span class="sep">|</span>
          <span class="expense">支出 ¥{{ (summary.total_expense / 100).toFixed(2) }}</span>
        </div>
      </div>

      <div v-for="(day, di) in groupedRecords" :key="di" class="day-group">
        <div class="day-label">{{ day.date }}</div>
        <div v-for="r in day.records" :key="r.id" class="record-row">
          <div class="record-left">
            <span class="record-cat">{{ categoryIcon(r.category) }} {{ r.category }}</span>
            <span v-if="r.note" class="record-note">{{ r.note }}</span>
          </div>
          <div class="record-right">
            <span :class="r.type === 'income' ? 'income' : 'expense'">{{ r.type === 'income' ? '+' : '-' }}¥{{ (r.amount / 100).toFixed(2) }}</span>
            <button @click="showRecordMenu(r)" class="menu-btn">⋯</button>
          </div>
        </div>
      </div>

      <div class="category-stats">
        <div class="stat-title">分类统计</div>
        <div v-for="c in categoryStats" :key="c.name" class="stat-row">
          <span class="stat-name">{{ categoryIcon(c.name) }} {{ c.name }}</span>
          <div class="stat-bar-wrap">
            <div class="stat-bar" :style="{width: c.pct + '%', background: categoryColor(c.name)}"></div>
          </div>
          <span class="stat-amount">¥{{ (c.amount / 100).toFixed(2) }}</span>
        </div>
      </div>

      <!-- 记一笔按钮 -->
      <button class="fab" @click="showAddPanel = true">💰 记一笔</button>
    </div>

    <!-- 记一笔面板 -->
    <div v-if="showAddPanel" class="panel-overlay" @click="showAddPanel = false">
      <div class="panel" @click.stop>
        <div class="panel-title">💰 记一笔</div>
        <div class="panel-body">
          <div class="amount-input-wrap">
            <span class="currency">¥</span>
            <input v-model="formAmount" type="number" class="amount-input" placeholder="0.00" autofocus />
          </div>
          <div class="type-toggle">
            <button :class="['type-btn', formType === 'expense' ? 'active' : '']" @click="formType = 'expense'">支出</button>
            <button :class="['type-btn', formType === 'income' ? 'active' : '']" @click="formType = 'income'">收入</button>
          </div>
          <div class="category-scroll">
            <button v-for="cat in categories" :key="cat" :class="['cat-btn', formCategory === cat ? 'active' : '']" @click="formCategory = cat">{{ categoryIcon(cat) }} {{ cat }}</button>
          </div>
          <input v-model="formNote" class="form-input" placeholder="备注（可选）" />
          <div class="panel-actions">
            <button @click="saveRecord" class="btn-primary" style="flex:1;">✓ 保存</button>
            <button @click="showAddPanel = false" style="flex:1;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 记录操作菜单 -->
    <div v-if="menuRecord" class="panel-overlay" @click="menuRecord = null">
      <div class="action-sheet" @click.stop>
        <button @click="editRecord(menuRecord);menuRecord=null" class="action-btn">✎ 编辑</button>
        <button @click="deleteRecord(menuRecord);menuRecord=null" class="action-btn danger">✕ 删除</button>
        <button @click="menuRecord = null" class="action-btn cancel">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onActivated } from 'vue'
import { apiCreateRecord, apiGetRecords, apiUpdateRecord, apiDeleteRecord, apiGetSummary, apiAiParse, apiGetFinanceMessages, apiSaveFinanceMessage } from '../api/index'

const emit = defineEmits(['back'])
const props = defineProps({
  origin: { type: String, default: 'home' },
})
const activeTab = ref('chat')
const messages = ref([])
const chatInput = ref('')
const showAddPanel = ref(false)
const formAmount = ref('')
const formType = ref('expense')
const formCategory = ref('餐饮')
const formNote = ref('')
const records = ref([])
const summary = ref({ total_income: 0, total_expense: 0, balance: 0, categories: [] })
const menuRecord = ref(null)
const editingRecord = ref(null)
const chatScrollRef = ref(null)
const openMsgMenu = ref(-1)
const editingMsgIdx = ref(-1)
const editingText = ref('')

const quickItems = [
  { label: '🍜 午饭¥30', category: '餐饮', amount: 3000 },
  { label: '🚕 打车¥15', category: '交通', amount: 1500 },
  { label: '☕ 咖啡¥25', category: '餐饮', amount: 2500 },
  { label: '🛒 超市¥100', category: '购物', amount: 10000 },
  { label: '🏠 房租¥3000', category: '居住', amount: 300000 },
]

const categories = ['餐饮', '交通', '购物', '居住', '娱乐', '其他支出', '薪资', '其他收入']
const categoryIcons = { '餐饮': '🍜', '交通': '🚕', '购物': '🛒', '居住': '🏠', '娱乐': '🎮', '其他支出': '📌', '薪资': '💰', '其他收入': '📦' }
const categoryColors = { '餐饮': '#FF9F45', '交通': '#5FB0E8', '购物': '#E88D8D', '居住': '#9B6FD8', '娱乐': '#FFD0A8', '其他支出': '#A89C88', '薪资': '#5FBE63', '其他收入': '#4CAF50' }

function categoryIcon(name) { return categoryIcons[name] || '📌' }
function categoryColor(name) { return categoryColors[name] || '#A89C88' }

const groupedRecords = computed(() => {
  const groups = {}
  for (const r of records.value) {
    const d = r.record_date
    if (!groups[d]) groups[d] = { date: d, records: [] }
    groups[d].records.push(r)
  }
  return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

const categoryStats = computed(() => {
  const total = summary.value.total_expense + summary.value.total_income
  if (!total) return []
  return (summary.value.categories || []).map(c => ({
    ...c,
    pct: total ? Math.round(c.amount / total * 100) : 0,
  }))
})

onActivated(async () => {
  await loadData()
  await loadMessages()
});

async function loadData() {
  const now = new Date()
  const [recordsRes, summaryRes] = await Promise.all([
    apiGetRecords(now.getFullYear(), now.getMonth() + 1),
    apiGetSummary(now.getFullYear(), now.getMonth() + 1),
  ])
  records.value = recordsRes || []
  summary.value = summaryRes || summary.value
}

async function loadMessages() {
  const msgs = await apiGetFinanceMessages()
  messages.value = (msgs || []).map(m => {
    const msg = { ...m, parsed: null, confirmed: !!m.record_id }
    // 尝试解析 assistant 消息中的 JSON
    if (m.role === 'assistant') {
      try {
        const parsed = JSON.parse(m.content)
        if (parsed && parsed.amount) {
          msg.parsed = parsed
          msg.content = ''
        }
      } catch {}
    }
    return msg
  })
  scrollToBottom()
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text) return
  chatInput.value = ''
  messages.value.push({ id: Date.now().toString(), role: 'user', content: text, parsed: null, confirmed: false })
  await apiSaveFinanceMessage('user', text, null)
  scrollToBottom()

  // AI 解析
  const res = await apiAiParse(text)
  if (res && res.amount) {
    const parsed = { ...res, amount: res.amount }
    messages.value.push({ id: 'ai-' + Date.now(), role: 'assistant', content: '', parsed, confirmed: false })
    scrollToBottom()
  } else {
    messages.value.push({ id: 'ai-' + Date.now(), role: 'assistant', content: '没识别到金额，请重新描述～', parsed: null, confirmed: false })
  }
}

async function confirmRecord(msg) {
  const p = msg.parsed
  const res = await apiCreateRecord({
    type: p.type, category: p.category, amount: p.amount,
    note: p.note, source: 'ai',
  })
  if (res) {
    msg.confirmed = true
    await apiSaveFinanceMessage('assistant', JSON.stringify(p), res.id)
    await loadData()
  }
}

function editRecord(target) {
  if (target.parsed) {
    formType.value = target.parsed.type
    formCategory.value = target.parsed.category
    formAmount.value = (target.parsed.amount / 100).toFixed(2)
    formNote.value = target.parsed.note
    editingRecord.value = null
  } else if (target.id) {
    formType.value = target.type
    formCategory.value = target.category
    formAmount.value = (target.amount / 100).toFixed(2)
    formNote.value = target.note || ''
    editingRecord.value = target
  }
  showAddPanel.value = true
}

function cancelRecord(msg) {
  msg.parsed = null
  messages.value = messages.value.filter(m => m.id !== msg.id)
}

async function deleteMsgPair(idx) {
  const userMsg = messages.value[idx]
  if (!userMsg || userMsg.role !== 'user') return
  const aiMsg = messages.value[idx + 1]
  if (aiMsg?.record_id) {
    try { await apiDeleteRecord(aiMsg.record_id) } catch {}
  }
  messages.value.splice(idx, 2)
  openMsgMenu.value = -1
  await loadData()
}

function toggleMsgMenu(idx) {
  openMsgMenu.value = openMsgMenu.value === idx ? -1 : idx
}

function resendMsg(idx) {
  const userMsg = messages.value[idx]
  if (!userMsg) return
  chatInput.value = userMsg.content
  deleteMsgPair(idx)
}

function quickRecord(q) {
  chatInput.value = `${q.label}`
}

function scrollToBottom() {
  setTimeout(() => {
    if (chatScrollRef.value) chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }, 50)
}

function startEditMsg(m, idx) {
  editingMsgIdx.value = idx
  editingText.value = m.content
}

function confirmEditMsg(idx) {
  if (!editingText.value.trim()) { editingMsgIdx.value = -1; return }
  messages.value[idx].content = editingText.value.trim()
  editingMsgIdx.value = -1
}

function showRecordMenu(r) {
  menuRecord.value = r
}

async function deleteRecord(r) {
  await apiDeleteRecord(r.id)
  await loadData()
}

async function saveRecord() {
  if (!formAmount.value) return
  const amount = Math.round(parseFloat(formAmount.value) * 100)
  const data = { type: formType.value, category: formCategory.value, amount, note: formNote.value, source: 'manual' }
  if (editingRecord.value) {
    await apiUpdateRecord(editingRecord.value.id, data)
    editingRecord.value = null
  } else {
    await apiCreateRecord(data)
  }
  showAddPanel.value = false
  formAmount.value = ''
  formNote.value = ''
  await loadData()
}
</script>

<style scoped>
.back-bar { display: flex; align-items: center; padding: 4px 4px; }
.back-btn { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--ink-soft); padding: 6px 8px; background: none; border: none; cursor: pointer; }
.back-btn:hover { color: var(--ink); }
.tabs { display: flex; position: relative; margin: 8px 0 12px; background: var(--line); border-radius: var(--r-md); padding: 3px; }
.tabs .tab { flex: 1; padding: 8px; font-size: 14px; font-weight: 600; border: none; background: none; cursor: pointer; border-radius: var(--r-sm); color: var(--sub); transition: all .25s ease; z-index: 1; }
.tabs .tab.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.chat-section, .bill-section { animation: tabFadeIn .25s ease; }
@keyframes tabFadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* ── 会话（匹配主聊天样式）── */
.scroll-chat { display: flex; flex-direction: column; }
.scroll-chat .chat-section { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.chat-section .msg-list { flex: 1; overflow-y: auto; padding: 4px 0; min-height: 0; }
.chat-bottom { flex-shrink: 0; }
.msg-row { display: flex; align-items: flex-end; margin-bottom: 10px; gap: 6px; }
.msg-row.user { flex-direction: row-reverse; }
.msg-orb { flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: var(--honey-soft); border-radius: 50%; }
.msg-bubble { max-width: 80%; padding: 10px 14px; font-size: 14px; line-height: 1.5; word-break: break-word; position: relative; }
.msg-bubble.user { background: var(--sprout-soft); border-radius: 14px 14px 4px 14px; color: var(--ink); }
.msg-bubble.assistant { background: var(--honey-soft); border-radius: 14px 14px 14px 4px; }
.msg-actions { position: absolute; top: -24px; right: 0; display: flex; gap: 2px; background: var(--card); border-radius: 8px; padding: 2px 4px; box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10; }
.msg-menu-trigger { display: inline-flex; align-items: center; margin-left: 6px; cursor: pointer; opacity: .35; transition: opacity .15s; vertical-align: middle; }
.msg-menu-trigger:hover { opacity: .8; }
.msg-dots { font-size: 16px; letter-spacing: 1px; line-height: 1; color: var(--sub); }
.menu-overlay { position: fixed; inset: 0; z-index: 15; background: transparent; }
.msg-menu { position: absolute; top: 100%; right: 0; z-index: 20; margin-top: 4px; min-width: 110px; background: var(--card); border: 1px solid var(--line); border-radius: var(--r-sm); box-shadow: 0 4px 12px rgba(0,0,0,.1); padding: 4px 0; }
.msg-menu-item { display: block; width: 100%; text-align: left; padding: 8px 14px; font-size: 13px; color: var(--ink); background: none; border: none; cursor: pointer; }
.msg-menu-item:hover { background: var(--honey-soft); }
.msg-action-btn { font-size: 11px; padding: 2px 6px; border-radius: 4px; color: var(--ink-soft); border: none; background: none; cursor: pointer; }
.edit-input { width: 100%; border: none; outline: none; background: transparent; font-size: 14px; font-family: inherit; }

/* 快捷栏 */
.quickbar { display: flex; gap: 6px; overflow-x: auto; padding: 6px 0; margin: 0 -4px; }
.qa { white-space: nowrap; padding: 5px 12px; border-radius: 100px; border: 1.5px solid var(--line); font-size: 12px; background: var(--card); cursor: pointer; transition: all .15s; }
.qa:active { background: var(--honey-soft); transform: scale(.96); }

/* 输入框 */
.inputbar { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--line); }
.inputbar input { flex: 1; padding: 10px 14px; border: none; border-radius: 100px; background: var(--cream); font-size: 14px; outline: none; }
.inputbar .send-btn { width: 38px; height: 38px; border-radius: 50%; background: var(--honey); border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; transition: all .15s; }
.inputbar .send-btn:disabled { opacity: .3; }
.inputbar .send-btn svg { width: 18px; height: 18px; stroke: #fff; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.inputbar .send-btn:active { transform: scale(.9); }

/* 确认卡片 */
.confirm-card { min-width: 200px; }
.confirm-category { font-size: 13px; font-weight: 600; }
.confirm-amount { font-size: 22px; font-weight: 700; margin: 4px 0; }
.confirm-amount.income { color: var(--sprout); }
.confirm-amount.expense { color: var(--berry); }
.confirm-note { font-size: 12px; color: var(--sub); margin-bottom: 8px; }
.confirm-actions { display: flex; gap: 6px; }
.btn-sm { padding: 4px 12px; font-size: 12px; border-radius: var(--r-sm); border: 1px solid var(--line); background: var(--card); cursor: pointer; }
.btn-sm.primary { background: var(--sprout); color: #fff; border-color: var(--sprout); }
.btn-sm.cancel { color: var(--sub); }
.confirmed-badge { font-size: 12px; color: var(--sprout); font-weight: 600; }

/* 账单 */
.bill-section { padding-bottom: 80px; }
.summary-card {
  text-align: center; padding: 20px; margin-bottom: 12px;
  background: rgba(255,255,255,.6); backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: var(--r-lg); box-shadow: 0 2px 12px rgba(0,0,0,.04);
  border: 1px solid rgba(255,255,255,.8);
}
.balance { font-size: 32px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--ink); }
.income-expense { font-size: 13px; color: var(--sub); margin-top: 6px; }
.income-expense .income { color: var(--sprout); }
.income-expense .expense { color: var(--berry); }
.income-expense .sep { margin: 0 8px; color: var(--line); }
.day-group { margin-bottom: 12px; }
.day-label { font-size: 12px; font-weight: 600; color: var(--sub); margin-bottom: 4px; padding: 0 4px; }
.record-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; background: var(--card); border-radius: var(--r-md);
  margin-top: 4px; transition: all .2s ease;
  animation: recordFadeIn .35s ease;
}
.record-row:hover { background: var(--honey-soft); }
@keyframes recordFadeIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
.record-left { display: flex; flex-direction: column; gap: 2px; }
.record-cat { font-size: 14px; font-weight: 500; }
.record-note { font-size: 11px; color: var(--sub); }
.record-right { display: flex; align-items: center; gap: 8px; }
.record-right .income { color: var(--sprout); font-weight: 600; font-size: 15px; font-variant-numeric: tabular-nums; }
.record-right .expense { color: var(--berry); font-weight: 600; font-size: 15px; font-variant-numeric: tabular-nums; }
.menu-btn { font-size: 18px; color: var(--sub); padding: 2px 4px; background: none; border: none; cursor: pointer; }

/* 分类统计 */
.category-stats { margin-top: 16px; padding: 14px; background: var(--card); border-radius: var(--r-lg); }
.stat-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.stat-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.stat-name { font-size: 12px; width: 64px; flex-shrink: 0; }
.stat-bar-wrap { flex: 1; height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }
.stat-bar { height: 100%; border-radius: 4px; transition: width .3s; }
.stat-amount { font-size: 12px; font-weight: 600; width: 80px; text-align: right; font-variant-numeric: tabular-nums; }

/* 浮动按钮 */
.fab { position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); padding: 12px 28px; background: var(--honey); color: #fff; border: none; border-radius: 100px; font-size: 15px; font-weight: 600; cursor: pointer; box-shadow: 0 4px 16px rgba(255,159,69,.3); z-index: 10; transition: all .2s ease; animation: fabIn .5s cubic-bezier(.34,1.56,.64,1); }
.fab:active { transform: translateX(-50%) scale(.93); }
@keyframes fabIn { from { transform: translateX(-50%) scale(0) translateY(20px); opacity: 0; } to { transform: translateX(-50%) scale(1) translateY(0); opacity: 1; } }

/* 面板 */
.panel-overlay { position: fixed; inset: 0; z-index: 50; background: rgba(0,0,0,.3); display: flex; align-items: flex-end; justify-content: center; }
.panel { width: 100%; max-width: 480px; background: var(--card); border-radius: var(--r-lg) var(--r-lg) 0 0; padding: 20px; animation: panelSlide .4s cubic-bezier(.34,1.56,.64,1); }
@keyframes panelSlide { from { transform: translateY(100%); opacity: .5; } to { transform: translateY(0); opacity: 1; } }
@keyframes actionSheetSlide { from { transform: translateY(60%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.panel-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; }
.amount-input-wrap { display: flex; align-items: center; gap: 4px; margin-bottom: 12px; }
.currency { font-size: 24px; font-weight: 700; color: var(--ink); }
.amount-input { flex: 1; font-size: 32px; font-weight: 700; border: none; outline: none; background: none; font-variant-numeric: tabular-nums; width: 100%; }
.type-toggle { display: flex; gap: 8px; margin-bottom: 12px; }
.type-btn { flex: 1; padding: 8px; border-radius: var(--r-sm); border: 1.5px solid var(--line); font-size: 14px; cursor: pointer; background: none; }
.type-btn.active { border-color: var(--honey); background: var(--honey-soft); color: var(--honey-deep); }
.category-scroll { display: flex; gap: 6px; overflow-x: auto; margin-bottom: 12px; padding-bottom: 4px; }
.cat-btn { white-space: nowrap; padding: 6px 14px; border-radius: 100px; border: 1.5px solid var(--line); font-size: 13px; cursor: pointer; background: none; }
.cat-btn.active { border-color: var(--honey); background: var(--honey-soft); color: var(--honey-deep); }
.panel-actions { display: flex; gap: 10px; margin-top: 12px; }

/* 操作菜单 */
.action-sheet { width: 100%; max-width: 480px; background: var(--card); border-radius: var(--r-lg) var(--r-lg) 0 0; padding: 12px 20px 24px; animation: actionSheetSlide .35s cubic-bezier(.34,1.56,.64,1); }
.action-btn { width: 100%; padding: 12px; font-size: 15px; border: none; background: none; cursor: pointer; border-bottom: 1px solid var(--line); }
.action-btn:last-child { border-bottom: none; }
.action-btn.danger { color: var(--berry); }
.action-btn.cancel { color: var(--sub); text-align: center; margin-top: 4px; }
</style>
