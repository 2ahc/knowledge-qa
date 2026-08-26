// axios 实例：统一基础配置 + 请求/响应拦截器。
// 请求拦截：自动携带 access 令牌。
// 响应拦截：401 时用 refresh 令牌无感续期并重放请求；其余错误统一弹提示。
import axios from 'axios'
import { ElMessage } from 'element-plus'

export const http = axios.create({ baseURL: '/api', timeout: 60000 })

// 请求拦截：从本地存储取 access 令牌，加到 Authorization 头
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 用 refresh 令牌换取一对新令牌并落盘
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
    // 401 且还有 refresh 令牌：自动续期一次并重放原请求（_retried 防止无限循环）
    if (status === 401 && !original._retried && localStorage.getItem('refresh_token')) {
      original._retried = true
      try {
        const token = await refreshAccessToken()
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` }
        return http(original)
      } catch {
        // 续期也失败：清空令牌，跳回登录页
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (location.pathname !== '/login') location.href = '/login'
        return Promise.reject(error)
      }
    }
    // 统一错误提示：优先展示后端返回的中文 detail
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : error.message || '请求失败'
    if (!original._silent) ElMessage.error(msg)
    return Promise.reject(error)
  }
)
