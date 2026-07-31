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
