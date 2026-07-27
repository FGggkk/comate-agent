<template>
  <div class="scroll">
    <div class="page-title">设置</div>

    <!-- 个人信息 -->
    <div class="page-card">
      <div class="page-label">个人信息</div>
      <div style="display:flex;align-items:center;gap:14px;">
        <!-- 头像 -->
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
      <div class="style-head">
        <div class="page-label">当前风格</div>
        <button class="style-manage" @click="$emit('open-persona')">管理</button>
      </div>
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
import { ref, computed, onMounted, watch } from 'vue'
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
})
const emit = defineEmits(['open-persona', 'soul-changed'])

const userStore = useUserStore()
const reminders = ref([])
const reminderContent = ref('')
const reminderTime = ref('')
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
  await loadSoulInventory()
})
watch(() => props.refreshKey, loadSoulInventory)

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
  await apiCreateReminder(reminderContent.value, new Date(reminderTime.value).toISOString())
  reminderContent.value = ''; reminderTime.value = ''
  reminders.value = (await apiGetReminders()).reminders || []
}

async function deleteReminder(id) { await apiDeleteReminder(id); reminders.value = (await apiGetReminders()).reminders || [] }

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

function formatTime(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '' }
function logout() { userStore.logout(); window.location.reload() }
</script>

<style scoped>
.profile-avatar-wrap {
  position: relative; width: 50px; height: 50px;
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
  width: 50px; height: 50px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #fff; font-weight: 700;
  flex-shrink: 0; box-shadow: 0 4px 12px rgba(0,0,0,.08);
}
.profile-avatar-overlay {
  position: absolute; inset: 0; border-radius: 50%;
  background: rgba(0,0,0,.45); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; opacity: 0; transition: opacity .2s;
}
.style-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.style-manage {
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--honey-soft);
  color: var(--honey-deep);
  font-size: 12px;
  font-weight: 700;
}
.current-style {
  width: 100%;
  min-height: 58px;
  display: grid;
  grid-template-columns: 44px 1fr 18px;
  align-items: center;
  gap: 10px;
  text-align: left;
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
  padding-top: 10px;
  margin-top: 8px;
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
</style>
