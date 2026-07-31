<template>
  <div>
    <div class="page-title">计费规则</div>
    <div class="page-sub">配置各项功能的积分消耗与全局策略</div>

    <!-- 全局策略 -->
    <div class="card" style="margin-top:18px;">
      <div style="font-weight:600;font-size:14px;margin-bottom:14px;">全局策略</div>
      <div style="display:flex;flex-wrap:wrap;gap:24px;">
        <div>
          <div style="font-size:12px;color:var(--ink-soft);margin-bottom:8px;">扣费模式</div>
          <div class="toggle-row">
            <button :class="['mode-btn', settings.billing_enforce === 'false' ? 'active' : '']" @click="setMode('false')">
              宽松
              <small>余额不足不拦截</small>
            </button>
            <button :class="['mode-btn', settings.billing_enforce === 'true' ? 'active' : '']" @click="setMode('true')">
              严格
              <small>不足则拒绝操作</small>
            </button>
          </div>
        </div>
        <div>
          <div style="font-size:12px;color:var(--ink-soft);margin-bottom:8px;">新用户注册赠送（积分）</div>
          <div style="display:flex;gap:8px;">
            <input v-model.number="bonusInput" type="number" min="0" class="small-input" />
            <button class="btn-gold" @click="saveBonus">保存</button>
          </div>
        </div>
      </div>
      <p v-if="globalMsg" style="font-size:12px;color:var(--moss);margin-top:10px;">{{ globalMsg }}</p>
    </div>

    <!-- 规则列表 -->
    <div class="card" style="margin-top:16px;padding:0;overflow:hidden;">
      <table class="table">
        <thead>
          <tr>
            <th>计费项</th>
            <th style="width:120px;">单价（积分）</th>
            <th style="width:100px;">启用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rules" :key="r.item_key">
            <td>
              <div style="font-weight:500;">{{ r.item_name }}</div>
              <div style="font-size:11px;color:var(--ink-soft);">{{ r.item_key }}</div>
            </td>
            <td>
              <input v-model.number="r.price" type="number" min="0" class="small-input" style="width:80px;" />
            </td>
            <td>
              <button :class="['switch', r.enabled ? 'on' : '']" @click="r.enabled = !r.enabled">
                <span class="knob"></span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div style="display:flex;justify-content:flex-end;margin-top:16px;align-items:center;gap:12px;">
      <p v-if="saveMsg" style="font-size:12px;color:var(--moss);">{{ saveMsg }}</p>
      <button class="btn-gold" :class="{ saved: rulesSaved }" :disabled="saving" @click="saveRules">
        {{ saving ? '保存中…' : rulesSaved ? '✓ 已保存' : '保存计费规则' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { apiAdminBillingRules, apiAdminSaveRules, apiAdminSaveSetting } from '../api'

const rules = ref([])
const settings = ref({ billing_enforce: 'false', register_bonus: '20' })
const bonusInput = ref(20)
const saving = ref(false)
const saveMsg = ref('')
const globalMsg = ref('')
const rulesSaved = ref(false)

async function load() {
  const res = await apiAdminBillingRules()
  if (res.success) {
    rules.value = res.data.rules
    settings.value = { billing_enforce: res.data.billing_enforce, register_bonus: res.data.register_bonus }
    bonusInput.value = Number(res.data.register_bonus || 0)
  }
}

// 规则或赠送积分被修改时，复位"已保存"状态并清除旧提示，避免误导
watch(
  rules,
  () => { rulesSaved.value = false; saveMsg.value = '' },
  { deep: true }
)
watch(bonusInput, () => { globalMsg.value = '' })

async function setMode(mode) {
  const res = await apiAdminSaveSetting('billing_enforce', mode)
  if (res.success) {
    settings.value.billing_enforce = mode
    globalMsg.value = '已切换为' + (mode === 'true' ? '严格' : '宽松') + '模式'
  }
}

async function saveBonus() {
  const res = await apiAdminSaveSetting('register_bonus', String(bonusInput.value))
  if (res.success) globalMsg.value = '✓ 注册赠送积分已保存'
}

async function saveRules() {
  saving.value = true
  saveMsg.value = ''
  try {
    const res = await apiAdminSaveRules(rules.value)
    if (res.success) {
      rulesSaved.value = true
      saveMsg.value = '✓ 计费规则已保存'
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toggle-row { display: flex; gap: 8px; }
.mode-btn {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 10px 20px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  font-size: 14px; font-weight: 600;
  color: var(--ink-soft);
  transition: all .15s;
}
.mode-btn small { font-size: 11px; font-weight: 400; color: var(--ink-soft); }
.mode-btn.active { border-color: var(--gold); background: var(--gold-soft); color: #8A6A1C; }
.mode-btn.active small { color: #8A6A1C; }

.small-input {
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
  font-size: 13px;
  outline: none;
  width: 100px;
}
.small-input:focus { border-color: var(--gold); }

/* 保存成功态 */
.btn-gold.saved { background: var(--moss); cursor: default; }

.switch {
  width: 44px; height: 24px;
  border-radius: 100px;
  border: none;
  background: var(--line);
  position: relative;
  cursor: pointer;
  transition: background .2s;
}
.switch.on { background: var(--moss); }
.switch .knob {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.2);
  transition: left .2s;
}
.switch.on .knob { left: 23px; }
</style>
