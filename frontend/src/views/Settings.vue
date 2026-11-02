<template>
  <div>
    <h1>Tenant Settings</h1>
    
    <div class="grid">
      <div class="card">
        <h3>API Keys</h3>
        <button @click="generateApiKey" class="btn-primary">Generate New Key</button>
        <ul class="key-list">
          <li v-for="key in apiKeys" :key="key.id">
            <span>{{ key.name }} ({{ key.prefix }}...)</span>
            <button @click="revokeApiKey(key.id)" class="btn-danger">Revoke</button>
          </li>
        </ul>
        <div v-if="newApiKey" class="new-key-alert">
          <p>Copy this key now. You won't see it again:</p>
          <code>{{ newApiKey }}</code>
        </div>
      </div>

      <div class="card">
        <h3>Webhooks</h3>
        <form @submit.prevent="createWebhook" class="webhook-form">
          <input v-model="webhookForm.name" placeholder="Webhook Name" required />
          <input v-model="webhookForm.url" placeholder="https://your-server.com/hook" required />
          <input v-model="webhookForm.secret" placeholder="Secret (for HMAC signing)" required />
          <select v-model="webhookForm.events" multiple required>
            <option value="scan.completed">Scan Completed</option>
            <option value="scan.failed">Scan Failed</option>
            <option value="correlation.completed">Correlation Completed</option>
          </select>
          <button type="submit" class="btn-primary">Add Webhook</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'

const apiKeys = ref<any[]>([])
const newApiKey = ref<string | null>(null)
const webhookForm = ref({ name: '', url: '', secret: '', events: [] as string[] })

async function fetchApiKeys() {
  const res = await apiClient.get('/api-keys/')
  apiKeys.value = res.data
}

async function generateApiKey() {
  const res = await apiClient.post('/api-keys/', { name: `Key-${Date.now()}`, expires_in_days: 365 })
  newApiKey.value = res.data.raw_key
  fetchApiKeys()
}

async function revokeApiKey(id: string) {
  await apiClient.delete(`/api-keys/${id}`)
  fetchApiKeys()
}

async function createWebhook() {
  try {
    await apiClient.post('/webhooks/', webhookForm.value)
    alert('Webhook created successfully')
    webhookForm.value = { name: '', url: '', secret: '', events: [] }
  } catch (e) {
    alert('Failed to create webhook')
  }
}

onMounted(fetchApiKeys)
</script>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
.card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.btn-primary { background: #0056b3; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
.btn-danger { background: #d9534f; color: white; border: none; padding: 0.25rem 0.5rem; border-radius: 4px; cursor: pointer; margin-left: 1rem; }
.key-list { list-style: none; padding: 0; margin-top: 1rem; }
.key-list li { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #eee; align-items: center; }
.new-key-alert { background: #d4edda; padding: 1rem; border-radius: 4px; margin-top: 1rem; word-break: break-all; }
.webhook-form { display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem; }
.webhook-form input, .webhook-form select { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
</style>
