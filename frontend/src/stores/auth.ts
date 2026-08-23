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
