<template>
  <div>
    <h1>Agents</h1>
    <p class="subtitle">Manage on-premises scanning agents.</p>
    <div class="table-container">
      <table>
        <thead><tr><th>Name</th><th>Status</th><th>Last Heartbeat</th><th>Version</th><th>IP Address</th></tr></thead>
        <tbody>
          <tr v-for="agent in agents" :key="agent.id">
            <td>{{ agent.name }}</td>
            <td><span class="badge" :class="agent.status === 'ONLINE' ? 'status-active' : 'status-inactive'">{{ agent.status }}</span></td>
            <td>{{ agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleString() : 'Never' }}</td>
            <td>{{ agent.version || 'N/A' }}</td>
            <td>{{ agent.ip_address || 'N/A' }}</td>
          </tr>
          <tr v-if="agents.length === 0"><td colspan="5" class="no-data">No agents enrolled yet.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'

const agents = ref<any[]>([])

async function fetchAgents() {
  try {
    const res = await apiClient.get('/agents/')
    agents.value = res.data
  } catch (e) {
    console.error('Failed to fetch agents', e)
  }
}

onMounted(fetchAgents)
</script>

<style scoped>
.subtitle { color: #666; margin-bottom: 1.5rem; }
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.status-active { background: #d4edda; color: #155724; }
.status-inactive { background: #f8d7da; color: #721c24; }
.no-data { text-align: center; padding: 2rem; color: #888; }
</style>
