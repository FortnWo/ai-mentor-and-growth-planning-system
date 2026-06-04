import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import type { AdminPermissionKey } from '../constants/adminPermissions'
import {
  authState,
  hasAdminPermission,
  isAdmin,
  isFullAdmin,
  loadStoredAuthState,
  refreshCurrentUser,
} from '../stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
    requiresFullAdmin?: boolean
    adminPermission?: AdminPermissionKey
    guestOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home',
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPasswordView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/ChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/info',
    name: 'Info',
    component: () => import('../views/InfoView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin/users/:userId/usage',
    name: 'AdminUserUsage',
    component: () => import('../views/AdminUserUsageView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, requiresFullAdmin: true },
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('../views/AdminUsersView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, adminPermission: 'user.read' },
  },
  {
    path: '/admin/system',
    name: 'AdminSystem',
    component: () => import('../views/AdminSystemView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, requiresFullAdmin: true },
  },
  {
    path: '/plan',
    name: 'Plan',
    component: () => import('../views/PlanView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/growth',
    name: 'GrowthRecords',
    component: () => import('../views/GrowthRecordsView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to) => {
  loadStoredAuthState()

  if (authState.token && (to.meta.requiresAuth || !authState.user || to.meta.guestOnly)) {
    await refreshCurrentUser()
  }

  if (to.meta.requiresAuth && !authState.token) {
    return {
      path: '/login',
      query: {
        redirect: to.fullPath,
      },
    }
  }

  if (to.meta.requiresAdmin && !isAdmin(authState.user)) {
    return '/chat'
  }

  if (to.meta.requiresFullAdmin && !isFullAdmin(authState.user)) {
    return '/home'
  }

  if (to.meta.adminPermission && !hasAdminPermission(authState.user, to.meta.adminPermission)) {
    return '/home'
  }

  if (to.meta.guestOnly && authState.token) {
    if (isFullAdmin(authState.user)) {
      return '/admin/users'
    }
    return '/home'
  }

  return true
})

export default router
