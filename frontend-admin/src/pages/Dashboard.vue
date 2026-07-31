<template>
  <div>
    <div class="page-title">仪表盘</div>
    <div class="page-sub">今天，陪伴正在进行</div>

    <!-- 指标卡 -->
    <div class="stat-grid">
      <div class="card stat-card gold-border">
        <div class="stat-label">用户总数</div>
        <div class="stat-value num">{{ d.total_users ?? '–' }}</div>
        <div class="stat-hint">今日新增 {{ d.today_new_users ?? 0 }}</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">对话会话</div>
        <div class="stat-value num">{{ d.total_sessions ?? '–' }}</div>
        <div class="stat-hint">累计</div>
      </div>
      <div class="card stat-card moss-border">
        <div class="stat-label">消息总数</div>
        <div class="stat-value num">{{ d.total_messages ?? '–' }}</div>
        <div class="stat-hint">今日 {{ d.today_messages ?? 0 }}</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">累计充值</div>
        <div class="stat-value num">{{ d.total_recharged ?? 0 }}</div>
        <div class="stat-hint">积分</div>
      </div>
      <div class="card stat-card berry-border">
        <div class="stat-label">累计消费</div>
        <div class="stat-value num">{{ d.total_consumed ?? 0 }}</div>
        <div class="stat-hint">积分</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">已兑换积分</div>
        <div class="stat-value num">{{ d.redeemed_amount ?? 0 }}</div>
        <div class="stat-hint">兑换码</div>
      </div>
    </div>

    <!-- 脉搏线：签名元素 -->
    <div class="pulse-wrap">
      <div class="pulse-head">
        <div style="display:flex;align-items:baseline;gap:10px;">
          <span class="pulse-title">对话脉搏</span>
          <span class="pulse-sub">近 {{ range }} 天消息量 · 单位：条</span>
        </div>
        <div class="pulse-range">
          <button v-for="r in ranges" :key="r" :class="['range-btn', range === r ? 'active' : '']" @click="switchRange(r)">{{ r }}天</button>
        </div>
      </div>
      <svg class="pulse-svg" viewBox="0 0 600 90" preserveAspectRatio="none" aria-label="对话趋势">
        <defs>
          <linearGradient id="pulse-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#C99A2E" stop-opacity=".18" />
            <stop offset="100%" stop-color="#C99A2E" stop-opacity="0" />
          </linearGradient>
        </defs>
        <!-- 基线 -->
        <line :x1="pad" y1="78" :x2="600 - pad" y2="78" stroke="#E2DCCB" stroke-width="1" />
        <!-- 面积填充 -->
        <polygon :points="areaPoints" fill="url(#pulse-fill)" />
        <!-- 脉搏折线（金色） -->
        <polyline :points="linePoints" fill="none" stroke="#C99A2E" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
        <!-- 数据点 -->
        <circle v-for="(p, i) in points" :key="i" :cx="p.x" :cy="p.y" r="2.5" fill="#C99A2E" />
      </svg>
      <!-- 日期标签：HTML 渲染，避免 SVG 拉伸变形与被裁切 -->
      <div class="pulse-labels">
        <span v-for="i in labelIndexes" :key="'t' + i">{{ trend[i]?.date }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiDashboard } from '../api'

const d = ref({})
const ranges = [7, 30, 90]
const range = ref(7)

const trend = computed(() => Array.isArray(d.value.trend) ? d.value.trend : [])
const maxV = computed(() => Math.max(1, ...trend.value.map((t) => t.messages || 0)))
// 左右留边距，避免首尾数据点/标签贴边
const pad = 20
const points = computed(() => {
  const arr = trend.value
  if (!arr.length) return []
  const w = 600 - pad * 2, h = 70, top = 8, bottom = 74
  const step = w / Math.max(arr.length - 1, 1)
  return arr.map((t, i) => ({
    x: pad + i * step,
    y: bottom - ((t.messages || 0) / maxV.value) * (bottom - top),
  }))
})
const linePoints = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))
const areaPoints = computed(() => {
  if (!points.value.length) return ''
  const pts = points.value.map((p) => `${p.x},${p.y}`).join(' ')
  return `${pts} ${points.value[points.value.length - 1].x},78 ${pad},78`
})

// 日期标签抽样：最多显示 7 个，均匀取点
const labelIndexes = computed(() => {
  const n = trend.value.length
  if (!n) return []
  const max = 7
  if (n <= max) return trend.value.map((_, i) => i)
  const idxs = [0]
  for (let k = 1; k < max - 1; k++) idxs.push(Math.round((k * (n - 1)) / (max - 1)))
  idxs.push(n - 1)
  return [...new Set(idxs)]
})

async function load() {
  try {
    const res = await apiDashboard(range.value)
    if (res.success) d.value = res.data
  } catch {}
}

function switchRange(r) {
  if (range.value === r) return
  range.value = r
  load()
}

onMounted(load)
</script>
