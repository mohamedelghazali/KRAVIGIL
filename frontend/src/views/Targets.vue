<template>
  <div>
    <h1>Targets</h1>
    
    <div class="action-bar">
      <button @click="showCreateModal = true" class="btn-primary">+ Add Target</button>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>IP Address</th>
            <th>Domain</th>
            <th>Authorized</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="target in targets" :key="target.id">
            <td>{{ target.name }}</td>
            <td>{{ target.ip_address || 'N/A' }}</td>
            <td>{{ target.domain || 'N/A' }}</td>
            <td>{{ target.is_authorized ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="startScan(target)" class="btn-sm">Quick Scan</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreateModal" class="modal-overlay">
      <div class="modal">
        <h3>Add New Target</h3>
        <form @submit.prevent="createTarget">
          <input v-model="newTarget.name" placeholder="Target Name" required />
          <input v-model="newTarget.ip_address" placeholder="IP Address (e.g., 192.168.1.1)" />
          <input v-model="newTarget.domain" placeholder="Domain (e.g., example.com)" />
          <label>
            <input type="checkbox" v-model="newTarget.is_authorized" />
            I confirm I have authorization to scan this target
          </label>
          <div class="modal-actions">
            <button type="button" @click="showCreateModal = false">Cancel</button>
            <button type="submit" class="btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const targets = ref<any[]>([])
const showCreateModal = ref(false)
const newTarget = ref({ name: '', ip_address: '', domain: '', is_authorized: false })

async function fetchTargets() {
  const response = await axios.get('/api/v1/targets/')
  targets.value = response.data
}

async function createTarget() {
  try {
    await axios.post('/api/v1/targets/', newTarget.value)
    showCreateModal.value = false
    newTarget.value = { name: '', ip_address: '', domain: '', is_authorized: false }
    fetchTargets()
  } catch (e) {
    alert('Failed to create target')
  }
}

async function startScan(target: any) {
  try {
    await axios.post('/api/v1/scans/network', { target_id: target.id, ports: [22, 80, 443] })
    alert('Scan queued successfully!')
  } catch (e) {
    alert('Failed to start scan')
  }
}

onMounted(fetchTargets)
</script>

<style scoped>
.action-bar { margin-bottom: 1rem; }
.btn-primary { background: #0056b3; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; cursor: pointer; }
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal { background: white; padding: 2rem; border-radius: 8px; width: 400px; }
.modal form { display: flex; flex-direction: column; gap: 1rem; }
.modal input[type="text"], .modal input:not([type]) { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }
</style>
