<template>
  <div>
    <h1>User Management</h1>
    
    <div class="action-bar">
      <button @click="showModal = true" class="btn-primary">+ Add User</button>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.email }}</td>
            <td>
              <select :value="user.role" @change="updateRole(user.id, $event.target.value)">
                <option value="admin">Admin</option>
                <option value="analyst">Analyst</option>
                <option value="viewer">Viewer</option>
              </select>
            </td>
            <td>
              <span class="badge" :class="user.is_active ? 'status-active' : 'status-inactive'">
                {{ user.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td>
              <button v-if="user.is_active" @click="deactivateUser(user.id)" class="btn-danger">Deactivate</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showModal" class="modal-overlay">
      <div class="modal">
        <h3>Add New User</h3>
        <form @submit.prevent="createUser">
          <input v-model="form.email" type="email" placeholder="Email" required />
          <input v-model="form.password" type="password" placeholder="Password (min 12 chars, 1 upper, 1 lower, 1 digit)" required />
          <select v-model="form.role" required>
            <option value="analyst">Analyst</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </select>
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

const users = ref<any[]>([])
const showModal = ref(false)
const form = ref({ email: '', password: '', role: 'analyst' })
const notifications = useNotificationStore()

async function fetchUsers() {
  const res = await apiClient.get('/users/')
  users.value = res.data
}

async function createUser() {
  try {
    await apiClient.post('/users/', form.value)
    showModal.value = false
    form.value = { email: '', password: '', role: 'analyst' }
    notifications.add('success', 'User created successfully')
    fetchUsers()
  } catch (e: any) {
    notifications.add('error', e.response?.data?.detail || 'Failed to create user')
  }
}

async function updateRole(id: string, role: string) {
  try {
    await apiClient.put(`/users/${id}/role`, { role })
    notifications.add('success', 'User role updated')
  } catch (e) {
    notifications.add('error', 'Failed to update role')
    fetchUsers()
  }
}

async function deactivateUser(id: string) {
  if (!confirm('Are you sure you want to deactivate this user?')) return
  try {
    await apiClient.delete(`/users/${id}`)
    notifications.add('success', 'User deactivated')
    fetchUsers()
  } catch (e) {
    notifications.add('error', 'Failed to deactivate user')
  }
}

onMounted(fetchUsers)
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
