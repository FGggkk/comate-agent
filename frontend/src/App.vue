<template>
  <div class="app-container">
    <LoginForm v-if="!userStore.token" @onboard="onOnboarded" />

    <template v-else>
      <!-- Header -->
      <div class="app-header">
        <div class="brand">
          <button class="header-soul-orb" @click="openPersona" aria-label="打开人设设置">
            <SoulOrb :template="currentSoul || {}" size="sm" />
          </button>
          <div>
            <h1>伴行</h1>
            <small>AI Emotional Companion</small>
          </div>
        </div>
        <span class="badge">v1</span>
        <div class="user-av">{{ userEmail[0] }}</div>
      </div>

      <!-- Pages -->
      <div class="pages">
        <ChatPage
          :class="['page', activeTab === 'chat' ? 'active' : '']"
          :current-soul="currentSoul"
          @tab-change="handleTabChange"
        />
        
        <MemoryPage
          :class="['page', activeTab === 'memory' ? 'active' : '']"
          :active="activeTab === 'memory'"
          :current-soul="currentSoul"
        />
        <InterviewPage :class="['page', activeTab === 'interview' ? 'active' : '']" />
        <WorkbenchPage :class="['page', activeTab === 'workbench' ? 'active' : '']" />

        <SettingsPage
          :class="['page', activeTab === 'settings' ? 'active' : '']"
          :refresh-key="personaRefreshKey"
          @open-persona="openPersona"
          @soul-changed="handleSoulChanged"
        />
        <PersonaPage
          :class="['page', activeTab === 'persona' ? 'active' : '']"
          :refresh-key="personaRefreshKey"
          @back="closePersona"
          @changed="handleSoulChanged"
        />
      </div>

      <!-- TabBar -->
      <TabBar v-if="activeTab !== 'persona'" :active="activeTab" @tab-change="handleTabChange" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useUserStore } from './stores/user'
import { apiGetSoulInventory } from './api/index'
import LoginForm from './components/LoginForm.vue'
import TabBar from './components/TabBar.vue'
import SoulOrb from './components/SoulOrb.vue'
import ChatPage from './pages/ChatPage.vue'
import MemoryPage from './pages/MemoryPage.vue'
import WorkbenchPage from './pages/WorkbenchPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import PersonaPage from './pages/PersonaPage.vue'

const userStore = useUserStore()
const activeTab = ref('chat')
const lastMainTab = ref('chat')
const personaRefreshKey = ref(0)
const currentSoul = ref(null)
const userEmail = computed(() => userStore.email || 'U')

onMounted(loadSoulInventory)
watch(() => userStore.token, loadSoulInventory)

function squishComp(el) {
  if (!el) return
  el.classList.add('squish')
  setTimeout(() => el.classList.remove('squish'), 500)
}

function handleTabChange(tab) {
  activeTab.value = tab
  if (tab !== 'persona') lastMainTab.value = tab
}

function openPersona(e) {
  if (activeTab.value !== 'persona') lastMainTab.value = activeTab.value
  if (e?.currentTarget) squishComp(e.currentTarget)
  personaRefreshKey.value++
  activeTab.value = 'persona'
}

function closePersona() {
  activeTab.value = lastMainTab.value || 'settings'
}

async function loadSoulInventory() {
  if (!userStore.token) {
    currentSoul.value = null
    return
  }
  try {
    const res = await apiGetSoulInventory()
    currentSoul.value = res.current || null
  } catch (e) {
    console.error('load current soul error:', e)
  }
}

async function handleSoulChanged() {
  personaRefreshKey.value++
  await loadSoulInventory()
}

function onOnboarded() {
  loadSoulInventory()
}
</script>

<style scoped>
.header-soul-orb {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  animation: header-orb-bob 3.2s ease-in-out infinite;
}
@keyframes header-orb-bob {
  0%,100% { transform: translateY(0) rotate(-1.5deg); }
  50% { transform: translateY(-5px) rotate(1.5deg); }
}
</style>
