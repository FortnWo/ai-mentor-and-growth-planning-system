import apiClient from './client'

export type MessageRole = 'user' | 'assistant'
export type MessageDeliveryStatus = 'pending' | 'completed' | 'failed'

export interface ChatSessionRead {
  id: number
  user_id: number
  title?: string
  created_at: string
}

export interface RenameSessionPayload {
  title: string
}

export interface ChatMessageRead {
  id: number
  session_id: number
  role: MessageRole
  content: string
  status?: MessageDeliveryStatus
  created_at: string
}

export interface SendMessagePayload {
  message: string
  session_id?: number
  title?: string
}

export interface SendMessageResponse {
  session: ChatSessionRead
  user_message: ChatMessageRead
  assistant_message?: ChatMessageRead | null
}

export const sendMessage = (payload: SendMessagePayload): Promise<SendMessageResponse> =>
  apiClient
    .post<SendMessageResponse>('/chat', payload, { timeout: 120_000 })
    .then((response) => response.data)

export const listSessions = (): Promise<ChatSessionRead[]> => apiClient.get<ChatSessionRead[]>('/chat/sessions').then((response) => response.data)

export const listMessages = (sessionId: number): Promise<ChatMessageRead[]> =>
  apiClient.get<ChatMessageRead[]>(`/chat/${sessionId}/messages`).then((response) => response.data)

export const deleteSession = (sessionId: number): Promise<void> => apiClient.delete(`/chat/${sessionId}`).then(() => undefined)

export const renameSession = (sessionId: number, title: string): Promise<ChatSessionRead> =>
  apiClient.patch<ChatSessionRead>(`/chat/${sessionId}`, { title } satisfies RenameSessionPayload).then((response) => response.data)
