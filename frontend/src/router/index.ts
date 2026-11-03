import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Reports from '../views/Reports.vue'
import Login from '../views/Login.vue'
import Findings from '../views/Findings.vue'
import Scans from '../views/Scans.vue'
import Targets from '../views/Targets.vue'
import Assets from '../views/Assets.vue'
import Risk from '../views/Risk.vue'
import Settings from '../views/Settings.vue'
import UserManagement from '../views/UserManagement.vue'
import AuditLogs from '../views/AuditLogs.vue'
import Schedules from '../views/Schedules.vue'
import Agents from '../views/Agents.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { requiresAuth: false } },
    { path: '/', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/targets', component: Targets, meta: { requiresAuth: true } },
    { path: '/assets', component: Assets, meta: { requiresAuth: true } },
    { path: '/scans', component: Scans, meta: { requiresAuth: true } },
    { path: '/schedules', component: Schedules, meta: { requiresAuth: true } },
    { path: '/agents', component: Agents, meta: { requiresAuth: true } },
    { path: '/findings', component: Findings, meta: { requiresAuth: true } },
    { path: '/risk', component: Risk, meta: { requiresAuth: true } },
    { path: '/reports', component: Reports, meta: { requiresAuth: true } },
    { path: '/users', component: UserManagement, meta: { requiresAuth: true, requiresAdmin: true } },
    { path: '/audit-logs', component: AuditLogs, meta: { requiresAuth: true, requiresAdmin: true } },
    { path: '/settings', component: Settings, meta: { requiresAuth: true } }
  ]
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
