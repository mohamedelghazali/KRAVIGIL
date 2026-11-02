<template>
  <div>
    <h1>Scheduled Scans</h1>
    <div class="action-bar">
      <button @click="showModal = true" class="btn-primary">+ Add Schedule</button>
    </div>
    <div class="table-container">
      <table>
        <thead><tr><th>Name</th><th>Type</th><th>Cron</th><th>Next Run</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          <tr v-for="schedule in schedules" :key="schedule.id">
            <td>{{ schedule.name }}</td><td>{{ schedule.scan_type }}</td>
            <td><code>{{ schedule.cron_expression }}</code></td>
            <td>{{ new Date(schedule.next_run).toLocaleString() }}</td>
            <td><span class="badge" :class="schedule.is_active ? 'status-active' : 'status-inactive'">{{ schedule.is_active ? 'Active' : 'Inactive' }}</span></td>
            <td><button @click="deleteSchedule(schedule.id)" class="btn-danger">Delete</button></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="showModal" class="modal-overlay">
      <div class="modal">
        <h3>Add Scheduled Scan</h3>
        <form @submit.prevent="createSchedule">
          <input v-model="form.name" placeholder="Schedule Name" required />
          <select v-model="form.target_id" required>
            <option value="" disabled>Select Target</option>
            <option v-for="t in targets" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
          <select v-model="form.scan_type" required><option value="NETWORK">Network</option><option value="WEB">Web</option></select>
          <input v-model="form.cron_expression" placeholder="Cron (e.g., 0 2 * * *)" required />
          <div class="modal-actions">
            <button type="button" @click="showModal = false">Cancel</button>
            <button type="submit" class="btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../services/api'
import { useNotificationStore } from '../stores/notifications'
const schedules = ref<any[]>([])
const targets = ref<any[]>([])
const showModal = ref(false)
const form = ref({ name: '', target_id: '', scan_type: 'NETWORK', cron_expression: '0 2 * * *', parameters: { ports: [22, 80, 443] } })
const notifications = useNotificationStore()
async function fetchData() {
  try {
    const [schedRes, targetRes] = await Promise.all([apiClient.get('/schedules/'), apiClient.get('/targets/')])
    schedules.value = schedRes.data
    targets.value = targetRes.data
  } catch (e) { console.error('Failed to fetch data', e) }
}
async function createSchedule() {
  try {
    await apiClient.post('/schedules/', form.value)
    showModal.value = false
    notifications.add('success', 'Schedule created successfully')
    fetchData()
  } catch (e: any) { notifications.add('error', e.response?.data?.detail || 'Failed to create schedule') }
}
async function deleteSchedule(id: string) {
  if (!confirm('Are you sure you want to delete this schedule?')) return
  try {
    await apiClient.delete(`/schedules/${id}`)
    notifications.add('success', 'Schedule deleted')
    fetchData()
  } catch (e) { notifications.add('error', 'Failed to delete schedule') }
}
onMounted(fetchData)
</script>
<style scoped>
.action-bar { margin-bottom: 1rem; }
.btn-primary { background: #0056b3; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
.btn-danger { background: #d9534f; color: white; border: none; padding: 0.25rem 0.5rem; border-radius: 4px; cursor: pointer; }
.table-container { background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; }
.badge { padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
.status-active { background: #d4edda; color: #155724; }
.status-inactive { background: #f8d7da; color: #721c24; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal { background: white; padding: 2rem; border-radius: 8px; width: 400px; }
.modal form { display: flex; flex-direction: column; gap: 1rem; }
.modal input, .modal select { padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem; }
</style>
