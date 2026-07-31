<template>
  <div v-if="!activeSection" class="scroll">
    <div class="settings-hero">
      <svg viewBox="0 0 120 20" width="120" height="20" class="settings-hero-waves">
        <path d="M0 10 Q30 1 60 10 T120 10" stroke="var(--honey-soft)" fill="none" stroke-width="2"/>
        <path d="M0 14 Q30 5 60 14 T120 14" stroke="var(--sprout-soft)" fill="none" stroke-width="1.5" opacity=".72"/>
      </svg>
      <div class="settings-hero-icon">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none" stroke="var(--honey-deep)" stroke-width="1.6">
          <circle cx="16" cy="16" r="4"/>
          <path d="M16 4v4M16 24v4M4 16h4M24 16h4M7.5 7.5l2.8 2.8M21.7 21.7l2.8 2.8M24.5 7.5l-2.8 2.8M10.3 21.7l-2.8 2.8"/>
        </svg>
      </div>
      <div class="settings-title">设置</div>
      <div class="settings-sub">调整账号、风格和提醒</div>
    </div>

    <div class="settings-entry-list">
      <button class="settings-entry entry-profile" @click="activeSection = 'profile'">
        <span class="settings-entry-icon">
          <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="16" cy="11" r="5"/>
            <path d="M8 27c0-4.4 3.6-8 8-8s8 3.6 8 8"/>
          </svg>
        </span>
        <span class="settings-entry-body">
          <span class="settings-entry-title">个人信息</span>
          <span class="settings-entry-desc">头像、昵称和账号信息</span>
        </span>
        <svg class="settings-entry-arrow" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="7,4 13,10 7,16"/>
        </svg>
      </button>

      <button class="settings-entry entry-style" @click="activeSection = 'style'">
        <span class="settings-entry-icon">
          <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M16 4l2.6 5.4 5.9.8-4.3 4.1 1 5.8L16 17.3l-5.2 2.8 1-5.8-4.3-4.1 5.9-.8L16 4z"/>
            <path d="M8 25h16"/>
          </svg>
        </span>
        <span class="settings-entry-body">
          <span class="settings-entry-title">当前风格</span>
          <span class="settings-entry-desc">切换你的伴行小球</span>
        </span>
        <svg class="settings-entry-arrow" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="7,4 13,10 7,16"/>
        </svg>
      </button>

      <button class="settings-entry entry-reminder" @click="activeSection = 'reminders'">
        <span class="settings-entry-icon">
          <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M16 27a3 3 0 0 0 3-3h-6a3 3 0 0 0 3 3z"/>
            <path d="M9 22h14l-2-3v-5a5 5 0 0 0-10 0v5l-2 3z"/>
            <path d="M23 9l3-3M9 9L6 6"/>
          </svg>
        </span>
        <span class="settings-entry-body">
          <span class="settings-entry-title">提醒</span>
          <span class="settings-entry-desc">查看、添加和管理提醒</span>
        </span>
        <span v-if="reminders.length" class="settings-entry-count">{{ reminders.length }} 条</span>
        <svg class="settings-entry-arrow" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="7,4 13,10 7,16"/>
        </svg>
      </button>
    </div>

    <button @click="logout" class="logout-btn">退出登录</button>
  </div>

  <div v-else class="scroll settings-detail-scroll">
    <div class="settings-detail-top">
      <button class="settings-back-btn" @click="activeSection = ''">
        <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8">
          <polyline points="13,4 7,10 13,16"/>
        </svg>
        返回设置
      </button>
      <div>
        <div class="settings-detail-title">{{ activeSectionInfo.title }}</div>
        <div class="settings-detail-desc">{{ activeSectionInfo.desc }}</div>
      </div>
    </div>

    <section v-if="activeSection === 'profile'" class="settings-detail-card">
      <div class="profile-row">
        <div class="profile-avatar-wrap" @click="triggerUpload">
          <img v-if="userStore.avatarUrl" :src="userStore.avatarUrl" class="profile-avatar-img" />
          <div v-else class="profile-avatar" :style="{ background: avatarGrad }">
            {{ avatarLetter }}
          </div>
          <div class="profile-avatar-overlay">
            <span v-if="uploading">上传中...</span>
            <span v-else>更换头像</span>
          </div>
        </div>
        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileSelect" />
        <div class="profile-copy">
          <div class="profile-name">{{ userStore.displayName }}</div>
          <div class="profile-email">{{ userStore.email }}</div>
        </div>
      </div>
      <div class="profile-edit-row">
        <input v-model="nicknameInput" placeholder="设置昵称" class="form-input profile-input" maxlength="20" />
        <button @click="saveProfile" :disabled="saving" class="btn-primary settings-primary-btn">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
      <p v-if="profileMsg" class="settings-msg">{{ profileMsg }}</p>
    </section>

    <section v-else-if="activeSection === 'style'" class="settings-detail-card">
      <button class="current-style" @click="$emit('open-persona')">
        <SoulOrb :template="currentSoul || {}" size="sm" :active="!!currentSoul" />
        <div class="current-style-copy">
          <div>{{ currentSoul?.name || '还未注入人设' }}</div>
          <p>{{ currentSoul?.orb?.tone || '抽取小球后，可以切换伴行风格' }}</p>
        </div>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>
      <div v-if="ownedSouls.length" class="style-orbs">
        <button
          v-for="item in ownedSouls"
          :key="item.id"
          :class="['style-orb-btn', item.active ? 'active' : '']"
          :disabled="switchingSoulId === item.id"
          @click="switchSoul(item)"
        >
          <SoulOrb :template="item" size="sm" :active="item.active" />
          <span>{{ item.name }}</span>
        </button>
      </div>
      <div v-else class="style-empty">还没有获得人设小球</div>
      <p v-if="soulMsg" class="style-msg">{{ soulMsg }}</p>
    </section>

    <section v-else-if="activeSection === 'reminders'" class="settings-detail-card">
      <div class="reminder-form">
        <input v-model="reminderContent" placeholder="提醒内容..." class="form-input reminder-content-input" />
        <input v-model="reminderTime" type="datetime-local" class="form-input reminder-time-input" />
        <button @click="createReminder" class="btn-primary settings-primary-btn reminder-add">添加</button>
      </div>
      <div class="reminder-list">
        <div
          v-for="r in reminders"
          :key="r.id"
          :class="['reminder-row', { expired: isReminderExpired(r) }]"
        >
          <div class="reminder-main">
            <div class="reminder-title-line">
              <span class="reminder-content">{{ r.content }}</span>
              <span v-if="isReminderExpired(r)" class="reminder-expired-badge">已过期</span>
            </div>
            <div class="reminder-time">{{ formatTime(r.remind_at) }}</div>
          </div>
          <button @click="deleteReminder(r.id)" class="reminder-cancel">取消</button>
        </div>
        <div v-if="reminders.length === 0" class="reminder-empty">暂无提醒</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useUserStore } from '../stores/user'
import SoulOrb from '../components/SoulOrb.vue'
import {
  apiGetReminders,
  apiCreateReminder,
  apiDeleteReminder,
  apiGetProfile,
  apiUpdateProfile,
  apiUploadAvatar,
  apiGetSoulInventory,
  apiInjectSoul,
} from '../api/index'

const props = defineProps({
  refreshKey: { type: Number, default: 0 },
  reminderRefreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['open-persona', 'soul-changed'])

const userStore = useUserStore()
const activeSection = ref('')
const reminders = ref([])
const reminderContent = ref('')
const reminderTime = ref('')
const nowMs = ref(Date.now())
const nicknameInput = ref(userStore.nickname || '')
const saving = ref(false)
const uploading = ref(false)
const profileMsg = ref('')
const fileInput = ref(null)
const soulInventory = ref({ templates: [], current: null, owned_count: 0, total_count: 5 })
const soulMsg = ref('')
const switchingSoulId = ref('')

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
const ownedSouls = computed(() => (soulInventory.value.templates || []).filter((item) => item.owned))
const currentSoul = computed(() => soulInventory.value.current || ownedSouls.value.find((item) => item.active) || null)
const activeSectionInfo = computed(() => ({
  profile: { title: '个人信息', desc: '头像、昵称和账号信息' },
  style: { title: '当前风格', desc: '切换你的伴行小球' },
  reminders: { title: '提醒', desc: '查看、添加和管理提醒' },
}[activeSection.value] || { title: '设置', desc: '' }))
let reminderClock = null

onMounted(async () => {
  reminderClock = window.setInterval(() => { nowMs.value = Date.now() }, 60000)
  await loadReminders()
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
  await loadSoulInventory()
})
onBeforeUnmount(() => {
  if (reminderClock) window.clearInterval(reminderClock)
})
watch(() => props.refreshKey, loadSoulInventory)
watch(() => props.reminderRefreshKey, loadReminders)

async function loadReminders() {
  reminders.value = (await apiGetReminders()).reminders || []
}

async function loadSoulInventory() {
  try {
    const res = await apiGetSoulInventory()
    if (res.templates) soulInventory.value = res
  } catch (e) {
    console.error('loadSoulInventory error:', e)
  }
}

async function switchSoul(item) {
  if (!item?.owned || item.active || switchingSoulId.value) return
  switchingSoulId.value = item.id
  soulMsg.value = ''
  try {
    const res = await apiInjectSoul(item.id)
    if (res.success && res.inventory) {
      soulInventory.value = res.inventory
      soulMsg.value = '已切换当前风格'
      emit('soul-changed')
    } else {
      soulMsg.value = res.message || '切换失败'
    }
  } catch (e) {
    console.error('switchSoul error:', e)
    soulMsg.value = '切换失败，请稍后再试'
  } finally {
    switchingSoulId.value = ''
    setTimeout(() => { soulMsg.value = '' }, 1800)
  }
}

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
  const res = await apiCreateReminder(reminderContent.value, new Date(reminderTime.value).toISOString())
  if (res?.success === false) return
  if (res?.already_exists) {
    await loadReminders()
    return
  }
  reminderContent.value = ''; reminderTime.value = ''
  await loadReminders()
}

async function deleteReminder(id) { await apiDeleteReminder(id); await loadReminders() }

function triggerUpload() {
  if (!uploading.value) fileInput.value?.click()
}

async function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  profileMsg.value = ''
  try {
    const res = await apiUploadAvatar(file)
    if (res.success) {
      userStore.setProfile(userStore.nickname, res.avatar_url)
      profileMsg.value = '头像已更新'
    } else {
      profileMsg.value = res.message || '上传失败'
    }
  } catch {
    profileMsg.value = '上传失败，请检查后端和 COS 配置'
  } finally {
    uploading.value = false
    e.target.value = ''
    setTimeout(() => { profileMsg.value = '' }, 3000)
  }
}

function isReminderExpired(reminder) {
  if (reminder?.triggered) return true
  const remindAt = new Date(reminder?.remind_at).getTime()
  return Number.isFinite(remindAt) && remindAt <= nowMs.value
}

function formatTime(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '' }
function logout() { userStore.logout(); window.location.reload() }
</script>

<style scoped>
.settings-hero {
  text-align: center;
  padding: 18px 0 16px;
  position: relative;
  overflow: hidden;
}
.settings-hero-waves {
  width: 100%;
  height: 16px;
  margin-bottom: 8px;
}
.settings-hero-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 10px;
  border-radius: 16px;
  background: var(--honey-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.settings-hero-icon svg {
  width: 28px;
  height: 28px;
}
.settings-title {
  color: var(--ink);
  font-size: 22px;
  font-weight: 700;
}
.settings-sub {
  color: var(--sub);
  font-size: 13px;
  margin-top: 2px;
}
.settings-entry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 4px;
}
.settings-entry {
  width: 100%;
  min-height: 78px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: var(--r-lg);
  border: 1.5px solid transparent;
  text-align: left;
}
.entry-profile {
  background: rgba(255,255,255,.64);
  border-color: rgba(239,230,212,.95);
  color: var(--sub);
}
.entry-style {
  background: #F6F3FF;
  border-color: #D4C8F0;
  color: #9B6FD8;
}
.entry-reminder {
  background: #F3FBF5;
  border-color: #B8E8C8;
  color: #5FBE63;
}
.settings-entry-icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.settings-entry-icon svg {
  width: 32px;
  height: 32px;
}
.settings-entry-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.settings-entry-title {
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
}
.settings-entry-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 2px;
}
.settings-entry-count {
  flex-shrink: 0;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.settings-entry-arrow {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--sub);
  opacity: .55;
}
.settings-detail-scroll {
  padding-top: 10px;
}
.settings-detail-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.settings-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 7px 8px;
  border-radius: var(--r-sm);
  color: var(--ink-soft);
  font-size: 13px;
}
.settings-back-btn:active {
  background: var(--line);
}
.settings-back-btn svg {
  width: 17px;
  height: 17px;
}
.settings-detail-title {
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
}
.settings-detail-desc {
  color: var(--sub);
  font-size: 12px;
  margin-top: 1px;
}
.settings-detail-card {
  padding: 16px;
  border: 1px solid rgba(232, 218, 197, .9);
  border-radius: var(--r-lg);
  background: rgba(255, 255, 255, .78);
  box-shadow: 0 10px 28px rgba(94, 62, 35, .05);
}
.settings-primary-btn {
  width: auto;
  min-width: 74px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 800;
  flex-shrink: 0;
}
.settings-msg {
  color: var(--honey-deep);
  font-size: 12px;
  margin-top: 8px;
}
.profile-row {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.profile-avatar-wrap {
  position: relative; width: 58px; height: 58px;
  border-radius: 50%; cursor: pointer; flex-shrink: 0;
  overflow: hidden;
}
.profile-avatar-wrap:hover .profile-avatar-overlay {
  opacity: 1;
}
.profile-avatar-img {
  width: 100%; height: 100%; object-fit: cover;
  border-radius: 50%;
}
.profile-avatar {
  width: 58px; height: 58px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; color: #fff; font-weight: 800;
  flex-shrink: 0; box-shadow: 0 4px 12px rgba(0,0,0,.08);
}
.profile-avatar-overlay {
  position: absolute; inset: 0; border-radius: 50%;
  background: rgba(0,0,0,.45); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; opacity: 0; transition: opacity .2s;
}
.profile-copy {
  min-width: 0;
  flex: 1;
}
.profile-name {
  color: var(--ink);
  font-size: 17px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.profile-email {
  color: var(--sub);
  font-size: 12px;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.profile-edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
.profile-input {
  flex: 1;
  min-width: 0;
}
.current-style {
  width: 100%;
  min-height: 60px;
  display: grid;
  grid-template-columns: 44px 1fr 18px;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border: none;
  background: transparent;
  text-align: left;
}
.current-style:hover .current-style-copy div {
  color: var(--honey-deep);
}
.current-style-copy {
  min-width: 0;
}
.current-style-copy div {
  font-weight: 700;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.current-style-copy p {
  color: var(--sub);
  font-size: 12px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.current-style svg {
  width: 18px;
  height: 18px;
  color: var(--hint);
  stroke-width: 2.4;
}
.style-orbs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 12px 0 2px;
  margin-top: 6px;
  border-top: 1px solid var(--line);
}
.style-orb-btn {
  min-width: 76px;
  height: 78px;
  border-radius: 15px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.64);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: var(--ink-soft);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.style-orb-btn.active {
  color: var(--honey-deep);
  border-color: rgba(255,143,110,.45);
  background: var(--honey-soft);
}
.style-orb-btn span {
  max-width: 66px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.style-empty {
  padding-top: 10px;
  margin-top: 8px;
  border-top: 1px solid var(--line);
  color: var(--sub);
  font-size: 13px;
}
.style-msg {
  color: var(--honey-deep);
  font-size: 12px;
  margin-top: 8px;
}
.reminder-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(188px, .88fr) auto;
  gap: 8px;
  margin-bottom: 12px;
}
.reminder-content-input,
.reminder-time-input {
  min-width: 0;
}
.reminder-list {
  border-top: 1px solid var(--line);
}
.reminder-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 54px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}
.reminder-row.expired {
  opacity: .64;
}
.reminder-main {
  min-width: 0;
  flex: 1;
}
.reminder-title-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.reminder-content {
  min-width: 0;
  color: var(--ink);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.reminder-row.expired .reminder-content {
  color: var(--sub);
}
.reminder-time {
  color: var(--sub);
  font-size: 11px;
  margin-top: 3px;
}
.reminder-expired-badge {
  flex-shrink: 0;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(166, 145, 120, .12);
  color: var(--sub);
  font-size: 11px;
  font-weight: 700;
}
.reminder-cancel {
  flex-shrink: 0;
  padding: 4px 8px;
  color: var(--berry);
  font-size: 12px;
}
.reminder-empty {
  color: var(--sub);
  font-size: 13px;
  padding: 12px 0 2px;
}
.logout-btn {
  width: calc(100% - 8px);
  min-height: 46px;
  margin: 18px 4px 0;
  border-radius: var(--r-md);
  border: 1.5px solid rgba(255, 111, 145, .22);
  background: rgba(255, 255, 255, .42);
  color: var(--berry);
  font-size: 14px;
  font-weight: 800;
  text-align: center;
}
.logout-btn:hover {
  background: rgba(255, 111, 145, .08);
}

@media (max-width: 560px) {
  .settings-detail-card {
    padding: 14px;
  }
  .reminder-form {
    grid-template-columns: 1fr;
  }
  .reminder-add {
    width: 100%;
  }
}
</style>
