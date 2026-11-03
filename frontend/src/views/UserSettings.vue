<template>
  <div class="settings-container">
    <h1>User Settings</h1>
    <div class="grid">
      <div class="card">
        <h3>Change Password</h3>
        <form @submit.prevent="changePassword">
          <input v-model="pwdForm.current_password" type="password" placeholder="Current Password" required autocomplete="current-password" />
          <input v-model="pwdForm.new_password" type="password" placeholder="New Password (min 12 chars)" required minlength="12" autocomplete="new-password" />
          <button type="submit" class="btn-primary" :disabled="saving">{{ saving ? 'Updating…' : 'Update Password' }}</button>
        </form>
      </div>
      <div class="card">
        <h3>MFA Status</h3>
        <p v-if="mfaEnabled" class="success">✓ MFA is enabled</p>
        <p v-else class="warning">⚠ MFA is not enabled</p>
        <router-link to="/mfa-setup" class="btn-secondary">Configure MFA</router-link>
      </div>
      <div class="card full-width">
        <h3>Active Sessions</h3>
        <router-link to="/sessions" class="btn-secondary">View & Revoke Sessions</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'
import { useNotificationStore } from '../stores/notifications'
import { useAuthStore } from '../stores/auth'

const pwdForm = ref({ current_password: '', new_password: '' })
const mfaEnabled = ref(false)
const saving = ref(false)
const notifications = useNotificationStore()
const authStore = useAuthStore()

async function changePassword() {
  if (pwdForm.value.new_password.length < 12) {
    notifications.add('error', 'New password must be at least 12 characters')
    return
  }
  saving.value = true
  try {
    await apiClient.post('/auth/change-password', pwdForm.value)
    notifications.add('success', 'Password changed. Please log in again.')
    pwdForm.value = { current_password: '', new_password: '' }
    window.setTimeout(() => {
      authStore.logout()
      window.location.href = '/login'
    }, 1500)
  } catch (e: any) {
    notifications.add('error', e.response?.data?.detail || 'Failed to change password')
  } finally {
    saving.value = false
  }
}

async function fetchMFAStatus() {
  try {
    const res = await apiClient.get('/users/me')
    mfaEnabled.value = Boolean(res.data.is_mfa_enabled)
  } catch (e) {
    console.error('Failed to fetch MFA status', e)
  }
}

onMounted(fetchMFAStatus)
</script>

<style scoped>
.settings-container { max-width: 1000px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2rem; }
.card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.full-width { grid-column: 1 / -1; }
form { display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem; }
input { padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; }
.btn-primary { background: #0056b3; color: white; border: none; padding: 0.75rem; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled { opacity: .6; cursor: wait; }
.btn-secondary { display: inline-block; background: #6c757d; color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; text-align: center; margin-top: 0.5rem; }
.success { color: #25833a; font-weight: bold; }
.warning { color: #a86b00; font-weight: bold; }
@media (max-width: 700px) { .grid { grid-template-columns: 1fr; } .full-width { grid-column: auto; } }
</style>
