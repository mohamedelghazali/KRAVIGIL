<template>
  <div>
    <h1>Assets Inventory</h1>
    
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>IP Address</th>
            <th>Hostname</th>
            <th>OS Family</th>
            <th>Status</th>
            <th>Target</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="asset in assets" :key="asset.id">
            <td>{{ asset.ip_address }}</td>
            <td>{{ asset.hostname || 'Unknown' }}</td>
            <td>{{ asset.os_family || 'Unknown' }}</td>
            <td>
              <span class="badge" :class="asset.is_active ? 'status-active' : 'status-inactive'">
                {{ asset.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td>{{ asset.target_id.substring(0, 8) }}</td>
          </tr>
          <tr v-if="assets.length === 0">
            <td colspan="5" class="no-data">No assets discovered yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'

const assets = ref<any[]>([])

async function fetchAssets() {
  try {
    const response = await apiClient.get('/assets/')
    assets.value = response.data
  } catch (error) {
    console.error('Failed to fetch assets', error)
  }
}

onMounted(fetchAssets)
</script>

<style scoped>
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.status-active { background: #d4edda; color: #155724; }
.status-inactive { background: #f8d7da; color: #721c24; }
.no-data { text-align: center; padding: 2rem; color: #888; }
</style>
