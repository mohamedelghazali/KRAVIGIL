<template>
  <div class="login-container">
    <div class="login-card">
      <h2>KRAVIGIL Login</h2>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>Email</label>
          <input v-model="email" type="email" required placeholder="admin@kravigil.local" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="password" type="password" required placeholder="••••••••" />
        </div>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Authenticating...' : 'Login' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const authStore = useAuthStore()
const router = useRouter()

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(email.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #1a1a2e; }
.login-card { background: white; padding: 3rem; border-radius: 8px; width: 100%; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
h2 { margin-top: 0; text-align: center; color: #1a1a2e; margin-bottom: 2rem; }
.form-group { margin-bottom: 1.5rem; }
label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: #555; }
input { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; font-size: 1rem; }
input:focus { outline: none; border-color: #0056b3; }
button { width: 100%; padding: 0.85rem; background: #0056b3; color: white; border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; transition: background 0.2s; }
button:hover:not(:disabled) { background: #004494; }
button:disabled { background: #ccc; cursor: not-allowed; }
.error-msg { color: #d9534f; margin-bottom: 1rem; text-align: center; font-size: 0.9rem; }
</style>
