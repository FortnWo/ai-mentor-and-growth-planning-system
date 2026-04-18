import apiClient from './client'

export interface UserCreatePayload {
  username: string
  email: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface UserUpdatePayload {
  username?: string
  email?: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface UserRead {
  id: number
  username: string
  email: string
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
  created_at: string
  updated_at: string
}

export const createUser = (payload: UserCreatePayload): Promise<UserRead> =>
  apiClient.post<UserRead>('/users', payload).then((response) => response.data)

export const getUser = (userId: number): Promise<UserRead> =>
  apiClient.get<UserRead>(`/users/${userId}`).then((response) => response.data)

export const updateUser = (userId: number, payload: UserUpdatePayload): Promise<UserRead> =>
  apiClient.put<UserRead>(`/users/${userId}`, payload).then((response) => response.data)

export const deleteUser = (userId: number): Promise<void> =>
  apiClient.delete(`/users/${userId}`).then(() => undefined)
