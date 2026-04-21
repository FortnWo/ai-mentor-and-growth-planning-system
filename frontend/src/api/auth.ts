import apiClient from './client'
import type { UserRead } from './user'

export interface LoginPayload {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
  user: UserRead
}

export const login = (payload: LoginPayload): Promise<TokenResponse> =>
  apiClient.post<TokenResponse>('/auth/login', payload).then((response) => response.data)

export const getMe = (): Promise<UserRead> =>
  apiClient.get<UserRead>('/auth/me').then((response) => response.data)