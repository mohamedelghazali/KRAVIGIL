<template>
  <div class="toast-container">
    <div v-for="n in notifications" :key="n.id" class="toast" :class="'toast-' + n.type">
      {{ n.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useNotificationStore } from '../stores/notifications'
const { notifications } = useNotificationStore()
</script>

<style scoped>
.toast-container { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 10px; z-index: 9999; }
.toast { padding: 1rem; border-radius: 4px; color: white; font-weight: 500; min-width: 250px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); animation: slideIn 0.3s ease-out; }
.toast-success { background: #5cb85c; }
.toast-error { background: #d9534f; }
.toast-info { background: #5bc0de; }
.toast-warning { background: #f0ad4e; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
</style>
