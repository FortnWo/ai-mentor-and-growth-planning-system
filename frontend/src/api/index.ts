import apiClient from './client'

export interface PingResponse {
  status: string
  message: string
}

export const ping = (): Promise<PingResponse> =>
  apiClient.get<PingResponse>('/ping').then((r) => r.data)

export interface ChatRequest {
  session_id?: number
  message: string
}

export interface ChatResponse {
  session_id: number
  role: string
  content: string
  created_at: string
}

export const sendMessage = (payload: ChatRequest): Promise<ChatResponse> =>
  apiClient.post<ChatResponse>('/chat', payload).then((r) => r.data)

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

export const getProfile = (userId: number): Promise<UserRead> =>
  apiClient.get<UserRead>(`/profile/${userId}`).then((r) => r.data)
