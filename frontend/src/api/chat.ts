import apiClient from './client'

export type MessageRole = 'user' | 'assistant'

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

export const deleteSession = (sessionId: number, userId: number): Promise<void> =>
  apiClient
    .delete(`/chat/${sessionId}`, {
      params: {
        user_id: userId,
      },
    })
    .then(() => undefined)

export const renameSession = (sessionId: number, userId: number, title: string): Promise<ChatSessionRead> =>
  apiClient
    .patch<ChatSessionRead>(
      `/chat/${sessionId}`,
      { title } satisfies RenameSessionPayload,
      {
        params: {
          user_id: userId,
        },
      },
    )
    .then((response) => response.data)
