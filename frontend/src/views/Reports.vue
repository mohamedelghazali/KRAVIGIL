<template>
  <section>
    <h1>Reports</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading">Loading reports...</p>
    <table v-else>
      <thead><tr><th>Report ID</th><th>Scan ID</th><th>Status</th><th>Size</th><th>Actions</th></tr></thead>
      <tbody>
        <tr v-for="report in reports" :key="report.id">
          <td>{{ report.id.slice(0, 8) }}...</td>
          <td>{{ report.scan_id.slice(0, 8) }}...</td>
          <td>{{ report.status }}</td>
          <td>{{ report.file_size_bytes ? (report.file_size_bytes / 1024).toFixed(2) + ' KB' : 'N/A' }}</td>
          <td><button @click="download(report.id)" :disabled="report.status !== 'READY'">Download PDF</button></td>
        </tr>
        <tr v-if="reports.length === 0"><td colspan="5">No reports found.</td></tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'

interface ReportItem {
  id: string
  scan_id: string
  status: string
  file_size_bytes: number | null
}

const reports = ref<ReportItem[]>([])
const loading = ref(true)
const error = ref('')

async function fetchReports() {
  try {
    const response = await axios.get<ReportItem[]>('/api/v1/reports/')
    reports.value = response.data
  } catch {
    error.value = 'Failed to fetch reports.'
  } finally {
    loading.value = false
  }
}

async function download(id: string) {
  try {
    const response = await axios.get(`/api/v1/reports/${id}/download`)
    window.open(response.data.download_url, '_blank', 'noopener,noreferrer')
  } catch {
    error.value = 'Download failed.'
  }
}

onMounted(fetchReports)
</script>
