<template>
  <div class="scroll">
    <div class="page-title">设置</div>

    <!-- 个人信息 -->
    <div class="page-card">
      <div class="page-label">个人信息</div>
      <div style="display:flex;align-items:center;gap:14px;">
        <!-- 头像 -->
        <div class="profile-avatar" :style="{ background: avatarGrad }">
          {{ avatarLetter }}
        </div>
        <div style="flex:1;">
          <div style="font-weight:600;font-size:15px;">{{ userStore.displayName }}</div>
          <div style="font-size:12px;color:var(--sub);">{{ userStore.email }}</div>
        </div>
      </div>
      <!-- 昵称编辑 -->
      <div style="display:flex;gap:8px;margin-top:14px;">
        <input v-model="nicknameInput" placeholder="设置昵称" class="form-input" style="flex:1;" maxlength="20" />
        <button @click="saveProfile" :disabled="saving" class="btn-primary" style="width:auto;padding:10px 16px;font-size:13px;">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
      <p v-if="profileMsg" style="font-size:12px;color:var(--honey-deep);margin-top:6px;">{{ profileMsg }}</p>
    </div>

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
    <div class="page-card">
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
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { apiGetReminders, apiCreateReminder, apiDeleteReminder, apiGetProfile, apiUpdateProfile } from '../api/index'

const userStore = useUserStore()
const reminders = ref([])
const reminderContent = ref('')
const reminderTime = ref('')
const nicknameInput = ref(userStore.nickname || '')
const saving = ref(false)
const profileMsg = ref('')

const avatarColors = [
  'linear-gradient(135deg, #FFD0A8, #FF9F7A)',
  'linear-gradient(135deg, #A8E6CF, #5FBE63)',
  'linear-gradient(135deg, #B8D4F0, #5FB0E8)',
  'linear-gradient(135deg, #FFB8C8, #FF6F91)',
  'linear-gradient(135deg, #F5D8A8, #FF9F45)',
  'linear-gradient(135deg, #D4B8F0, #9B6FD8)',
]
const avatarGrad = computed(() => {
  const idx = userStore.email ? userStore.email.length % avatarColors.length : 0
  return avatarColors[idx]
})
const avatarLetter = computed(() => {
  return (userStore.displayName || 'U')[0].toUpperCase()
})

onMounted(async () => {
  reminders.value = (await apiGetReminders()).reminders || []
  // 加载用户信息
  try {
    const res = await apiGetProfile()
    if (res.success && res.user) {
      userStore.setProfile(res.user.nickname, res.user.avatar_url)
      nicknameInput.value = res.user.nickname || ''
    }
  } catch (e) {
    console.error('loadProfile error:', e)
  }
})

async function saveProfile() {
  saving.value = true
  profileMsg.value = ''
  try {
    const res = await apiUpdateProfile({ nickname: nicknameInput.value || '' })
    if (res.success) {
      userStore.setProfile(res.user.nickname, res.user.avatar_url)
      profileMsg.value = '已保存'
    } else {
      profileMsg.value = res.message || '保存失败'
    }
  } catch (e) {
    profileMsg.value = '网络错误，请检查后端是否启动'
    console.error('saveProfile error:', e)
  } finally {
    saving.value = false
    setTimeout(() => { profileMsg.value = '' }, 2000)
  }
}

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

<style scoped>
.profile-avatar {
  width: 50px; height: 50px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #fff; font-weight: 700;
  flex-shrink: 0; box-shadow: 0 4px 12px rgba(0,0,0,.08);
}
</style>
