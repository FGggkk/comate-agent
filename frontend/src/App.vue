<template>
  <div class="app-container">
    <LoginForm v-if="!userStore.token" @onboard="onOnboarded" />

    <template v-else>
      <!-- Header -->
      <div class="app-header">
        <div class="brand">
          <div class="companion bob" @click="squishComp">
            <div class="companion-body">
              <span class="companion-eye l"></span>
              <span class="companion-eye r"></span>
              <span class="companion-cheek l"></span>
              <span class="companion-cheek r"></span>
              <span class="companion-mouth"></span>
            </div>
            <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
          </div>
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
        <ChatPage :class="['page', activeTab === 'chat' ? 'active' : '']" @tab-change="activeTab = $event" />
        <MemoryPage :class="['page', activeTab === 'memory' ? 'active' : '']" />
        <InterviewPage :class="['page', activeTab === 'interview' ? 'active' : '']" />
        <SettingsPage :class="['page', activeTab === 'settings' ? 'active' : '']" />
      </div>

      <!-- TabBar -->
      <TabBar :active="activeTab" @tab-change="activeTab = $event" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUserStore } from './stores/user'
import LoginForm from './components/LoginForm.vue'
import TabBar from './components/TabBar.vue'
import ChatPage from './pages/ChatPage.vue'
import MemoryPage from './pages/MemoryPage.vue'
import InterviewPage from './pages/InterviewPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const userStore = useUserStore()
const activeTab = ref('chat')
const userEmail = computed(() => userStore.email || 'U')

function squishComp(e) {
  const el = e.currentTarget
  el.classList.add('squish')
  setTimeout(() => el.classList.remove('squish'), 500)
}

function onOnboarded() {
  // soul selected, nothing extra needed
}
</script>
