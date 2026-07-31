const BASE = '/api/admin'

function authHeaders() {
  const token = localStorage.getItem('admin_token')
  return { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: authHeaders(),
  })
  if (res.status === 401) {
    localStorage.removeItem('admin_token')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }
  const json = await res.json()
  return json
}

export const apiAdminLogin = (email, password) =>
  fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  }).then((r) => r.json())

export const apiAdminMe = () => request('/auth/me')
export const apiDashboard = (days = 7) => request(`/dashboard?days=${days}`)

// 兑换码管理
export const apiAdminCodes = (status = 'all', page = 1, q = '', size = 20) =>
  request(`/codes?status=${status}&page=${page}&size=${size}${q ? `&q=${q}` : ''}`)
export const apiAdminCodesGenerate = (data) =>
  request('/codes/generate', { method: 'POST', body: JSON.stringify(data) })
export const apiAdminCodesDisable = (id) =>
  request(`/codes/${id}/disable`, { method: 'POST', body: '{}' })
export const apiAdminCodesExport = async () => {
  const token = localStorage.getItem('admin_token')
  const res = await fetch(`${BASE}/codes/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) return null
  return res.blob()
}

// 用户管理
export const apiAdminUsers = (q = '', status = 'all', page = 1, size = 20) =>
  request(`/users?q=${q}&status=${status}&page=${page}&size=${size}`)
export const apiAdminUserDetail = (id) => request(`/users/${id}`)
export const apiAdminUserStatus = (id, status) =>
  request(`/users/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) })
export const apiAdminUserBalance = (id, change, note) =>
  request(`/users/${id}/balance`, { method: 'POST', body: JSON.stringify({ change, note }) })

// 计费规则
export const apiAdminBillingRules = () => request('/billing-rules')
export const apiAdminSaveRules = (rules) =>
  request('/billing-rules', { method: 'PUT', body: JSON.stringify({ rules }) })
export const apiAdminSaveSetting = (key, value) =>
  request('/settings', { method: 'PUT', body: JSON.stringify({ key, value }) })

// 数据统计
export const apiAdminStats = (days = 30) => request(`/stats?days=${days}`)

// 系统设置
export const apiAdminListAdmins = () => request('/admins')
export const apiAdminCreateAdmin = (data) => request('/admins', { method: 'POST', body: JSON.stringify(data) })
export const apiAdminAdminStatus = (id, status) => request(`/admins/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) })
export const apiAdminAdminPassword = (id, password) => request(`/admins/${id}/password`, { method: 'POST', body: JSON.stringify({ password }) })
