import apiClient from './client'

export interface PingResponse {
  status: string
  message: string
}

export const ping = (): Promise<PingResponse> =>
  apiClient.get<PingResponse>('/ping').then((r) => r.data)

export * from './chat'
export * from './user'
