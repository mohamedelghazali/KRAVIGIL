import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const isAuthenticated = ref(!!token.value)

  if (token.value) axios.defaults.headers.common.Authorization = `Bearer ${token.value}`

  async function login(email: string, password: string) {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)
    const response = await axios.post('/api/v1/auth/login', formData)
    token.value = response.data.access_token
    localStorage.setItem('token', response.data.access_token)
    axios.defaults.headers.common.Authorization = `Bearer ${response.data.access_token}`
    isAuthenticated.value = true
  }

  function logout() {
    token.value = null
    localStorage.removeItem('token')
    isAuthenticated.value = false
    delete axios.defaults.headers.common.Authorization
  }

  return { token, isAuthenticated, login, logout }
})
