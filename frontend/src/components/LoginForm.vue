<template>
  <div class="login-page">
    <div style="text-align:center;margin-bottom:28px;">
      <div class="companion hero bob" style="--s:72px;margin:0 auto 8px;">
        <div class="companion-body">
          <span class="companion-eye l"></span>
          <span class="companion-eye r"></span>
          <span class="companion-cheek l"></span>
          <span class="companion-cheek r"></span>
          <span class="companion-mouth"></span>
        </div>
        <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
      </div>
      <h1 style="font-size:24px;font-weight:700;color:var(--ink);">伴行</h1>
      <p style="font-size:14px;color:var(--sub);margin-top:2px;">你的 AI 陪伴伙伴</p>
    </div>

    <div class="login-box">
      <div v-if="mode === 'login'">
        <label class="form-label">邮箱</label>
        <input v-model="email" type="email" placeholder="请输入邮箱" class="form-input" />
        <label class="form-label" style="margin-top:14px;">密码</label>
        <input v-model="password" type="password" placeholder="请输入密码" class="form-input" />
        <button @click="handleLogin" :disabled="loading" class="btn-primary" style="margin-top:18px;">
          {{ loading ? '登录中...' : '登录' }}
        </button>
        <p style="text-align:center;margin-top:14px;">
          <button @click="mode = 'register'" class="btn-text">没有账号？去注册</button>
        </p>
      </div>

      <div v-else-if="mode === 'register' && step === 'send'">
        <label class="form-label">邮箱</label>
        <input v-model="email" type="email" placeholder="请输入邮箱" class="form-input" />
        <button @click="sendCode" :disabled="sending" class="btn-primary" style="margin-top:16px;">
          {{ sending ? '发送中...' : '发送验证码' }}
        </button>
        <p style="text-align:center;margin-top:14px;">
          <button @click="mode = 'login'" class="btn-text">已有账号？去登录</button>
        </p>
      </div>

      <div v-else>
        <label class="form-label">验证码</label>
        <p style="font-size:13px;color:var(--sub);margin-bottom:8px;">已发送至 {{ email }}</p>
        <input v-model="code" type="text" maxlength="6" placeholder="6 位验证码" class="form-input" style="text-align:center;font-size:20px;letter-spacing:6px;" />
        <label class="form-label" style="margin-top:14px;">设置密码（至少 6 位）</label>
        <input v-model="password" type="password" placeholder="请输入密码" class="form-input" />
        <button @click="handleRegister" :disabled="registering" class="btn-primary" style="margin-top:16px;">
          {{ registering ? '注册中...' : '完成注册' }}
        </button>
        <button @click="step = 'send'" class="btn-text" style="display:block;width:100%;text-align:center;margin-top:10px;">← 重新输入</button>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUserStore } from '../stores/user'
import { apiSendCode, apiRegister, apiLogin } from '../api/index'

const emit = defineEmits(['onboard'])
const userStore = useUserStore()
const mode = ref('login')
const step = ref('send')
const email = ref('')
const code = ref('')
const password = ref('')
const sending = ref(false)
const loading = ref(false)
const registering = ref(false)
const error = ref('')

async function sendCode() {
  if (!email.value.includes('@')) { error.value = '请输入有效的邮箱地址'; return }
  sending.value = true; error.value = ''
  try {
    const res = await apiSendCode(email.value)
    res.success ? (step.value = 'code') : (error.value = res.message || '发送失败')
  } catch { error.value = '网络错误，请重试' } finally { sending.value = false }
}

async function handleRegister() {
  if (code.value.length !== 6) { error.value = '请输入 6 位验证码'; return }
  if (password.value.length < 6) { error.value = '密码至少 6 位'; return }
  registering.value = true; error.value = ''
  try {
    const res = await apiRegister(email.value, code.value, password.value)
    if (res.success) { userStore.login(res.token, email.value, res.onboarding_status, res.refresh_token); if (res.is_new_user) emit('onboard') }
    else error.value = res.message || '注册失败'
  } catch { error.value = '网络错误，请重试' } finally { registering.value = false }
}

async function handleLogin() {
  if (!email.value.includes('@')) { error.value = '请输入有效的邮箱地址'; return }
  if (!password.value) { error.value = '请输入密码'; return }
  loading.value = true; error.value = ''
  try {
    const res = await apiLogin(email.value, password.value)
    res.success ? userStore.login(res.token, email.value, res.onboarding_status, res.refresh_token) : (error.value = res.message || '登录失败')
  } catch { error.value = '网络错误，请重试' } finally { loading.value = false }
}
</script>
