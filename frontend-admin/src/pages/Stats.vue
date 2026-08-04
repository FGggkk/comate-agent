<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:flex-end;">
      <div>
        <div class="page-title">数据统计</div>
        <div class="page-sub">工具使用、消费与增长趋势</div>
      </div>
      <div class="pulse-range">
        <button v-for="r in ranges" :key="r" :class="['range-btn', range === r ? 'active' : '']" @click="switchRange(r)">{{ r }}天</button>
      </div>
    </div>

    <!-- 工具使用排行 -->
    <div class="card" style="margin-top:18px;">
      <div style="font-weight:600;font-size:14px;margin-bottom:14px;">工具使用量</div>
      <div v-for="t in toolUsage" :key="t.key" style="display:flex;align-items:center;gap:12px;padding:7px 0;">
        <span style="width:70px;font-size:13px;color:var(--ink-soft);">{{ t.name }}</span>
        <div style="flex:1;height:22px;background:var(--bg);border-radius:4px;overflow:hidden;">
          <div class="bar-fill" :style="{ width: barWidth(t.count) + '%', background: toolColor(t.key) }"></div>
        </div>
        <span class="num" style="width:40px;text-align:right;font-weight:600;">{{ t.count }}</span>
      </div>
      <div v-if="!toolUsage.length" style="font-size:13px;color:var(--ink-soft);padding:20px;text-align:center;">暂无数据</div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px;">
      <!-- 消费分布 -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;">积分消费分布</div>
        <div ref="consumeRef" style="height:220px;"></div>
      </div>
      <!-- 兑换趋势 -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;">兑换趋势（积分）</div>
        <div ref="redeemRef" style="height:220px;"></div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px;">
      <!-- 对话趋势 -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;">对话量趋势</div>
        <div ref="chatRef" style="height:220px;"></div>
      </div>
      <!-- 用户增长 -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;">新增用户</div>
        <div ref="userRef" style="height:220px;"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiAdminStats } from '../api'

const ranges = [7, 30, 90]
const range = ref(30)
const toolUsage = ref([])

const consumeRef = ref(null)
const redeemRef = ref(null)
const chatRef = ref(null)
const userRef = ref(null)

const charts = []

const toolColor = (key) => ({
  interview: '#FF9F45', travel: '#5FBE63', shopping: '#E88D8D', finance: '#9B6FD8',
}[key] || '#C99A2E')

const maxCount = ref(1)
const barWidth = (c) => Math.max(2, Math.round((c / maxCount.value) * 100))

const toolNames = { interview: '面试训练', travel: '旅游规划', shopping: '购物计划', finance: '记账', chat: '对话', finance_parse: '记账解析', redemption_code: '兑换', admin_adjust: '管理员' }

function renderChart(el, option) {
  if (!el) return
  const chart = echarts.init(el)
  chart.setOption(option)
  charts.push(chart)
}

async function load() {
  const res = await apiAdminStats(range.value)
  if (!res.success) return
  const d = res.data
  toolUsage.value = d.tool_usage
  maxCount.value = Math.max(1, ...d.tool_usage.map((t) => t.count))

  // 销毁旧图表
  charts.forEach((c) => c.dispose())
  charts.length = 0
  await nextTick()

  // 消费分布（饼图）
  const dist = d.consume_distribution
  renderChart(consumeRef.value, {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { fontSize: 11, color: '#5C6B64' } },
    color: ['#C99A2E', '#5F7F66', '#B5564F', '#FF9F45', '#9B6FD8', '#5FBE63'],
    series: [{
      type: 'pie', radius: ['45%', '70%'],
      center: ['50%', '45%'],
      label: { show: false },
      data: dist.map((i) => ({ name: toolNames[i.key] || i.key, value: i.amount })),
      emptyCircleStyle: { color: '#F3F2EC' },
    }],
  })

  // 兑换趋势（折线）
  renderChart(redeemRef.value, lineOption(d.redemption_trend, 'amount', '#C99A2E', '兑换积分'))

  // 对话趋势（折线）
  renderChart(chatRef.value, lineOption(d.chat_trend, 'count', '#5FBE63', '消息数'))

  // 用户增长（柱状）
  renderChart(userRef.value, {
    tooltip: { trigger: 'axis' },
    grid: { left: 30, right: 14, top: 20, bottom: 24 },
    xAxis: { type: 'category', data: d.user_growth.map((i) => i.date), axisLabel: { fontSize: 10, color: '#5C6B64', interval: Math.max(0, Math.floor(d.user_growth.length / 7)) } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10, color: '#5C6B64' } },
    series: [{ type: 'bar', data: d.user_growth.map((i) => i.count), itemStyle: { color: '#9B6FD8', borderRadius: [3, 3, 0, 0] } }],
  })
}

function lineOption(data, key, color, name) {
  const labels = data.map((i) => i.date)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 34, right: 14, top: 20, bottom: 24 },
    xAxis: { type: 'category', data: labels, boundaryGap: false, axisLabel: { fontSize: 10, color: '#5C6B64', interval: Math.max(0, Math.floor(labels.length / 7)) } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10, color: '#5C6B64' } },
    series: [{
      type: 'line', data: data.map((i) => i[key]),
      smooth: true, symbol: 'circle', symbolSize: 5,
      lineStyle: { color, width: 2 },
      itemStyle: { color },
      areaStyle: { color: color + '22' },
    }],
  }
}

function switchRange(r) {
  if (range.value === r) return
  range.value = r
  load()
}

onMounted(load)
onBeforeUnmount(() => charts.forEach((c) => c.dispose()))
</script>

<style scoped>
.bar-fill { height: 100%; border-radius: 4px; transition: width .4s ease; }
.pulse-range { display: flex; gap: 4px; background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 2px; }
.range-btn {
  background: transparent; border: none; font-size: 12px; color: var(--ink-soft);
  padding: 4px 12px; border-radius: 4px; transition: all .15s;
}
.range-btn:hover { color: var(--ink); }
.range-btn.active { background: var(--gold); color: #fff; font-weight: 600; }
@media (max-width: 900px) {
  .grid2 { grid-template-columns: 1fr; }
}
</style>
