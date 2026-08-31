// 认证状态（Pinia）：当前用户 + 登录/登出动作。
// 令牌存 localStorage，页面刷新后依然保持登录。
import { defineStore } from 'pinia'
import { http } from '../api/http'
import type { User } from '../api/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
  }),
  getters: {
    isLoggedIn: () => !!localStorage.getItem('access_token'),
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await http.post('/auth/login', { username, password })
      // 双令牌落盘：access 随请求携带，refresh 过期后无感续期
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      await this.fetchMe()
    },
    // 注册：后端只允许创建普通用户，成功即签发双令牌（无需再登录一次）
    async register(username: string, password: string, displayName: string) {
      const { data } = await http.post('/auth/register', {
        username,
        password,
        display_name: displayName || undefined,
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      await this.fetchMe()
    },
    async fetchMe() {
      const { data } = await http.get('/auth/me')
      this.user = data
    },
    logout() {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      this.user = null
    },
  },
})
