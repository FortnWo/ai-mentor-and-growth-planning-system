import apiClient from './client'
import type { UserRead } from './user'

export interface InfoUpdatePayload {
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface PasswordChangePayload {
  current_password: string
  new_password: string
}

export const getMyInfo = (): Promise<UserRead> =>
  apiClient.get<UserRead>('/info/me').then((response) => response.data)

export const updateMyInfo = (payload: InfoUpdatePayload): Promise<UserRead> =>
  apiClient.put<UserRead>('/info/me', payload).then((response) => response.data)

export const changeMyPassword = (payload: PasswordChangePayload): Promise<UserRead> =>
  apiClient.patch<UserRead>('/info/me/password', payload).then((response) => response.data)
