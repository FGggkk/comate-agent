const BASE = 'http://127.0.0.1:8000/api'

export function apiVoiceRealtimeUrl(sessionId) {
  const wsBase = BASE.replace(/^http/, 'ws')
  return `${wsBase}/voice/realtime?session_id=${encodeURIComponent(sessionId)}`
}

let _refreshing = null

function authHeaders() {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

async function refreshAuth() {
  const refreshToken = localStorage.getItem('comate_refresh_token')
  if (!refreshToken) return false
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) {
      localStorage.removeItem('comate_token')
      localStorage.removeItem('comate_refresh_token')
      localStorage.removeItem('comate_onboarding')
      return false
    }
    const data = await res.json()
    localStorage.setItem('comate_token', data.access_token)
    return true
  } catch {
    return false
  }
}

async function fetchWithAuth(path, options) {
  let res = await fetch(`${BASE}${path}`, options)
  if (res.status === 401 && localStorage.getItem('comate_refresh_token')) {
    if (!_refreshing) _refreshing = refreshAuth()
    const ok = await _refreshing
    _refreshing = null
    if (ok) {
      options.headers['Authorization'] = `Bearer ${localStorage.getItem('comate_token')}`
      res = await fetch(`${BASE}${path}`, options)
    } else {
      localStorage.removeItem('comate_token')
      localStorage.removeItem('comate_refresh_token')
      window.location.reload()
    }
  }
  return res
}

async function post(path, data) {
  const res = await fetchWithAuth(path, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  const json = await res.json()
  return json.success && 'data' in json ? json.data : json
}

async function get(path) {
  const res = await fetchWithAuth(path, { headers: authHeaders() })
  const json = await res.json()
  return json.success && 'data' in json ? json.data : json
}

async function del(path) {
  const res = await fetchWithAuth(path, { method: 'DELETE', headers: authHeaders() })
  const json = await res.json()
  return json.success && 'data' in json ? json.data : json
}

async function put(path, data) {
  const res = await fetchWithAuth(path, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  const json = await res.json()
  return json.success && 'data' in json ? json.data : json
}

// Auth（不需要 token）
export const apiSendCode = (email) => fetch(`${BASE}/auth/send-code`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) }).then(r => r.json())
export const apiRegister = (email, code, password) => fetch(`${BASE}/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, code, password }) }).then(r => r.json())
export const apiLogin = (email, password) => fetch(`${BASE}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }).then(r => r.json())

// Souls（部分需要 token）
export const apiGetTemplates = () => get('/souls/templates')
export const apiRecommend = (answers) => post('/souls/recommend', { answers })
export const apiPreview = (slug) => post('/souls/preview', { slug })
export const apiConfirmSoul = (template_id) => post('/souls/users/me/soul', { template_id })
export const apiGetSoulInventory = () => get('/souls/me/inventory')
export const apiDrawSoul = (exclude_template_id = null) => post('/souls/me/draw', { exclude_template_id: typeof exclude_template_id === 'string' ? exclude_template_id : null })
export const apiInjectSoul = (template_id) => post('/souls/me/inject', { template_id })
export const apiSaveSoulSlot = (template_id, replace_slot_id = null) => post('/souls/me/slots/save', { template_id, replace_slot_id })
export const apiDeleteSoulSlot = (slot_id) => del(`/souls/me/slots/${slot_id}`)

// Chat
export function apiSendMessage(message, sessionId, options = {}) {
  const token = localStorage.getItem('comate_token')
  const body = { message }
  if (sessionId) body.session_id = sessionId
  if (options.persistUserMessage === false) body.persist_user_message = false
  if (options.sourceMessageId) body.source_message_id = options.sourceMessageId
  return fetch(`${BASE}/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
}

// Company knowledge
export const apiGetCompanyKnowledgeTypes = () => get('/company-knowledge/types')
export const apiListCompanyKnowledgeMessages = (sessionId) =>
  get(`/company-knowledge/messages?session_id=${encodeURIComponent(sessionId)}`)
export function apiQueryCompanyKnowledge(data) {
  const token = localStorage.getItem('comate_token')
  return fetch(`${BASE}/company-knowledge/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) },
    body: JSON.stringify(data),
  })
}

// Memories
export const apiGetMemories = () => get('/memories')
export const apiCreateMemory = (data) => post('/memories', data)
export const apiCreateMemoryReminder = (id) => post(`/memories/${id}/reminder`, {})
export const apiUpdateMemory = (id, data) => put(`/memories/${id}`, data)
export const apiDeleteMemory = (id) => del(`/memories/${id}`)
export const apiAddForbidden = (topic, phrase) => post('/memories/forbidden', { topic_summary: topic, original_phrase: phrase })
export const apiRemoveForbidden = (id) => del(`/memories/forbidden/${id}`)
export const apiGetMemoryDocuments = () => get('/memories/documents')
export const apiGetMemoryDocument = (type) => get(`/memories/documents/${type}`)
export const apiRebuildMemoryDocuments = (docType = null, exportToFile = false) => post('/memories/documents/rebuild', { doc_type: docType, export_to_file: exportToFile })
export const apiUpdateMemoryDocument = (type, content, exportToFile = false) => put(`/memories/documents/${type}`, { content, export_to_file: exportToFile })
export const apiExportMemoryDocument = (type) => post(`/memories/documents/${type}/export`, {})
export const apiImportMemoryDocument = (type) => post(`/memories/documents/${type}/import`, {})

// Interview
export const apiStartInterview = (data) => post('/interview/start', data)
export const apiAnswerQuestion = (id, answer) => post(`/interview/${id}/answer`, { answer })
export const apiListInterviews = () => get('/interview')
export const apiNextQuestion = (id) => {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${BASE}/interview/${id}/next`, { method: 'POST', headers })
}
export const apiEndInterview = (id) => post(`/interview/${id}/end`, {})
export const apiDeleteInterview = (id) => del(`/interview/${id}`)
export const apiRenameInterview = (id, title) => put(`/interview/${id}`, { title })
export const apiEditInterviewAnswer = (sessionId, questionId, newAnswer) => put(`/interview/${sessionId}/answer/${questionId}`, { new_answer: newAnswer })

export const apiAnswerQuestionStream = (id, answer) => {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${BASE}/interview/${id}/answer/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ answer }),
  })
}
export const apiGetReport = (id) => get(`/interview/${id}/report`)
export const apiGetHint = (id, question) => post(`/interview/${id}/hint`, { question })
export const apiRerollQuestion = (id) => post(`/interview/${id}/reroll`, {})

// Finance
export const apiCreateRecord = (data) => post('/finance/record', data)
export const apiGetRecords = (year, month) => get(`/finance/records?year=${year}&month=${month}`)
export const apiUpdateRecord = (id, data) => put(`/finance/record/${id}`, data)
export const apiDeleteRecord = (id) => del(`/finance/record/${id}`)
export const apiGetSummary = (year, month) => get(`/finance/summary?year=${year}&month=${month}`)
export const apiAiParse = (text) => post('/finance/ai-parse', { text })
export const apiGetFinanceMessages = () => get('/finance/messages')
export const apiSaveFinanceMessage = (role, content, recordId) => post('/finance/messages', { role, content, record_id: recordId })

// Travel
export const apiGenerateTravelPlan = (data) => post('/travel/plan', data)
export const apiGetTravelPlans = () => get('/travel/plans')
export const apiGetTravelPlan = (id) => get(`/travel/plan/${id}`)
export const apiUpdateTravelPlan = (id, data) => put(`/travel/plan/${id}`, data)
export const apiDeleteTravelPlan = (id) => del(`/travel/plan/${id}`)
export const apiRegenerateTravelDay = (id, dayNumber) => post(`/travel/plan/${id}/regenerate-day`, { day_number: dayNumber })

// Shopping
export const apiGenerateShoppingPlan = (demand) => post('/shopping/generate', { demand })
export const apiGetShoppingProgress = (taskId) => `/api/shopping/progress/${taskId}`
export const apiSaveShoppingPlan = (taskId) => post('/shopping/save', { task_id: taskId })
export const apiGetShoppingHistory = () => get('/shopping/history')
export const apiGetShoppingPlan = (id) => get(`/shopping/plan/${id}`)
export const apiDeleteShoppingPlan = (id) => del(`/shopping/plan/${id}`)
export const apiFavoriteShoppingPlan = (id) => post(`/shopping/plan/${id}/favorite`, {})

// User Profile
export const apiGetProfile = () => get('/user/me')
export const apiUpdateProfile = (data) => put('/user/me', data)
export const apiUploadAvatar = async (file) => {
  const token = localStorage.getItem('comate_token')
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/user/avatar`, {
    method: 'POST',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body: form,
  })
  return res.json()
}

// Sessions
export const apiListSessions = () => get('/sessions')
export const apiCreateSession = (title) => post('/sessions', { title })
export const apiUpdateSession = (id, data) => put(`/sessions/${id}`, data)
export const apiDeleteSession = (id) => del(`/sessions/${id}`)
export const apiGetMessages = (sessionId) => get(`/sessions/${sessionId}/messages`)

// Messages
export const apiEditMessage = (id, content) => put(`/messages/${id}`, { content })
export const apiDeleteMessage = (id) => del(`/messages/${id}`)

// Reminders
export const apiCreateReminder = (content, remind_at) => post('/reminders', { content, remind_at })
export const apiGetReminders = () => get('/reminders')
export const apiDeleteReminder = (id) => del(`/reminders/${id}`)

// Billing（积分）
export const apiRedeemCode = (code) => post('/billing/redeem', { code })
export const apiGetBalance = () => get('/billing/balance')
export const apiGetTransactions = (page = 1) => get(`/billing/transactions?page=${page}&size=20`)
