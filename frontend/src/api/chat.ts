import apiClient from './client'

export type MessageRole = 'user' | 'assistant'

export interface ChatSessionRead {
  id: number
  user_id: number
  title?: string
  created_at: string
}

export interface ChatMessageRead {
  id: number
  session_id: number
  role: MessageRole
  content: string
  created_at: string
}

export interface SendMessagePayload {
  user_id: number
  message: string
  session_id?: number
  title?: string
}

export interface SendMessageResponse {
  session: ChatSessionRead
  user_message: ChatMessageRead
  assistant_message: ChatMessageRead
}

export const sendMessage = (payload: SendMessagePayload): Promise<SendMessageResponse> =>
  apiClient.post<SendMessageResponse>('/chat', payload).then((response) => response.data)

export const listSessions = (userId: number): Promise<ChatSessionRead[]> =>
  apiClient
    .get<ChatSessionRead[]>('/chat/sessions', {
      params: {
        user_id: userId,
      },
    })
    .then((response) => response.data)

export const listMessages = (sessionId: number, userId?: number): Promise<ChatMessageRead[]> =>
  apiClient
    .get<ChatMessageRead[]>(`/chat/${sessionId}/messages`, {
      params: {
        user_id: userId,
      },
    })
    .then((response) => response.data)
