import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const isAuthenticated = ref(!!token.value)

  async function login(email: string, password: string) {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)

    const response = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })

    token.value = response.data.access_token
    localStorage.setItem('token', response.data.access_token)
    isAuthenticated.value = true
  }

  function logout() {
    token.value = null
    localStorage.removeItem('token')
    isAuthenticated.value = false
  }

  return { token, isAuthenticated, login, logout }
})
