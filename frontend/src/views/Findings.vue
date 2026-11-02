<template>
  <div>
    <h1>Vulnerability Findings</h1>
    
    <div class="filters">
      <select v-model="selectedSeverity" @change="fetchFindings">
        <option value="">All Severities</option>
        <option value="CRITICAL">Critical</option>
        <option value="HIGH">High</option>
        <option value="MEDIUM">Medium</option>
        <option value="LOW">Low</option>
      </select>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Severity</th>
            <th>Confidence</th>
            <th>CVE</th>
            <th>First Seen</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="finding in findings" :key="finding.id">
            <td>{{ finding.title }}</td>
            <td><span class="badge" :class="'sev-' + finding.severity.toLowerCase()">{{ finding.severity }}</span></td>
            <td>{{ finding.confidence }}</td>
            <td>{{ finding.cve_id || 'N/A' }}</td>
            <td>{{ new Date(finding.first_seen).toLocaleString() }}</td>
            <td>{{ finding.validation_status }}</td>
          </tr>
          <tr v-if="findings.length === 0">
            <td colspan="6" class="no-data">No findings discovered yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const findings = ref<any[]>([])
const selectedSeverity = ref('')

async function fetchFindings() {
  try {
    let url = '/api/v1/findings/'
    if (selectedSeverity.value) {
      url += `?severity=${selectedSeverity.value}`
    }
    const response = await axios.get(url)
    findings.value = response.data
  } catch (error) {
    console.error('Failed to fetch findings', error)
  }
}

onMounted(fetchFindings)
</script>

<style scoped>
.filters { margin-bottom: 1rem; }
select { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; color: #555; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.sev-critical { background: #f8d7da; color: #721c24; }
.sev-high { background: #fff3cd; color: #856404; }
.sev-medium { background: #d1ecf1; color: #0c5460; }
.sev-low { background: #d4edda; color: #155724; }
.no-data { text-align: center; padding: 2rem; color: #888; }
</style>
