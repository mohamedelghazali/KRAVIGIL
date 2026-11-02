import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Reports from '../views/Reports.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard, meta: { requiresAuth: true } },
    { path: '/reports', component: Reports, meta: { requiresAuth: true } },
    { path: '/login', component: () => import('../views/Login.vue') }
  ]
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) return '/login'
  if (to.path === '/login' && token) return '/'
  return true
})

export default router
