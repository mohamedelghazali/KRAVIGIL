<template>
  <div>
    <h1>Audit Logs</h1>
    
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Action</th>
            <th>Resource</th>
            <th>Actor</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td>{{ new Date(log.timestamp).toLocaleString() }}</td>
            <td>{{ log.action }}</td>
            <td>{{ log.resource_type }} ({{ log.resource_id?.substring(0, 8) }})</td>
            <td>{{ log.actor_id?.substring(0, 8) || 'SYSTEM' }}</td>
            <td><code>{{ JSON.stringify(log.details) }}</code></td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="5" class="no-data">No audit logs available.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'

const logs = ref<any[]>([])

async function fetchLogs() {
  const res = await apiClient.get('/audit-logs/')
  logs.value = res.data
}

onMounted(fetchLogs)
</script>

<style scoped>
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
code { background: #f4f4f4; padding: 0.2rem 0.4rem; border-radius: 3px; font-size: 0.85rem; }
.no-data { text-align: center; padding: 2rem; color: #888; }
</style>
