<template>
  <div class="scroll">
    <div class="back-bar">
      <button @click="$emit('back')" class="back-btn">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="13,4 7,10 13,16"/></svg>
        返回工作台
      </button>
    </div>

    <div class="tabs">
      <button :class="['tab', activeTab === 'plan' ? 'active' : '']" @click="activeTab = 'plan'">📝 规划</button>
      <button :class="['tab', activeTab === 'history' ? 'active' : '']" @click="activeTab = 'history'">📋 历史</button>
    </div>

    <!-- 规划标签 -->
    <div v-if="activeTab === 'plan'">
      <!-- 表单 -->
      <div v-if="!currentPlan" class="form-section">
        <div style="text-align:center;padding:8px 0 16px;">
          <div style="font-size:22px;font-weight:700;">规划你的旅程</div>
          <div style="font-size:13px;color:var(--sub);margin-top:2px;">告诉我你想去哪，AI 为你定制行程</div>
        </div>

        <div class="glass-card">
          <div class="glass-title">📍 目的地</div>
          <input v-model="form.destination" placeholder="例：北京、东京、巴黎…" class="glass-input" :class="{ 'input-error': errors.destination }" />
          <div v-if="errors.destination" class="field-err">{{ errors.destination }}</div>
        </div>

        <div class="glass-card">
          <div class="glass-title">📅 时间</div>
          <div style="display:flex;gap:10px;">
            <div style="flex:1;">
              <div class="glass-label">出发日期</div>
              <input v-model="form.startDate" type="date" class="glass-input" />
            </div>
            <div style="width:80px;">
              <div class="glass-label">天数</div>
              <input v-model.number="form.days" type="number" min="1" max="30" class="glass-input" />
            </div>
          </div>
        </div>

        <div class="glass-card">
          <div class="glass-title">💰 预算</div>
          <div style="display:flex;gap:10px;align-items:center;">
            <span style="font-size:18px;font-weight:700;color:var(--honey-deep);">¥</span>
            <input v-model.number="form.budget" type="number" placeholder="5000" class="glass-input" style="flex:1;" />
          </div>
        </div>

        <div class="glass-card">
          <div class="glass-title">👥 人数</div>
          <div style="display:flex;gap:10px;">
            <div style="flex:1;">
              <div class="glass-label">成人</div>
              <input v-model.number="form.adults" type="number" min="1" class="glass-input" />
            </div>
            <div style="flex:1;">
              <div class="glass-label">儿童</div>
              <input v-model.number="form.children" type="number" min="0" class="glass-input" />
            </div>
          </div>
        </div>

        <div class="glass-card">
          <div class="glass-title">🏷️ 偏好</div>
          <div class="pref-tags">
            <button v-for="p in preferences" :key="p" :class="['pref-tag', form.prefs.includes(p) ? 'active' : '']" @click="togglePref(p)">{{ p }}</button>
          </div>
        </div>

        <div class="glass-card">
          <div class="glass-title">📝 备注</div>
          <textarea v-model="form.note" rows="2" placeholder="其他要求或想法…" class="glass-input" style="resize:none;"></textarea>
        </div>

        <button @click="generatePlan" :disabled="generating" class="btn-go">
          <span>{{ generating ? 'AI 思考中…' : 'AI 生成行程' }}</span>
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 10h10M12 5l5 5-5 5"/></svg>
        </button>

        <!-- 阶段进度条 -->
        <div v-if="progressVisible" class="progress-wrap" style="margin-top:12px;">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--sub);margin-bottom:4px;">
            <span><span class="spinner"></span> {{ progressLabel }}</span>
            <span>{{ Math.round(progressPct) }}%</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" :class="{'progress-pulse': progressPct < 100}" :style="{width: progressPct + '%'}"></div></div>
          <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;">
            <span v-for="(ph, i) in progressPhases" :key="i" :style="{fontSize:'11px',color: i <= progressPhase ? 'var(--honey-deep)' : 'var(--sub)',opacity: i <= progressPhase ? 1 : .5}">
              {{ i > 0 ? ' · ' : '' }}{{ i <= progressPhase ? '✓' : '○' }} {{ ph }}
            </span>
          </div>
        </div>

        <!-- Toast 提示 -->
        <div v-if="toast" class="toast">{{ toast }}</div>

        <div v-if="genError" style="text-align:center;font-size:13px;color:var(--berry);margin-top:8px;">{{ genError }}</div>
      </div>

      <!-- 行程展示 -->
      <div v-else class="itinerary">
        <div class="itinerary-top">
          <button @click="currentPlan = null" class="back-link">← 重新填写</button>
          <div style="display:flex;gap:6px;">
            <button @click="toggleSave" class="icon-btn" :style="{color: currentPlan.saved ? '#e74c3c' : 'var(--sub)'}">{{ currentPlan.saved ? '♥' : '♡' }} <span style="font-size:12px;">{{ currentPlan.saved ? '已收藏' : '收藏' }}</span></button>
            <button @click="exportPlan" class="icon-btn">📄 <span style="font-size:12px;">导出</span></button>
          </div>
        </div>

        <div class="plan-hero">
          <div class="plan-badge">{{ currentPlan.destination }}</div>
          <div class="plan-title">{{ currentPlan.title || (currentPlan.destination || '') + '行程' }}</div>
          <div v-if="currentPlan.days" class="plan-stats">
            <span>📅 {{ planDays(currentPlan) }}天</span>
            <span class="dot">·</span>
            <span>💰 ¥{{ (currentPlan.budget / 100).toFixed(0) }}</span>
            <span class="dot">·</span>
            <span>👤 {{ currentPlan.adults + (currentPlan.children || 0) }}人</span>
          </div>
        </div>

        <div v-if="currentPlan.budget_detail && Object.keys(currentPlan.budget_detail).length" class="budget-row">
          <span v-for="(v, k) in currentPlan.budget_detail" :key="k" class="budget-chip">{{ budgetLabels[k] || k }} ¥{{ v }}</span>
        </div>

        <div v-for="day in currentPlan.days" :key="day.day_number" class="day-card">
          <div class="day-head">
            <div>
              <span class="day-num">DAY {{ day.day_number }}</span>
              <span class="day-date">{{ day.date }}</span>
            </div>
            <button @click="regenerateDay(day.day_number)" class="day-edit" title="修改这天">↻</button>
          </div>
          <div class="day-body">
            <div v-for="seg in day.segments" :key="seg.period" class="seg-item">
              <div class="seg-time">{{ periodLabel(seg.period) }}</div>
              <div class="seg-content">
                <div class="seg-title">{{ seg.title }}</div>
                <div class="seg-desc">{{ seg.description }}</div>
                <div class="seg-footer">
                  <span v-if="seg.cost">💰 ¥{{ seg.cost }}</span>
                  <span v-if="seg.duration">⏱ {{ seg.duration }}</span>
                </div>
                <div v-if="seg.tips" class="seg-tip">💡 {{ seg.tips }}</div>
              </div>
            </div>
          </div>
          <div class="day-total">本日合计 <strong>¥{{ day.total_cost || 0 }}</strong></div>
        </div>
      </div>
    </div>

    <!-- 历史标签 -->
    <div v-if="activeTab === 'history'" class="history-wrap">
      <div v-if="history.length === 0" class="empty-state">
        <div class="empty-icon">🗺</div>
        <div style="font-size:14px;color:var(--sub);">还没有行程记录</div>
        <div style="font-size:12px;color:var(--sub);margin-top:4px;">去规划你的第一次旅行吧</div>
      </div>

      <template v-else>
        <!-- 收藏的方案 -->
        <div v-if="savedPlans.length > 0">
          <div class="history-section-title">📌 收藏的方案</div>
          <div v-for="p in savedPlans" :key="p.id" class="history-card" @click="viewPlan(p)">
            <div style="display:flex;align-items:center;gap:10px;flex:1;">
              <div class="hc-icon">
                <svg viewBox="0 0 32 32" width="22" height="22" fill="none" stroke="var(--honey-deep)" stroke-width="1.5"><circle cx="16" cy="16" r="10"/><path d="M16 6c3 3.3 3 10.7 3 14M16 6c-3 3.3-3 10.7-3 14"/><line x1="6" y1="16" x2="26" y2="16"/></svg>
              </div>
              <div style="flex:1;">
                <div style="font-weight:600;font-size:14px;">{{ p.title || p.destination || '未命名' }}</div>
                <div style="font-size:12px;color:var(--sub);">{{ p.destination || '' }} · ¥{{ p.budget ? (p.budget/100).toFixed(0) : '-' }} · {{ timeAgo(p.updated_at) }}</div>
              </div>
            </div>
            <button @click.stop="deletePlan(p.id)" style="font-size:14px;color:var(--berry);padding:4px 8px;border:none;background:none;cursor:pointer;opacity:.5;">✕</button>
          </div>
        </div>

        <!-- 历史记录 -->
        <div v-if="regularPlans.length > 0" style="margin-top:16px;">
          <div class="history-section-title">🕐 历史记录</div>
          <div v-for="p in regularPlans" :key="p.id" class="history-card" @click="viewPlan(p)">
            <div style="display:flex;align-items:center;gap:10px;flex:1;">
              <div class="hc-icon">
                <svg viewBox="0 0 32 32" width="22" height="22" fill="none" stroke="var(--ink-soft)" stroke-width="1.5"><circle cx="16" cy="16" r="10"/><polyline points="16,8 16,16 22,20"/></svg>
              </div>
              <div style="flex:1;">
                <div style="font-weight:600;font-size:14px;">{{ p.title || p.destination || '未命名' }}</div>
                <div style="font-size:12px;color:var(--sub);">{{ p.destination || '' }} · {{ planDays(p) }}天 · ¥{{ p.budget ? (p.budget/100).toFixed(0) : '-' }}</div>
              </div>
            </div>
            <button @click.stop="deletePlan(p.id)" style="font-size:14px;color:var(--berry);padding:4px 8px;border:none;background:none;cursor:pointer;opacity:.5;">✕</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { apiGenerateTravelPlan, apiGetTravelPlans, apiGetTravelPlan, apiUpdateTravelPlan, apiDeleteTravelPlan, apiRegenerateTravelDay } from '../api/index'

const emit = defineEmits(['back'])
const activeTab = ref('plan')
const currentPlan = ref(null)
const generating = ref(false)
const genError = ref('')
const history = ref([])

const savedPlans = computed(() => history.value.filter(p => p.saved))
const regularPlans = computed(() => history.value.filter(p => !p.saved))

const preferences = ['自然风光', '美食', '文化', '购物', '休闲', '冒险', '亲子', '摄影']
const budgetLabels = { accommodation: '住宿', food: '餐饮', tickets: '门票', transport: '交通', other: '其他' }

const form = reactive({
  destination: '',
  startDate: new Date().toISOString().split('T')[0],
  days: 3,
  budget: 5000,
  adults: 1,
  children: 0,
  prefs: [],
  note: '',
})
const errors = reactive({ destination: '' })
const toast = ref('')
const progressVisible = ref(false)
const progressPct = ref(0)
const progressPhase = ref(0)
const progressPhases = ref([])
const progressLabel = ref('')
let progressTimer = null

function showProgress(phases) {
  progressPhases.value = phases
  progressPhase.value = 0
  progressPct.value = 5
  progressVisible.value = true
  progressLabel.value = phases[0] || ''
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    const end = ((progressPhase.value + 1) / phases.length) * 90
    if (progressPct.value < end - 3) progressPct.value = Math.min(progressPct.value + 1, end - 3)
  }, 300)
}

function advanceProgress() {
  if (progressPhase.value < progressPhases.value.length - 1) {
    progressPhase.value++
    progressLabel.value = progressPhases.value[progressPhase.value] || ''
    const pct = ((progressPhase.value + 1) / progressPhases.value.length) * 90
    progressPct.value = Math.max(progressPct.value, pct - 5)
  }
}

function doneProgress() {
  progressPct.value = 100
  progressPhase.value = progressPhases.value.length - 1
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function hideProgress() {
  progressVisible.value = false
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => toast.value = '', 2500)
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return mins + '分钟前'
  const hours = Math.floor(mins / 60)
  if (hours < 24) return hours + '小时前'
  const days = Math.floor(hours / 24)
  if (days < 30) return days + '天前'
  return Math.floor(days / 30) + '个月前'
}

function togglePref(p) {
  const idx = form.prefs.indexOf(p)
  if (idx >= 0) form.prefs.splice(idx, 1)
  else form.prefs.push(p)
}

function periodLabel(p) {
  return { morning: '☀️ 上午', afternoon: '⛅ 下午', evening: '🌙 晚上' }[p] || p
}

function planDays(p) {
  // days 可能是数字或数组
  if (Array.isArray(p.days)) return p.days.length
  return p.days || 0
}

onMounted(loadHistory)

async function loadHistory() {
  try {
    const data = await apiGetTravelPlans()
    history.value = data || []
  } catch {}
}

async function generatePlan() {
  // 校验
  errors.destination = ''
  if (!form.destination.trim()) {
    errors.destination = '请填写目的地'
    showToast('请填写目的地')
    return
  }
  generating.value = true
  genError.value = ''
  // 等待 DOM 更新后再显示进度条
  await nextTick()
  showProgress(['分析需求', '生成行程', '整理数据', '完成'])
  try {
    setTimeout(() => advanceProgress(), 600)
    const res = await apiGenerateTravelPlan({
      destination: form.destination,
      start_date: form.startDate,
      days: form.days,
      budget: Math.round(form.budget * 100),
      adults: form.adults,
      children: form.children,
      preferences: form.prefs,
      note: form.note,
    })
    const ok = res && res.days
    // 不管成功还是失败，都走完进度条再显示结果
    const phases = progressPhases.value.length
    let phase = progressPhase.value
    const animateToEnd = () => {
      if (phase < phases - 1) {
        phase++
        advanceProgress()
        setTimeout(animateToEnd, 350)
      } else {
        doneProgress()
        setTimeout(() => {
          hideProgress()
          if (ok) {
            currentPlan.value = res
            loadHistory()
          } else {
            genError.value = res?.message || '生成失败，请重试'
          }
          generating.value = false
        }, 500)
      }
    }
    animateToEnd()
  } catch (e) {
    // 网络异常也走完进度
    const phases = progressPhases.value.length
    let phase = progressPhase.value
    const animateToEnd = () => {
      if (phase < phases - 1) {
        phase++
        advanceProgress()
        setTimeout(animateToEnd, 350)
      } else {
        doneProgress()
        setTimeout(() => {
          hideProgress()
          genError.value = e.message || '网络错误'
          generating.value = false
        }, 500)
      }
    }
    animateToEnd()
  }
}

async function viewPlan(p) {
  // 直接用历史列表的数据，不用再请求 API
  currentPlan.value = p
  activeTab.value = 'plan'
}

async function toggleSave() {
  if (!currentPlan.value) return
  const res = await apiUpdateTravelPlan(currentPlan.value.id, { saved: !currentPlan.value.saved })
  if (res) currentPlan.value.saved = res.saved
}

async function deletePlan(id) {
  await apiDeleteTravelPlan(id)
  history.value = history.value.filter(p => p.id !== id)
}

async function regenerateDay(dayNumber) {
  if (!currentPlan.value) return
  const res = await apiRegenerateTravelDay(currentPlan.value.id, dayNumber)
  if (res) {
    const idx = currentPlan.value.days.findIndex(d => d.day_number === dayNumber)
    if (idx >= 0) currentPlan.value.days[idx] = res
  }
}

function exportPlan() {
  if (!currentPlan.value) return
  const p = currentPlan.value
  let text = `📋 ${p.title || p.destination}\n${p.destination} · ${p.days}天 · 预算¥${(p.budget/100).toFixed(2)}\n\n`
  for (const day of p.days || []) {
    text += `── 第${day.day_number}天 ${day.date} ──\n`
    for (const seg of day.segments || []) {
      text += `  ${periodLabel(seg.period)}: ${seg.title}${seg.cost ? ' (¥'+seg.cost+')' : ''}\n`
    }
    text += `  本日合计: ¥${day.total_cost || 0}\n\n`
  }
  if (p.budget_detail) {
    text += '💰 预算明细:\n'
    for (const [k, v] of Object.entries(p.budget_detail)) text += `  ${budgetLabels[k]||k}: ¥${v}\n`
  }
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${p.destination}行程.txt`
  a.click()
}
</script>

<style scoped>
/* ── 标签 ── */
.tabs { display: flex; margin: 8px 0 14px; background: var(--line); border-radius: var(--r-md); padding: 3px; }
.tabs .tab { flex: 1; padding: 8px; font-size: 14px; font-weight: 600; border: none; background: none; cursor: pointer; border-radius: var(--r-sm); color: var(--sub); transition: all .25s; z-index: 1; }
.tabs .tab.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 4px rgba(0,0,0,.08); }

/* ── 表单 ── */
.form-section { animation: fadeUp .35s ease; }
.glass-card { background: rgba(255,255,255,.6); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-radius: var(--r-lg); padding: 14px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,.8); }
.glass-title { font-size: 13px; font-weight: 600; color: var(--ink-soft); margin-bottom: 6px; }
.glass-label { font-size: 11px; color: var(--sub); margin-bottom: 2px; }
.glass-input { width: 100%; padding: 10px 12px; border: 1.5px solid var(--line); border-radius: var(--r-md); font-size: 15px; background: var(--card); outline: none; transition: border-color .2s; box-sizing: border-box; font-family: inherit; }
.glass-input:focus { border-color: var(--honey); }
.glass-input.input-error { border-color: var(--berry); }
.field-err { font-size: 11px; color: var(--berry); margin-top: 4px; }
.pref-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.pref-tag { padding: 5px 14px; border-radius: 100px; border: 1.5px solid var(--line); font-size: 13px; background: var(--card); cursor: pointer; transition: all .15s; }
.pref-tag.active { border-color: #5FBE63; background: #F0FAF4; color: #3A8F4A; font-weight: 500; }
.btn-go { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 14px; border: none; border-radius: var(--r-md); background: var(--honey-deep); color: #fff; font-size: 16px; font-weight: 600; cursor: pointer; transition: all .2s; box-shadow: 0 4px 14px rgba(200,130,60,.25); margin-top: 4px; }
.btn-go:active { transform: scale(.97); }
.btn-go:disabled { opacity: .5; }
.progress-wrap { padding: 10px 12px; background: var(--honey-soft); border-radius: var(--r-md); }
.progress-bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--honey), var(--honey-deep)); border-radius: 3px; transition: width .3s ease; }
.progress-pulse {
  position: relative;
  overflow: hidden;
}
.progress-pulse::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,.4) 50%, transparent 100%);
  animation: shimmer 1.2s ease-in-out infinite;
}
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--honey-deep);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin .6s linear infinite;
  vertical-align: middle;
  margin-right: 4px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.toast { position: fixed; top: 60px; left: 50%; transform: translateX(-50%); background: var(--ink); color: #fff; padding: 8px 20px; border-radius: 100px; font-size: 13px; z-index: 100; animation: toastIn .25s ease; box-shadow: 0 4px 12px rgba(0,0,0,.15); }
@keyframes toastIn { from { opacity: 0; transform: translateX(-50%) translateY(-8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }

/* ── 行程展示 ── */
.itinerary { animation: fadeUp .35s ease; }
.itinerary-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.back-link { font-size: 13px; color: var(--honey); background: none; border: none; cursor: pointer; padding: 4px 0; }
.icon-btn { font-size: 18px; padding: 4px 8px; border: none; background: none; cursor: pointer; border-radius: var(--r-sm); }
.icon-btn:hover { background: var(--honey-soft); }
.plan-hero { text-align: center; padding: 16px 0; }
.plan-badge { display: inline-block; padding: 3px 12px; border-radius: 100px; background: var(--honey-soft); color: var(--honey-deep); font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.plan-title { font-size: 20px; font-weight: 700; }
.plan-stats { font-size: 13px; color: var(--sub); margin-top: 4px; display: flex; justify-content: center; gap: 4px; }
.dot { color: var(--line); }
.budget-row { display: flex; flex-wrap: wrap; gap: 4px 8px; justify-content: center; padding: 10px; background: var(--honey-soft); border-radius: var(--r-md); margin-bottom: 14px; font-size: 12px; animation: fadeUp .3s ease; }
.budget-chip { background: var(--card); padding: 3px 10px; border-radius: 100px; }

/* ── 日程卡片 ── */
.day-card { border: 1px solid var(--line); border-radius: var(--r-lg); overflow: hidden; margin-bottom: 12px; animation: cardSlide .4s cubic-bezier(.34,1.56,.64,1); }
@keyframes cardSlide { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.day-head { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--honey-soft); }
.day-num { font-weight: 700; font-size: 14px; letter-spacing: 1px; }
.day-date { font-size: 12px; color: var(--sub); margin-left: 8px; }
.day-edit { font-size: 18px; padding: 4px; border: none; background: none; cursor: pointer; color: var(--ink-soft); border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; }
.day-edit:hover { background: rgba(0,0,0,.05); }
.day-body { padding: 10px 14px; }
.seg-item { display: flex; gap: 10px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.seg-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.seg-time { width: 52px; font-size: 11px; font-weight: 600; color: var(--honey-deep); flex-shrink: 0; padding-top: 2px; }
.seg-content { flex: 1; }
.seg-title { font-size: 14px; font-weight: 600; }
.seg-desc { font-size: 12px; color: var(--sub); margin-top: 2px; line-height: 1.5; }
.seg-footer { display: flex; gap: 12px; font-size: 11px; color: var(--ink-soft); margin-top: 4px; }
.seg-tip { font-size: 11px; color: var(--honey); margin-top: 3px; padding: 4px 8px; background: var(--honey-soft); border-radius: var(--r-sm); display: inline-block; }
.day-total { text-align: right; padding: 10px 14px; border-top: 1px solid var(--line); font-size: 13px; color: var(--sub); }
.day-total strong { color: var(--ink); font-size: 15px; }

/* ── 历史 ── */
.history-wrap { animation: fadeUp .35s ease; }
.history-section-title { font-size: 14px; font-weight: 600; color: var(--sub); margin-bottom: 6px; padding: 0 4px; }
.empty-state { text-align: center; padding: 40px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 8px; }
.history-card { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--card); border-radius: var(--r-lg); margin-bottom: 8px; cursor: pointer; transition: all .15s; box-shadow: 0 1px 4px rgba(0,0,0,.03); }
.history-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.06); }
.hc-icon { width: 40px; height: 40px; background: var(--honey-soft); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }

@keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.back-bar { display: flex; align-items: center; padding: 4px 4px; }
.back-btn { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--ink-soft); padding: 6px 8px; background: none; border: none; cursor: pointer; }
.back-btn:hover { color: var(--ink); }
</style>
