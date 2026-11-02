<template>
  <div>
    <h1>Scan Management</h1>
    
    <div class="grid">
      <div class="card">
        <h3>Start New Scan</h3>
        <form @submit.prevent="startScan">
          <select v-model="scanData.target_id" required>
            <option value="" disabled>Select Target</option>
            <option v-for="t in targets" :key="t.id" :value="t.id">{{ t.name }} ({{ t.ip_address || t.domain }})</option>
          </select>
          
          <select v-model="scanData.type" required>
            <option value="NETWORK">Network Scan (C++)</option>
            <option value="WEB">Web Scan (Nuclei)</option>
            <option value="CLOUD">Cloud Scan (Prowler)</option>
          </select>
          
          <div v-if="scanData.type === 'NETWORK'">
            <input v-model="scanData.ports" placeholder="Ports (e.g., 22,80,443)" required />
          </div>

          <div v-if="scanData.type === 'CLOUD'">
            <select v-model="scanData.provider">
              <option value="aws">Amazon Web Services (AWS)</option>
              <option value="azure">Microsoft Azure</option>
              <option value="gcp">Google Cloud Platform</option>
            </select>
          </div>

          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? 'Starting...' : 'Launch Scan' }}
          </button>
        </form>
      </div>
      
      <div class="card">
        <h3>Recent Scans</h3>
        <ul class="scan-list">
          <li v-for="scan in scans" :key="scan.id">
            <div class="scan-info">
              <span class="scan-type">{{ scan.scan_type }}</span>
              <span class="scan-id">{{ scan.id.substring(0, 8) }}</span>
            </div>
            <span class="badge" :class="'status-' + scan.status.toLowerCase()">{{ scan.status }}</span>
          </li>
          <li v-if="scans.length === 0">No scans found.</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import apiClient from '../services/api'
import { useScanWebSocket } from '../services/ws'
import { useNotificationStore } from '../stores/notifications'

const targets = ref<any[]>([])
const scans = ref<any[]>([])
const loading = ref(false)
const { lastMessage } = useScanWebSocket()
const notifications = useNotificationStore()

const scanData = ref({
  target_id: '',
  type: 'NETWORK',
  ports: '22,80,443',
  provider: 'aws'
})

async function fetchTargets() {
  const res = await apiClient.get('/targets/')
  targets.value = res.data
}

async function fetchScans() {
  const res = await apiClient.get('/scans/')
  scans.value = res.data
}

async function startScan() {
  loading.value = true
  try {
    let endpoint = '/scans/network'
    let payload: any = { target_id: scanData.value.target_id }

    if (scanData.value.type === 'NETWORK') {
      payload.ports = scanData.value.ports.split(',').map(p => parseInt(p.trim()))
    } else if (scanData.value.type === 'WEB') {
      endpoint = '/scans/web'
    } else if (scanData.value.type === 'CLOUD') {
      endpoint = '/scans/cloud'
      payload.provider = scanData.value.provider
    }
    
    await apiClient.post(endpoint, payload)
    notifications.add('success', 'Scan launched successfully!')
    fetchScans()
  } catch (e: any) {
    notifications.add('error', e.response?.data?.detail || 'Failed to launch scan')
  } finally {
    loading.value = false
  }
}

watch(lastMessage, (msg) => {
  if (msg && msg.type === 'scan_update') {
    fetchScans()
  }
})

onMounted(() => {
  fetchTargets()
  fetchScans()
})
</script>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
.card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
form { display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem; }
select, input { padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; width: 100%; box-sizing: border-box; }
.btn-primary { background: #0056b3; color: white; border: none; padding: 0.75rem; border-radius: 4px; cursor: pointer; font-weight: bold; }
.btn-primary:disabled { background: #ccc; }
.scan-list { list-style: none; padding: 0; margin-top: 1rem; }
.scan-list li { display: flex; justify-content: space-between; align-items: center; padding: 1rem; border-bottom: 1px solid #eee; }
.scan-info { display: flex; flex-direction: column; }
.scan-type { font-weight: bold; font-size: 0.9rem; }
.scan-id { font-family: monospace; color: #666; font-size: 0.8rem; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.status-running { background: #fff3cd; color: #856404; }
.status-completed { background: #d4edda; color: #155724; }
.status-pending { background: #e2e3e5; color: #383d41; }
.status-failed { background: #f8d7da; color: #721c24; }
</style>