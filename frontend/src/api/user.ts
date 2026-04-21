import apiClient from './client'

export type UserRole = 'admin' | 'user'
export type AdminPermissionLevel = 'full' | 'limited'

export interface UserCreatePayload {
  username: string
  email: string
  password: string
  role: UserRole
  is_active?: boolean
  admin_permission_level?: AdminPermissionLevel
  admin_permissions?: string[]
  admin_expires_at?: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface UserUpdatePayload {
  username?: string
  email?: string
  password?: string
  role?: UserRole
  is_active?: boolean
  admin_permission_level?: AdminPermissionLevel
  admin_permissions?: string[]
  admin_expires_at?: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface AdminPrivilegeUpdatePayload {
  permission_level: AdminPermissionLevel
  permissions: string[]
  expires_at?: string
}

export interface UserRead {
  id: number
  username: string
  email: string
  role: UserRole
  is_active: boolean
  admin_permission_level?: AdminPermissionLevel
  admin_permissions: string[]
  admin_expires_at?: string
  last_login_at?: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
  created_at: string
  updated_at: string
}

export const listUsers = (skip = 0, limit = 100): Promise<UserRead[]> =>
  apiClient
    .get<UserRead[]>('/admin/users', {
      params: { skip, limit },
    })
    .then((response) => response.data)

export const createUser = (payload: UserCreatePayload): Promise<UserRead> =>
  apiClient.post<UserRead>('/admin/users', payload).then((response) => response.data)

export const getUser = (userId: number): Promise<UserRead> =>
  apiClient.get<UserRead>(`/admin/users/${userId}`).then((response) => response.data)

export const updateUser = (userId: number, payload: UserUpdatePayload): Promise<UserRead> =>
  apiClient.put<UserRead>(`/admin/users/${userId}`, payload).then((response) => response.data)

export const grantAdminAccess = (
  userId: number,
  payload: AdminPrivilegeUpdatePayload,
): Promise<UserRead> =>
  apiClient.patch<UserRead>(`/admin/users/${userId}/admin-access`, payload).then((response) => response.data)

export const revokeAdminAccess = (userId: number): Promise<UserRead> =>
  apiClient.delete<UserRead>(`/admin/users/${userId}/admin-access`).then((response) => response.data)

export const deleteUser = (userId: number): Promise<void> =>
  apiClient.delete(`/admin/users/${userId}`).then(() => undefined)
