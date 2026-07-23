import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('comate_token') || '')
  const email = ref(localStorage.getItem('comate_email') || '')
  const onboardingStatus = ref(localStorage.getItem('comate_onboarding') || 'none')

  const isLoggedIn = computed(() => !!token.value)
  const needsOnboarding = computed(() => onboardingStatus.value !== 'completed')

  function login(t, e, status) {
    token.value = t
    email.value = e
    onboardingStatus.value = status || 'none'
    localStorage.setItem('comate_token', t)
    localStorage.setItem('comate_email', e)
    localStorage.setItem('comate_onboarding', onboardingStatus.value)
  }

  function completeOnboarding() {
    onboardingStatus.value = 'completed'
    localStorage.setItem('comate_onboarding', 'completed')
  }

  function logout() {
    token.value = ''
    email.value = ''
    onboardingStatus.value = 'none'
    localStorage.removeItem('comate_token')
    localStorage.removeItem('comate_email')
    localStorage.removeItem('comate_onboarding')
  }

  return { token, email, onboardingStatus, isLoggedIn, needsOnboarding, login, completeOnboarding, logout }
})
