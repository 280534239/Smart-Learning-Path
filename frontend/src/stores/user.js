import { defineStore } from 'pinia'

import * as authApi from '../api/auth'
import {
  TOKEN_STORAGE_KEY,
  USER_STORAGE_KEY,
} from '../api/request'

const THEME_STORAGE_KEY = 'slp_theme'

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_STORAGE_KEY) || '',
    profile: readStoredUser(),
    theme: localStorage.getItem(THEME_STORAGE_KEY) || 'light',
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    displayName: (state) =>
      state.profile?.nickname ||
      state.profile?.username ||
      '学习者',
    avatarText: (state) => {
      const name =
        state.profile?.nickname ||
        state.profile?.username ||
        '学'
      return name.slice(0, 1).toUpperCase()
    },
  },

  actions: {
    async login(payload) {
      const data = await authApi.login(payload)
      this.token = data.token
      this.profile = data.user
      localStorage.setItem(TOKEN_STORAGE_KEY, data.token)
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user))
      return data
    },

    async register(payload) {
      await authApi.register(payload)
      return this.login({
        username: payload.username,
        password: payload.password,
      })
    },

    async fetchProfile() {
      if (!this.token) return null
      const data = await authApi.getProfile()
      this.profile = data
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data))
      return data
    },

    async updateProfile(payload) {
      const data = await authApi.updateProfile(payload)
      this.profile = data
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data))
      return data
    },

    applyProfilePatch(patch) {
      this.profile = {
        ...(this.profile || {}),
        ...patch,
      }
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(this.profile))
    },

    logout() {
      this.token = ''
      this.profile = null
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      localStorage.removeItem(USER_STORAGE_KEY)
    },

    setTheme(theme) {
      this.theme = theme
      localStorage.setItem(THEME_STORAGE_KEY, theme)
      document.documentElement.classList.toggle('dark', theme === 'dark')
    },

    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },

    initializeTheme() {
      document.documentElement.classList.toggle(
        'dark',
        this.theme === 'dark',
      )
    },
  },
})
