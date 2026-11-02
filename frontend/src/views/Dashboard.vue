<template>
  <div class="dashboard">
    <h1>Security Overview</h1>
    <div class="connection-status" :class="{ online: isConnected }">
      WebSocket: {{ isConnected ? 'Connected' : 'Disconnected' }}
    </div>

    <div class="stats-grid">
      <div class="stat-card critical">
        <h3>Critical Risks</h3>
        <p class="stat-value">{{ stats.critical }}</p>
      </div>
      <div class="stat-card high">
        <h3>High Risks</h3>
        <p class="stat-value">{{ stats.high }}</p>
      </div>
      <div class="stat-card medium">
        <h3>Medium Risks</h3>
        <p class="stat-value">{{ stats.medium }}</p>
      </div>
      <div class="stat-card low">
        <h3>Low Risks</h3>
        <p class="stat-value">{{ stats.low }}</p>
      </div>
    </div>

    <div class="recent-activity">
      <h2>Real-Time Activity</h2>
      <ul>
        <li v-for="(event, index) in events" :key="index">
          {{ new Date().toLocaleTimeString() }} - {{ event }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'
import { useScanWebSocket } from '../services/ws'

const stats = ref({ critical: 0, high: 0, medium: 0, low: 0 })
const events = ref<string[]>([])
const { connect, isConnected, lastMessage } = useScanWebSocket()

async function fetchStats() {
  try {
    const response = await axios.get('/api/v1/risk/')
    const risks = response.data

    stats.value.critical = risks.filter((r: any) => r.risk_level === 'CRITICAL').length
    stats.value.high = risks.filter((r: any) => r.risk_level === 'HIGH').length
    stats.value.medium = risks.filter((r: any) => r.risk_level === 'MEDIUM').length
    stats.value.low = risks.filter((r: any) => r.risk_level === 'LOW').length
  } catch (error) {
    console.error('Failed to fetch stats', error)
  }
}

watch(lastMessage, (msg) => {
  if (msg && msg.type) {
    events.value.unshift('Event: ' + msg.type + ' - ' + (msg.status || msg.report_id || ''))
    if (events.value.length > 20) events.value.pop()
    if (msg.type === 'correlation_complete') fetchStats()
  }
})

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) connect(token)
  fetchStats()
})
</script>

<style scoped>
.dashboard { padding: 20px; }
.connection-status { padding: 8px; border-radius: 4px; background: #d9534f; color: white; display: inline-block; margin-bottom: 20px; }
.connection-status.online { background: #5cb85c; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
.stat-card { padding: 20px; border-radius: 8px; color: white; text-align: center; }
.stat-card.critical { background: #d9534f; }
.stat-card.high { background: #f0ad4e; }
.stat-card.medium { background: #5bc0de; }
.stat-card.low { background: #5cb85c; }
.stat-value { font-size: 2.5rem; font-weight: bold; margin: 10px 0 0 0; }
.recent-activity { background: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; }
.recent-activity ul { list-style: none; padding: 0; }
.recent-activity li { padding: 8px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 0.9em; }
</style>
