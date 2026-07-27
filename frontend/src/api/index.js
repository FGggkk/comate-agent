const BASE = '/api'

function authHeaders() {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

async function post(path, data) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  return res.json()
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  return res.json()
}

async function del(path) {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers: authHeaders() })
  return res.json()
}

async function put(path, data) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  return res.json()
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

// Chat
export function apiSendMessage(message, sessionId) {
  const token = localStorage.getItem('comate_token')
  const body = { message }
  if (sessionId) body.session_id = sessionId
  return fetch('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
}

// Memories
export const apiGetMemories = () => get('/memories')
export const apiUpdateMemory = (id, data) => put(`/memories/${id}`, data)
export const apiDeleteMemory = (id) => del(`/memories/${id}`)
export const apiAddForbidden = (topic, phrase) => post('/memories/forbidden', { topic_summary: topic, original_phrase: phrase })
export const apiRemoveForbidden = (id) => del(`/memories/forbidden/${id}`)
export const apiFulfillAnchor = (id) => post(`/memories/anchor/${id}/fulfill`, {})

// Interview
export const apiStartInterview = (data) => post('/interview/start', data)
export const apiAnswerQuestion = (id, answer) => post(`/interview/${id}/answer`, { answer })
export const apiListInterviews = () => get('/interview')
export const apiNextQuestion = (id) => {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`/api/interview/${id}/next`, { method: 'POST', headers })
}
export const apiEndInterview = (id) => post(`/interview/${id}/end`, {})
export const apiDeleteInterview = (id) => del(`/interview/${id}`)
export const apiRenameInterview = (id, title) => put(`/interview/${id}`, { title })
export const apiEditInterviewAnswer = (sessionId, questionId, newAnswer) => put(`/interview/${sessionId}/answer/${questionId}`, { new_answer: newAnswer })

export const apiAnswerQuestionStream = (id, answer) => {
  const token = localStorage.getItem('comate_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`/api/interview/${id}/answer/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ answer }),
  })
}
export const apiGetReport = (id) => get(`/interview/${id}/report`)

// User Profile
export const apiGetProfile = () => get('/user/me')
export const apiUpdateProfile = (data) => put('/user/me', data)
export const apiUploadAvatar = async (file) => {
  const token = localStorage.getItem('comate_token')
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/user/avatar', {
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
