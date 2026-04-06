import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// --- Auth ---
export const authApi = {
  login: (data: { username: string; password: string }) => api.post('/auth/login', data),
  register: (data: { username: string; email: string; password: string }) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

// --- Domains ---
export const domainsApi = {
  list: (params?: Record<string, any>) => api.get('/domains', { params }),
  create: (data: any) => api.post('/domains', data),
  get: (id: string) => api.get(`/domains/${id}`),
  update: (id: string, data: any) => api.put(`/domains/${id}`, data),
  delete: (id: string) => api.delete(`/domains/${id}`),
  results: (id: string) => api.get(`/domains/${id}/results`),
  history: (id: string, params?: Record<string, any>) => api.get(`/domains/${id}/history`, { params }),
  exportCsv: () => api.get('/domains/export/csv', { responseType: 'blob' }),
}

// --- Jobs ---
export const jobsApi = {
  check: (data: { domain_id: string; vendor?: string }) => api.post('/jobs/check', data),
  reputation: (data: { domain_id: string }) => api.post('/jobs/reputation', data),
  submit: (data: { domain_id: string; vendor?: string }) => api.post('/jobs/submit', data),
  bulkCheck: (vendor?: string) => api.post('/jobs/bulk-check', null, { params: { vendor } }),
  get: (id: string) => api.get(`/jobs/${id}`),
  list: (params?: Record<string, any>) => api.get('/jobs', { params }),
}

// --- Vendors ---
export const vendorsApi = {
  list: () => api.get('/vendors'),
}

// --- Dashboard ---
export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
  matrix: (params?: Record<string, any>) => api.get('/dashboard/matrix', { params }),
}
