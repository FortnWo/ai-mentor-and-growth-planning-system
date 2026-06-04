import { reactive } from 'vue'

import { getMe, login as loginApi } from '../api/auth'
import type { LoginPayload } from '../api/auth'
import type { AdminPermissionKey } from '../constants/adminPermissions'
import type { UserRead } from '../api/user'

const ACCESS_TOKEN_STORAGE_KEY = 'ai_mentor_access_token'
const USER_STORAGE_KEY = 'ai_mentor_user'

type AuthState = {
  initialized: boolean
  token: string | null
  user: UserRead | null
}

const authState = reactive<AuthState>({
  initialized: false,
  token: null,
  user: null,
})

function loadStoredAuthState() {
  if (authState.initialized) {
    return
  }

  const token = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  const userRaw = localStorage.getItem(USER_STORAGE_KEY)

  authState.token = token
  if (userRaw) {
    try {
      authState.user = JSON.parse(userRaw) as UserRead
    } catch {
      authState.user = null
    }
  }

  authState.initialized = true
}

function setAuthSession(token: string, user: UserRead) {
  authState.token = token
  authState.user = user
  authState.initialized = true

  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
}

function clearAuthSession() {
  authState.token = null
  authState.user = null
  authState.initialized = true

  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  localStorage.removeItem(USER_STORAGE_KEY)
}

async function login(payload: LoginPayload): Promise<UserRead> {
  const response = await loginApi(payload)
  setAuthSession(response.access_token, response.user)
  return response.user
}

async function refreshCurrentUser(): Promise<UserRead | null> {
  loadStoredAuthState()

  if (!authState.token) {
    clearAuthSession()
    return null
  }

  try {
    const user = await getMe()
    setAuthSession(authState.token, user)
    return user
  } catch {
    clearAuthSession()
    return null
  }
}

function isAdmin(user: UserRead | null): boolean {
  return user?.role === 'admin'
}

function isFullAdmin(user: UserRead | null): boolean {
  if (!user || user.role !== 'admin') {
    return false
  }

  if (user.is_system_admin) {
    return true
  }

  return !user.admin_permission_level || user.admin_permission_level === 'full'
}

function isLimitedAdmin(user: UserRead | null): boolean {
  return isAdmin(user) && !isFullAdmin(user)
}

function hasAdminPermission(user: UserRead | null, permission: AdminPermissionKey): boolean {
  if (!user || user.role !== 'admin') {
    return false
  }

  if (user.is_system_admin) {
    return true
  }

  if (!user.admin_permission_level || user.admin_permission_level === 'full') {
    return true
  }

  return user.admin_permissions.includes(permission)
}

export {
  authState,
  clearAuthSession,
  hasAdminPermission,
  isAdmin,
  isFullAdmin,
  isLimitedAdmin,
  loadStoredAuthState,
  login,
  refreshCurrentUser,
}