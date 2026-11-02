<template>
  <div id="app">
    <nav v-if="authStore.isAuthenticated">
      <router-link to="/">Dashboard</router-link>
      <router-link to="/scans">Scans</router-link>
      <router-link to="/findings">Findings</router-link>
      <router-link to="/reports">Reports</router-link>
      <button @click="authStore.logout">Logout</button>
    </nav>
    <main><router-view /></main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from './stores/auth'
const authStore = useAuthStore()
</script>

<style>
#app { font-family: Arial, sans-serif; margin: 0; padding: 0; }
nav { background: #333; padding: 1rem; display: flex; gap: 1rem; }
nav a { color: white; text-decoration: none; }
nav a:hover { text-decoration: underline; }
nav button { margin-left: auto; background: #d9534f; color: white; border: 0; padding: .5rem 1rem; cursor: pointer; }
main { padding: 2rem; }
</style>
