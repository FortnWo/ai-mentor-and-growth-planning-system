import apiClient from './client'

export interface PingResponse {
  status: string
  message: string
}

export const ping = (): Promise<PingResponse> =>
  apiClient.get<PingResponse>('/ping').then((r) => r.data)

export * from './auth'
export * from './chat'
export * from './profile'
export * from './user'
