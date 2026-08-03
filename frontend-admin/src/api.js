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

// 公司知识库
export const apiAdminCompanyKnowledgeTypes = () => request('/company-knowledge/types')
export const apiAdminCompanyKnowledgeSources = (knowledgeType = 'policy', status = 'all', page = 1, size = 20) =>
  request(`/company-knowledge/sources?knowledge_type=${encodeURIComponent(knowledgeType)}&status=${status}&page=${page}&size=${size}`)
export const apiAdminCompanyKnowledgeSource = (id) => request(`/company-knowledge/sources/${id}`)
export const apiAdminCompanyKnowledgePublish = (id) => request(`/company-knowledge/sources/${id}/publish`, { method: 'POST', body: '{}' })
export const apiAdminCompanyKnowledgeArchive = (id) => request(`/company-knowledge/sources/${id}/archive`, { method: 'POST', body: '{}' })
export const apiAdminCompanyKnowledgeReindex = (id) => request(`/company-knowledge/sources/${id}/reindex`, { method: 'POST', body: '{}' })
export const apiAdminCompanyKnowledgeJobs = (page = 1, size = 30) =>
  request(`/company-knowledge/jobs?page=${page}&size=${size}`)
export const apiAdminCompanyKnowledgeUpload = async (data) => {
  const token = localStorage.getItem('admin_token')
  const form = new FormData()
  form.append('file', data.file)
  form.append('title', data.title)
  form.append('version', data.version)
  form.append('effective_at', data.effective_at)
  if (data.expires_at) form.append('expires_at', data.expires_at)
  form.append('category', data.category || '')
  form.append('knowledge_type', data.knowledge_type || 'policy')
  const res = await fetch(`${BASE}/company-knowledge/sources`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (res.status === 401) {
    localStorage.removeItem('admin_token')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }
  return res.json()
}

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
export const apiAdminUserSlotCapacity = (id, capacity) =>
  request(`/users/${id}/slot_capacity`, { method: 'POST', body: JSON.stringify({ capacity }) })

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

// 角色管理
export const apiAdminSouls = (status = 'all', page = 1) => request(`/souls?status=${status}&page=${page}&size=20`)
export const apiAdminCreateSoul = (data) => request('/souls', { method: 'POST', body: JSON.stringify(data) })
export const apiAdminUpdateSoul = (id, data) => request(`/souls/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const apiAdminSoulStatus = (id, status) => request(`/souls/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) })
export const apiAdminImportSoul = (text) => request('/souls/import', { method: 'POST', body: JSON.stringify({ text }) })
export const apiAdminSoulsUpload = async (file) => {
  const token = localStorage.getItem('admin_token')
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/souls/upload`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd })
  return res.json()
}
