<template>
  <div>
    <h1>Risk Assessment</h1>
    
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Finding</th>
            <th>Risk Score</th>
            <th>Risk Level</th>
            <th>CVSS</th>
            <th>EPSS</th>
            <th>KEV</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="risk in risks" :key="risk.id">
            <td>{{ risk.finding_id.substring(0, 8) }}</td>
            <td>{{ risk.calculated_risk_score.toFixed(2) }}</td>
            <td>
              <span class="badge" :class="'risk-' + risk.risk_level.toLowerCase()">{{ risk.risk_level }}</span>
            </td>
            <td>{{ risk.cvss_score || 'N/A' }}</td>
            <td>{{ risk.epss_score ? risk.epss_score.toFixed(4) : 'N/A' }}</td>
            <td>{{ risk.kev_status ? 'YES' : 'NO' }}</td>
          </tr>
          <tr v-if="risks.length === 0">
            <td colspan="6" class="no-data">No risk assessments available.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'

const risks = ref<any[]>([])

async function fetchRisks() {
  try {
    const response = await apiClient.get('/risk/')
    risks.value = response.data
  } catch (error) {
    console.error('Failed to fetch risks', error)
  }
}

onMounted(fetchRisks)
</script>

<style scoped>
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.risk-critical { background: #721c24; color: white; }
.risk-high { background: #f8d7da; color: #721c24; }
.risk-medium { background: #fff3cd; color: #856404; }
.risk-low { background: #d1ecf1; color: #0c5460; }
.risk-info { background: #e2e3e5; color: #383d41; }
.no-data { text-align: center; padding: 2rem; color: #888; }
</style>
