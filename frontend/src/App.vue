<template>
  <div id="app">
    <nav v-if="authStore.isAuthenticated">
      <div class="nav-brand">KRAVIGIL</div>
      <div class="nav-links">
        <router-link to="/">Dashboard</router-link>
        <router-link to="/targets">Targets</router-link>
        <router-link to="/assets">Assets</router-link>
        <router-link to="/scans">Scans</router-link>
        <router-link to="/schedules">Schedules</router-link>
        <router-link to="/agents">Agents</router-link>
        <router-link to="/findings">Findings</router-link>
        <router-link to="/risk">Risk</router-link>
        <router-link to="/reports">Reports</router-link>
        <router-link to="/users">Users</router-link>
        <router-link to="/audit-logs">Audit Logs</router-link>
        <router-link to="/settings">Settings</router-link>
      </div>
      <button @click="handleLogout" class="logout-btn">Logout</button>
    </nav>
    <main :class="{ 'full-width': !authStore.isAuthenticated }">
      <router-view />
    </main>
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import Toast from './components/Toast.vue'

const authStore = useAuthStore()
const router = useRouter()

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style>
body { margin: 0; background-color: #f8f9fa; font-family: 'Inter', -apple-system, sans-serif; color: #333; }
#app { display: flex; flex-direction: column; min-height: 100vh; }
nav { background: #1a1a2e; padding: 0 2rem; height: 60px; display: flex; align-items: center; justify-content: space-between; color: white; }
.nav-brand { font-weight: bold; font-size: 1.2rem; letter-spacing: 1px; }
.nav-links { display: flex; gap: 1rem; }
nav a { color: #a0a0b8; text-decoration: none; font-size: 0.9rem; transition: color 0.2s; }
nav a:hover, nav a.router-link-active { color: white; }
.logout-btn { background: transparent; border: 1px solid #a0a0b8; color: #a0a0b8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; transition: all 0.2s; }
.logout-btn:hover { background: #d9534f; border-color: #d9534f; color: white; }
main { flex: 1; padding: 2rem; max-width: 1400px; margin: 0 auto; width: 100%; box-sizing: border-box; }
main.full-width { display: flex; justify-content: center; align-items: center; }
</style>
