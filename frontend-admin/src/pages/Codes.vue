<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:flex-end;">
      <div>
        <div class="page-title">兑换码</div>
        <div class="page-sub">生成、发放与管理积分兑换码</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn-ghost" @click="exportCsv">导出 CSV</button>
        <button class="btn-gold" @click="openGenerate">＋ 生成兑换码</button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div style="display:flex;gap:6px;margin:18px 0 12px;">
      <button v-for="t in tabs" :key="t.key" :class="['tab-filter', status === t.key ? 'active' : '']" @click="switchStatus(t.key)">
        {{ t.label }}
      </button>
    </div>

    <!-- 表格 -->
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="table">
        <thead>
          <tr>
            <th>兑换码</th>
            <th>面额</th>
            <th>状态</th>
            <th>使用</th>
            <th>有效期</th>
            <th>备注</th>
            <th style="width:90px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in items" :key="c.id">
            <td class="num" style="letter-spacing:.04em;">{{ c.code }}</td>
            <td><b class="num">{{ c.amount }}</b> 积分</td>
            <td><span :class="['badge', badgeClass(c.status)]">{{ statusLabel(c.status) }}</span></td>
            <td class="num">{{ c.used_count }}/{{ c.max_uses }}</td>
            <td class="num" style="color:var(--ink-soft);font-size:12px;">{{ c.expires_at ? c.expires_at.slice(0, 10) : '永久' }}</td>
            <td style="color:var(--ink-soft);">{{ c.note || '—' }}</td>
            <td>
              <button class="row-btn" @click="copyCode(c.code)">复制</button>
              <button v-if="c.status === 'active'" class="row-btn danger" @click="disableCode(c)">作废</button>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="7" style="text-align:center;color:var(--ink-soft);padding:40px 0;">
              还没有兑换码，点击「生成兑换码」创建
            </td>
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

    <!-- 生成弹窗 -->
    <div v-if="showGen" class="modal-mask" @click.self="showGen = false">
      <div class="modal">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
          <b style="font-size:16px;">生成兑换码</b>
          <button class="modal-close" @click="showGen = false">×</button>
        </div>

        <div v-if="!genResult" class="gen-form">
          <div class="field">
            <label>面额（积分）</label>
            <input v-model.number="gen.amount" type="number" min="1" />
          </div>
          <div style="display:flex;gap:12px;">
            <div class="field" style="flex:1;">
              <label>数量</label>
              <input v-model.number="gen.count" type="number" min="1" max="500" />
            </div>
            <div class="field" style="flex:1;">
              <label>有效期（天）</label>
              <input v-model.number="gen.expires_days" type="number" min="1" placeholder="永久" />
            </div>
          </div>
          <div class="field">
            <label>单码可兑换次数</label>
            <input v-model.number="gen.max_uses" type="number" min="1" value="1" />
          </div>
          <div class="field">
            <label>备注</label>
            <input v-model="gen.note" placeholder="如：第一批内测用户" />
          </div>
          <button class="btn-gold" style="width:100%;" :disabled="genLoading" @click="doGenerate">
            {{ genLoading ? '生成中…' : '生成' }}
          </button>
        </div>

        <div v-else class="gen-result">
          <div style="text-align:center;margin-bottom:14px;">
            <div class="num" style="font-size:26px;font-weight:700;color:var(--gold);">已生成 {{ genResult.count }} 个</div>
            <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">批次 {{ genResult.batch_no }} · 每个 {{ gen.amount }} 积分</div>
          </div>
          <div class="code-list">
            <div v-for="c in genResult.codes" :key="c.id" class="code-row num" @click="copyCode(c.code)">
              {{ c.code }} <span style="color:var(--ink-soft);font-size:11px;">点击复制</span>
            </div>
          </div>
          <div style="display:flex;gap:8px;margin-top:16px;">
            <button class="btn-ghost" style="flex:1;" @click="copyAll">复制全部</button>
            <button class="btn-gold" style="flex:1;" @click="finishGen">完成</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiAdminCodes, apiAdminCodesGenerate, apiAdminCodesDisable, apiAdminCodesExport } from '../api'

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '未用' },
  { key: 'used', label: '已用' },
  { key: 'expired', label: '过期' },
  { key: 'disabled', label: '作废' },
]

const status = ref('all')
const items = ref([])
const total = ref(0)
const page = ref(1)
const sizeOptions = [10, 20, 50, 100]
const size = ref(20)

const showGen = ref(false)
const genLoading = ref(false)
const gen = ref({ amount: 100, count: 10, expires_days: 30, max_uses: 1, note: '' })
const genResult = ref(null)

const statusLabel = (s) => ({ active: '未用', used: '已用', expired: '过期', disabled: '作废' }[s] || s)
const badgeClass = (s) => ({ active: 'badge-gold', used: 'badge-moss', expired: '', disabled: '' }[s] || '')

async function load() {
  const res = await apiAdminCodes(status.value, page.value, '', size.value)
  if (res.success) {
    items.value = res.data.items
    total.value = res.data.total
  }
}
function switchStatus(k) { status.value = k; page.value = 1; load() }
function goPage(p) { page.value = p; load() }
function changeSize() { page.value = 1; load() }

function openGenerate() { genResult.value = null; showGen.value = true }
async function doGenerate() {
  genLoading.value = true
  try {
    const res = await apiAdminCodesGenerate(gen.value)
    if (res.success) genResult.value = res.data
  } finally { genLoading.value = false }
}
function finishGen() { showGen.value = false; load() }

async function disableCode(c) {
  if (!confirm(`作废兑换码 ${c.code}？已兑换的不受影响`)) return
  const res = await apiAdminCodesDisable(c.id)
  if (res.success) load()
}

async function copyCode(code) {
  try { await navigator.clipboard.writeText(code) } catch {}
  alert(`已复制 ${code}`)
}
function copyAll() {
  const text = genResult.value.codes.map((c) => c.code).join('\n')
  try { navigator.clipboard.writeText(text) } catch {}
  alert('已复制全部兑换码')
}

async function exportCsv() {
  const blob = await apiAdminCodesExport()
  if (!blob) return
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '兑换码.csv'
  a.click()
  URL.revokeObjectURL(url)
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
.size-select:focus { border-color: var(--gold); }

.modal-mask {
  position: fixed; inset: 0;
  background: rgba(20, 32, 26, .45);
  display: flex; align-items: center; justify-content: center;
  z-index: 50;
}
.modal {
  width: 420px; max-height: 80vh; overflow-y: auto;
  background: var(--bg);
  border-radius: 12px;
  padding: 24px;
}
.modal-close { background: none; border: none; font-size: 22px; color: var(--ink-soft); cursor: pointer; }
.gen-form input { width: 100%; padding: 9px 12px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); font-size: 14px; outline: none; }
.gen-form input:focus { border-color: var(--gold); }

.code-list { max-height: 220px; overflow-y: auto; border: 1px solid var(--line); border-radius: 8px; }
.code-row {
  padding: 9px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  cursor: pointer;
  display: flex; justify-content: space-between; align-items: center;
}
.code-row:last-child { border-bottom: none; }
.code-row:hover { background: var(--gold-soft); }
</style>
