import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", redirect: "/overview" },
    { path: "/overview", component: () => import("../views/Overview.vue") },
    { path: "/assets", component: () => import("../views/Assets.vue") },
    { path: "/scans", component: () => import("../views/Scans.vue") },
    { path: "/findings", component: () => import("../views/Findings.vue") },
    { path: "/reports", component: () => import("../views/Reports.vue") },
  ],
});

export default router;
