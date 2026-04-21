import apiClient from './client'
import type { UserRead } from './user'

export interface ProfileUpdatePayload {
  full_name?: string
  major?: string
  year_of_study?: number
  bio?: string
}

export interface PasswordChangePayload {
  current_password: string
  new_password: string
}

export const getMyProfile = (): Promise<UserRead> =>
  apiClient.get<UserRead>('/profile/me').then((response) => response.data)

export const updateMyProfile = (payload: ProfileUpdatePayload): Promise<UserRead> =>
  apiClient.put<UserRead>('/profile/me', payload).then((response) => response.data)

export const changeMyPassword = (payload: PasswordChangePayload): Promise<UserRead> =>
  apiClient.patch<UserRead>('/profile/me/password', payload).then((response) => response.data)