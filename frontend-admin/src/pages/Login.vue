<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-logo">
        <div class="logo-orb"></div>
        <div>
          <b>伴行</b>
          <small>AI Emotional Companion · 管理后台</small>
        </div>
      </div>
      <p class="login-tip">照料陪伴产品生长的操作台</p>

      <div v-if="error" class="login-err">{{ error }}</div>

      <div class="field">
        <label>邮箱</label>
        <input v-model="email" type="email" placeholder="admin@comate.local" @keydown.enter="submit" />
      </div>
      <div class="field">
        <label>密码</label>
        <input v-model="password" type="password" placeholder="请输入密码" @keydown.enter="submit" />
      </div>
      <button class="btn-gold" style="width:100%;" :disabled="loading" @click="submit">
        {{ loading ? '登录中…' : '进入后台' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '../stores/admin'
import { apiAdminLogin } from '../api'

const router = useRouter()
const store = useAdminStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!email.value.includes('@')) { error.value = '请输入有效的邮箱'; return }
  if (!password.value) { error.value = '请输入密码'; return }
  loading.value = true
  error.value = ''
  try {
    const res = await apiAdminLogin(email.value, password.value)
    if (res.success) {
      store.login(res.token, res.admin)
      router.push('/dashboard')
    } else {
      error.value = res.message || '登录失败'
    }
  } catch {
    error.value = '网络错误，请重试'
  } finally {
    loading.value = false
  }
}
</script>
