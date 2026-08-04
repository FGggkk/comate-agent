<template>
  <div>
    <div class="page-title">用户</div>
    <div class="page-sub">用户列表、详情与积分管理</div>

    <!-- 搜索 + 筛选 -->
    <div style="display:flex;gap:8px;margin:18px 0 12px;flex-wrap:wrap;">
      <input v-model="q" class="search-input" placeholder="搜索邮箱 / 昵称…" @keydown.enter="search" />
      <button v-for="t in tabs" :key="t.key" :class="['tab-filter', status === t.key ? 'active' : '']" @click="switchStatus(t.key)">
        {{ t.label }}
      </button>
    </div>

    <!-- 表格 -->
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="table">
        <thead>
          <tr>
            <th>用户</th>
            <th>邮箱</th>
            <th>积分</th>
            <th>状态</th>
            <th>RAG</th>
            <th>注册时间</th>
            <th style="width:120px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in items" :key="u.id" @click="openDetail(u.id)" style="cursor:pointer;">
            <td>
              <div style="display:flex;align-items:center;gap:10px;">
                <span class="user-av">{{ (u.nickname || u.email[0]).toUpperCase() }}</span>
                <span>{{ u.nickname || '—' }}</span>
              </div>
            </td>
            <td style="color:var(--ink-soft);">{{ u.email }}</td>
            <td><b class="num">{{ u.balance }}</b></td>
            <td><span :class="['badge', u.status === 'disabled' ? 'badge-berry' : 'badge-moss']">{{ u.status === 'disabled' ? '已禁用' : '正常' }}</span></td>
            <td @click.stop>
              <label class="rag-switch" :title="u.rag_enabled ? '关闭 RAG' : '启用 RAG'">
                <input type="checkbox" :checked="u.rag_enabled" @change="toggleRag(u, $event.target.checked)" />
                <span></span>
              </label>
            </td>
            <td class="num" style="color:var(--ink-soft);font-size:12px;">{{ (u.created_at || '').slice(0, 10) }}</td>
            <td @click.stop>
              <button class="row-btn" @click="openDetail(u.id)">详情</button>
              <button v-if="u.status === 'active'" class="row-btn danger" @click="toggleStatus(u, 'disabled')">禁用</button>
              <button v-else class="row-btn moss" @click="toggleStatus(u, 'active')">启用</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="7" style="text-align:center;color:var(--ink-soft);padding:40px 0;">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;flex-wrap:wrap;gap:8px;">
      <div style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-soft);">
        <span class="num">共 {{ total }} 条</span>
        <span style="color:var(--line);">|</span>
        <span>每页</span>
        <select v-model="size" class="size-select" @change="changeSize">
          <option v-for="s in sizeOptions" :key="s" :value="s">{{ s }} 条</option>
        </select>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn-ghost" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="num" style="font-size:13px;min-width:24px;text-align:center;">{{ page }}</span>
        <button class="btn-ghost" :disabled="page * size >= total" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>

    <!-- 详情抽屉 -->
    <div v-if="detail" class="drawer-mask" @click.self="detail = null">
      <div class="drawer">
        <div class="drawer-head">
          <b style="font-size:16px;">用户详情</b>
          <button class="modal-close" @click="detail = null">×</button>
        </div>

        <div class="card" style="margin-bottom:14px;">
          <div style="display:flex;align-items:center;gap:14px;">
            <span class="user-av lg">{{ (detail.nickname || detail.email[0]).toUpperCase() }}</span>
            <div>
              <div style="font-weight:600;font-size:15px;">{{ detail.nickname || '未设置昵称' }}</div>
              <div style="font-size:12px;color:var(--ink-soft);">{{ detail.email }}</div>
              <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">注册于 {{ (detail.created_at || '').slice(0, 10) }}</div>
            </div>
          </div>
        </div>

        <!-- 积分 -->
        <div class="card" style="margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-size:12px;color:var(--ink-soft);">当前积分</div>
              <div class="num" style="font-size:24px;font-weight:700;color:var(--gold);">{{ detail.balance }}</div>
            </div>
            <div style="display:flex;gap:8px;">
              <input v-model.number="adjAmount" type="number" placeholder="±积分" class="adj-input" @input="resetAdj" />
              <button class="btn-gold" :class="{ saved: adjDone }" @click="adjustBalance">{{ adjDone ? '✓ 已调整' : '调整' }}</button>
            </div>
          </div>
          <p v-if="adjMsg" style="font-size:12px;color:var(--moss);margin-top:8px;">{{ adjMsg }}</p>
        </div>

        <!-- 灵魂卡槽 -->
        <div class="card" style="margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div>
              <div style="font-size:12px;color:var(--ink-soft);">灵魂卡槽上限</div>
              <div class="num" style="font-size:20px;font-weight:700;color:var(--honey);">{{ detail.slot_capacity ?? 6 }} 格</div>
            </div>
            <div style="display:flex;gap:6px;">
              <button
                v-for="c in [6, 9, 12]"
                :key="c"
                class="btn-ghost"
                :style="(detail.slot_capacity ?? 6) === c ? slotBtnActiveStyle : ''"
                :disabled="slotSaving"
                @click="setSlotCapacity(c)"
              >{{ c }}</button>
            </div>
          </div>
          <p v-if="slotMsg" style="font-size:12px;color:var(--moss);margin-top:4px;">{{ slotMsg }}</p>
        </div>

        <!-- SOUL -->
        <div class="card" style="margin-bottom:14px;">
          <div style="font-size:12px;color:var(--ink-soft);margin-bottom:8px;">SOUL 库存（{{ detail.souls?.length || 0 }}）</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;">
            <span v-for="s in detail.souls || []" :key="s.id" class="soul-chip">{{ s.status }}</span>
            <span v-if="!detail.souls?.length" style="font-size:13px;color:var(--ink-soft);">无</span>
          </div>
        </div>

        <!-- 流水 -->
        <div class="card" style="padding:0;overflow:hidden;">
          <div style="font-size:12px;color:var(--ink-soft);padding:14px 16px 6px;">最近流水</div>
          <table class="table">
            <thead><tr><th>类型</th><th>变动</th><th>说明</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="t in detail.transactions || []" :key="t.id">
                <td style="font-size:12px;">{{ typeLabel(t.type) }}</td>
                <td :style="{ fontWeight: 600, color: t.change >= 0 ? 'var(--moss)' : 'var(--berry)' }">{{ t.change >= 0 ? '+' : '' }}{{ t.change }}</td>
                <td style="font-size:12px;color:var(--ink-soft);">{{ t.note || '—' }}</td>
                <td class="num" style="font-size:11px;color:var(--ink-soft);">{{ (t.created_at || '').slice(0, 16).replace('T', ' ') }}</td>
              </tr>
              <tr v-if="!detail.transactions?.length"><td colspan="4" style="text-align:center;color:var(--ink-soft);padding:20px;">暂无流水</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiAdminUsers, apiAdminUserDetail, apiAdminUserStatus, apiAdminUserBalance, apiAdminUserSlotCapacity, apiAdminUserRagEnabled } from '../api'

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '正常' },
  { key: 'disabled', label: '已禁用' },
]

const q = ref('')
const status = ref('all')
const items = ref([])
const total = ref(0)
const page = ref(1)
const sizeOptions = [10, 20, 50, 100]
const size = ref(20)

const detail = ref(null)
const adjAmount = ref(0)
const adjMsg = ref('')
const adjDone = ref(false)

const slotMsg = ref('')
const slotSaving = ref(false)
const slotBtnActiveStyle = { background: 'var(--honey)', color: '#fff', borderColor: 'var(--honey)' }

async function setSlotCapacity(c) {
  if (!detail.value || slotSaving.value) return
  slotSaving.value = true
  slotMsg.value = ''
  const res = await apiAdminUserSlotCapacity(detail.value.id, c)
  if (res.success) {
    detail.value.slot_capacity = c
    slotMsg.value = res.message
  } else {
    slotMsg.value = res.message || '设置失败'
  }
  slotSaving.value = false
}

const typeLabel = (t) => ({ recharge: '充值', consume: '消费', admin: '管理员' }[t] || t)

async function load() {
  const res = await apiAdminUsers(q.value, status.value, page.value, size.value)
  if (res.success) {
    items.value = res.data.items
    total.value = res.data.total
  }
}
function search() { page.value = 1; load() }
function switchStatus(k) { status.value = k; page.value = 1; load() }
function goPage(p) { page.value = p; load() }
function changeSize() { page.value = 1; load() }

async function openDetail(id) {
  const res = await apiAdminUserDetail(id)
  if (res.success) { detail.value = res.data; adjAmount.value = 0; adjMsg.value = ''; adjDone.value = false; slotMsg.value = ''; slotSaving.value = false }
}

function resetAdj() {
  adjDone.value = false
  adjMsg.value = ''
}

async function toggleStatus(u, s) {
  const res = await apiAdminUserStatus(u.id, s)
  if (res.success) { u.status = s; load() }
}

async function toggleRag(user, enabled) {
  const previous = user.rag_enabled
  user.rag_enabled = enabled
  const res = await apiAdminUserRagEnabled(user.id, enabled)
  if (!res.success) user.rag_enabled = previous
  if (detail.value?.id === user.id && res.success) detail.value.rag_enabled = enabled
}

async function adjustBalance() {
  if (!adjAmount.value) return
  const res = await apiAdminUserBalance(detail.value.id, adjAmount.value, '管理端调整')
  if (res.success) {
    detail.value.balance = res.balance
    adjMsg.value = res.message
    adjDone.value = true
    load()
  }
}

onMounted(load)
</script>

<style scoped>
.tab-filter {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: transparent;
  font-size: 13px;
  color: var(--ink-soft);
  transition: all .15s;
}
.tab-filter:hover { color: var(--ink); border-color: var(--gold); }
.tab-filter.active { background: var(--gold-soft); border-color: var(--gold); color: #8A6A1C; font-weight: 600; }

.search-input {
  flex: 1; min-width: 180px;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
  font-size: 13px;
  outline: none;
}
.search-input:focus { border-color: var(--gold); }

.row-btn {
  background: none;
  border: 1px solid var(--line);
  border-radius: 4px;
  font-size: 12px;
  color: var(--ink-soft);
  padding: 3px 10px;
  margin-right: 4px;
}
.row-btn:hover { border-color: var(--gold); color: var(--ink); }
.row-btn.danger:hover { border-color: var(--berry); color: var(--berry); }
.row-btn.moss:hover { border-color: var(--moss); color: var(--moss); }
.rag-switch { display:inline-flex; cursor:pointer; }
.rag-switch input { position:absolute; opacity:0; pointer-events:none; }
.rag-switch span { width:30px; height:17px; padding:2px; border-radius:10px; background:var(--line); transition:background .15s; }
.rag-switch span::after { content:''; display:block; width:13px; height:13px; border-radius:50%; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.2); transition:transform .15s; }
.rag-switch input:checked + span { background:var(--moss); }
.rag-switch input:checked + span::after { transform:translateX(13px); }
.rag-switch input:focus-visible + span { outline:2px solid var(--gold); outline-offset:2px; }

.user-av {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: var(--side);
  color: var(--gold);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
  flex-shrink: 0;
}
.user-av.lg { width: 44px; height: 44px; font-size: 17px; }

.size-select {
  padding: 5px 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
  font-size: 12px;
  color: var(--ink);
  outline: none;
  cursor: pointer;
}

.adj-input {
  width: 90px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
  font-size: 13px;
  outline: none;
}
.adj-input:focus { border-color: var(--gold); }

/* 调整成功态 */
.btn-gold.saved { background: var(--moss); }

.soul-chip {
  padding: 3px 10px;
  border-radius: 100px;
  background: var(--gold-soft);
  color: #8A6A1C;
  font-size: 12px;
}

.drawer-mask {
  position: fixed; inset: 0;
  background: rgba(20, 32, 26, .4);
  z-index: 40;
}
.drawer {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 440px; max-width: 92vw;
  background: var(--bg);
  padding: 22px;
  overflow-y: auto;
  box-shadow: -12px 0 40px rgba(0,0,0,.18);
}
.drawer-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal-close { background: none; border: none; font-size: 22px; color: var(--ink-soft); cursor: pointer; }
</style>
