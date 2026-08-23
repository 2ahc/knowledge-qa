import axios from 'axios'
import { ElMessage } from 'element-plus'

export const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  return data.access_token
}

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error.response?.status
    const original = error.config || {}
    if (status === 401 && !original._retried && localStorage.getItem('refresh_token')) {
      original._retried = true
      try {
        const token = await refreshAccessToken()
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` }
        return http(original)
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (location.pathname !== '/login') location.href = '/login'
        return Promise.reject(error)
      }
    }
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : error.message || '请求失败'
    if (!original._silent) ElMessage.error(msg)
    return Promise.reject(error)
  }
)
