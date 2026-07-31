<template>
  <div>
    <div class="page-title">系统设置</div>
    <div class="page-sub">模型配置、工具开关与管理员账号</div>

    <!-- 模型配置 -->
    <div class="card" style="margin-top:18px;">
      <div style="font-weight:600;font-size:14px;margin-bottom:14px;">模型配置</div>
      <div class="field-row">
        <div class="field">
          <label>API Key</label>
          <input v-model="settings.model_key" type="password" placeholder="sk-..." class="set-input" />
        </div>
        <div class="field">
          <label>模型名称</label>
          <input v-model="settings.model_name" placeholder="deepseek-chat" class="set-input" />
        </div>
        <div class="field" style="max-width:120px;">
          <label>温度</label>
          <input v-model="settings.model_temperature" type="number" step="0.1" min="0" max="2" class="set-input" />
        </div>
      </div>
      <div style="font-size:11px;color:var(--ink-soft);margin-top:4px;">保存后需重启后端生效（当前未接入运行时读取）</div>
      <button class="btn-gold" style="margin-top:12px;" :class="{ saved: savedKeys.model }" @click="saveSetting('model_key'); saveSetting('model_name'); saveSetting('model_temperature')">
        {{ savedKeys.model ? '✓ 已保存' : '保存模型配置' }}
      </button>
    </div>

    <!-- 工具开关 -->
    <div class="card" style="margin-top:16px;">
      <div style="font-weight:600;font-size:14px;margin-bottom:6px;">工具开关</div>
      <div style="font-size:11px;color:var(--ink-soft);margin-bottom:12px;">控制用户端可用能力（保存后需重启后端生效）</div>
      <div v-for="t in tools" :key="t.key" style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line);">
        <div>
          <div style="font-size:14px;">{{ t.label }}</div>
          <div style="font-size:12px;color:var(--ink-soft);">{{ t.desc }}</div>
        </div>
        <button :class="['switch', settings[t.key] === 'true' ? 'on' : '']" @click="toggleTool(t.key)">
          <span class="knob"></span>
        </button>
      </div>
      <p v-if="toolMsg" style="font-size:12px;color:var(--moss);margin-top:8px;">{{ toolMsg }}</p>
    </div>

    <!-- 管理员账号 -->
    <div class="card" style="margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div style="font-weight:600;font-size:14px;">管理员账号</div>
        <button class="btn-gold" @click="showCreate = true">＋ 新增管理员</button>
      </div>
      <table class="table">
        <thead><tr><th>邮箱</th><th>昵称</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="a in admins" :key="a.id">
            <td>{{ a.email }}</td>
            <td>{{ a.nickname || '—' }}</td>
            <td><span class="badge" :class="a.role === 'super' ? 'badge-gold' : 'badge-moss'">{{ a.role === 'super' ? '超级' : '普通' }}</span></td>
            <td><span class="badge" :class="a.status === 'disabled' ? 'badge-berry' : 'badge-moss'">{{ a.status === 'disabled' ? '已禁用' : '正常' }}</span></td>
            <td>
              <button class="row-btn" @click="resetPwd(a)">重置密码</button>
              <button v-if="a.status === 'active'" class="row-btn danger" @click="toggleAdmin(a, 'disabled')">禁用</button>
              <button v-else class="row-btn moss" @click="toggleAdmin(a, 'active')">启用</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增管理员弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <b>新增管理员</b>
          <button class="modal-close" @click="showCreate = false">×</button>
        </div>
        <div class="field">
          <label>邮箱</label>
          <input v-model="createForm.email" type="email" placeholder="ops@comate.local" class="set-input" />
        </div>
        <div class="field">
          <label>密码（至少 6 位）</label>
          <input v-model="createForm.password" type="password" class="set-input" />
        </div>
        <div class="field">
          <label>昵称</label>
          <input v-model="createForm.nickname" placeholder="选填" class="set-input" />
        </div>
        <div class="field">
          <label>角色</label>
          <select v-model="createForm.role" class="set-input">
            <option value="admin">普通管理员</option>
            <option value="super">超级管理员</option>
          </select>
        </div>
        <button class="btn-gold" style="width:100%;" @click="createAdmin">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiAdminBillingRules, apiAdminSaveSetting, apiAdminListAdmins, apiAdminCreateAdmin, apiAdminAdminStatus, apiAdminAdminPassword } from '../api'

const settings = ref({ model_key: '', model_name: '', model_temperature: '', tool_search: '', tool_weather: '', tool_shopping: '' })
const savedKeys = ref({})
const toolMsg = ref('')
const admins = ref([])
const showCreate = ref(false)
const createForm = ref({ email: '', password: '', nickname: '', role: 'admin' })

const tools = [
  { key: 'tool_search', label: '联网搜索', desc: 'Firecrawl 实时搜索（对话工具）' },
  { key: 'tool_weather', label: '天气查询', desc: '和风天气（对话工具）' },
  { key: 'tool_shopping', label: '购物比价', desc: '购物计划实时搜索' },
]

async function load() {
  const res = await apiAdminBillingRules()
  if (res.success) {
    settings.value = { model_key: '', model_name: '', model_temperature: '', tool_search: '', tool_weather: '', tool_shopping: '', ...res.data.settings }
  }
  const adminsRes = await apiAdminListAdmins()
  if (adminsRes.success) admins.value = adminsRes.data
}

async function saveSetting(key) {
  const res = await apiAdminSaveSetting(key, settings.value[key] || '')
  if (res.success) savedKeys.value.model = true
}

async function toggleTool(key) {
  const next = settings.value[key] === 'true' ? 'false' : 'true'
  const res = await apiAdminSaveSetting(key, next)
  if (res.success) {
    settings.value[key] = next
    toolMsg.value = '已' + (next === 'true' ? '开启' : '关闭')
  }
}

async function createAdmin() {
  if (!createForm.value.email.includes('@') || createForm.value.password.length < 6) return
  const res = await apiAdminCreateAdmin(createForm.value)
  if (res.success) {
    showCreate.value = false
    createForm.value = { email: '', password: '', nickname: '', role: 'admin' }
    load()
  }
}

async function toggleAdmin(a, s) {
  const res = await apiAdminAdminStatus(a.id, s)
  if (res.success) load()
}

async function resetPwd(a) {
  const pwd = prompt(`为 ${a.email} 设置新密码（至少 6 位）`)
  if (!pwd || pwd.length < 6) return
  const res = await apiAdminAdminPassword(a.id, pwd)
  if (res.success) alert(res.message)
}

onMounted(load)
</script>

<style scoped>
.field-row { display: flex; gap: 14px; flex-wrap: wrap; }
.field { flex: 1; min-width: 160px; }
.field label { display: block; font-size: 12px; color: var(--ink-soft); margin-bottom: 6px; }
.set-input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
  font-size: 13px;
  outline: none;
}
.set-input:focus { border-color: var(--gold); }

.btn-gold.saved { background: var(--moss); }

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

.row-btn {
  background: none; border: 1px solid var(--line); border-radius: 4px;
  font-size: 12px; color: var(--ink-soft); padding: 3px 10px; margin-right: 4px;
}
.row-btn:hover { border-color: var(--gold); color: var(--ink); }
.row-btn.danger:hover { border-color: var(--berry); color: var(--berry); }
.row-btn.moss:hover { border-color: var(--moss); color: var(--moss); }

.modal-mask {
  position: fixed; inset: 0; background: rgba(20, 32, 26, .45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal { width: 400px; background: var(--bg); border-radius: 12px; padding: 24px; }
.modal-close { background: none; border: none; font-size: 22px; color: var(--ink-soft); cursor: pointer; }
</style>
