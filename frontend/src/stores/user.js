import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('comate_token') || '')
  const email = ref(localStorage.getItem('comate_email') || '')
  const nickname = ref(localStorage.getItem('comate_nickname') || '')
  const avatarUrl = ref(localStorage.getItem('comate_avatar_url') || '')
  const onboardingStatus = ref(localStorage.getItem('comate_onboarding') || 'none')

  const isLoggedIn = computed(() => !!token.value)
  const needsOnboarding = computed(() => onboardingStatus.value !== 'completed')

  const displayName = computed(() => nickname.value || email.value.split('@')[0])

  function login(t, e, status) {
    token.value = t
    email.value = e
    onboardingStatus.value = status || 'none'
    localStorage.setItem('comate_token', t)
    localStorage.setItem('comate_email', e)
    localStorage.setItem('comate_onboarding', onboardingStatus.value)
  }

  function setProfile(nick, ava) {
    nickname.value = nick || ''
    avatarUrl.value = ava || ''
    localStorage.setItem('comate_nickname', nickname.value)
    localStorage.setItem('comate_avatar_url', avatarUrl.value)
  }

  function completeOnboarding() {
    onboardingStatus.value = 'completed'
    localStorage.setItem('comate_onboarding', 'completed')
  }

  function logout() {
    token.value = ''
    email.value = ''
    nickname.value = ''
    avatarUrl.value = ''
    onboardingStatus.value = 'none'
    localStorage.removeItem('comate_token')
    localStorage.removeItem('comate_email')
    localStorage.removeItem('comate_nickname')
    localStorage.removeItem('comate_avatar_url')
    localStorage.removeItem('comate_onboarding')
  }

  return { token, email, nickname, avatarUrl, onboardingStatus, isLoggedIn, needsOnboarding, displayName, login, setProfile, completeOnboarding, logout }
})
