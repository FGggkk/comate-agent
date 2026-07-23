<template>
  <div class="scroll">
    <div class="page-title">设置</div>

    <!-- SOUL -->
    <div class="page-card">
      <div class="page-label">当前风格</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="companion" style="--s:40px;"><div class="companion-body"><span class="companion-eye l"></span><span class="companion-eye r"></span><span class="companion-cheek l"></span><span class="companion-cheek r"></span><span class="companion-mouth"></span></div><div class="companion-sprout"><span class="companion-sprout-r"></span></div></div>
        <div>
          <div style="font-weight:600;">温柔陪伴型</div>
          <div style="font-size:12px;color:var(--sub);">温和、耐心</div>
        </div>
      </div>
    </div>

    <!-- 提醒 -->
    <div class="page-card" style="margin-top:12px;">
      <div class="page-label">提醒</div>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input v-model="reminderContent" placeholder="提醒内容..." class="form-input" style="flex:1;" />
        <input v-model="reminderTime" type="datetime-local" class="form-input" style="flex:0 0 auto;width:auto;" />
        <button @click="createReminder" class="btn-primary" style="width:auto;padding:10px 16px;font-size:13px;">添加</button>
      </div>
      <div v-for="r in reminders" :key="r.id" style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line);">
        <div><div style="font-size:14px;">{{ r.content }}</div><div style="font-size:11px;color:var(--sub);">{{ formatTime(r.remind_at) }}</div></div>
        <button @click="deleteReminder(r.id)" style="font-size:12px;color:var(--berry);padding:4px 8px;">取消</button>
      </div>
      <div v-if="reminders.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无提醒</div>
    </div>

    <!-- 退出 -->
    <button @click="logout" style="width:100%;margin-top:20px;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;color:var(--berry);text-align:center;">
      退出登录
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { apiGetReminders, apiCreateReminder, apiDeleteReminder } from '../api/index'

const userStore = useUserStore()
const reminders = ref([])
const reminderContent = ref('')
const reminderTime = ref('')

onMounted(async () => { reminders.value = (await apiGetReminders()).reminders || [] })

async function createReminder() {
  if (!reminderContent.value || !reminderTime.value) return
  await apiCreateReminder(reminderContent.value, new Date(reminderTime.value).toISOString())
  reminderContent.value = ''; reminderTime.value = ''
  reminders.value = (await apiGetReminders()).reminders || []
}

async function deleteReminder(id) { await apiDeleteReminder(id); reminders.value = (await apiGetReminders()).reminders || [] }

function formatTime(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '' }
function logout() { userStore.logout(); window.location.reload() }
</script>
