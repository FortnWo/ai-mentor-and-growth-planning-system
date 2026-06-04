import apiClient from './client'

export interface AvailableMethodsResponse {
  methods: string[]
}

export interface SendCodePayload {
  username: string
  method: 'phone' | 'email'
}

export interface VerifyCodePayload {
  username: string
  method: string
  code: string
}

export interface VerifyCodeResponse {
  reset_token: string
  message: string
}

export interface ConfirmResetPayload {
  reset_token: string
  new_password: string
}

export const getAvailableMethods = (): Promise<AvailableMethodsResponse> =>
  apiClient
    .get<AvailableMethodsResponse>('/auth/password-reset/available-methods')
    .then((r) => r.data)

export const sendResetCode = (payload: SendCodePayload): Promise<{ message: string }> =>
  apiClient
    .post<{ message: string }>('/auth/password-reset/send-code', payload)
    .then((r) => r.data)

export const verifyResetCode = (payload: VerifyCodePayload): Promise<VerifyCodeResponse> =>
  apiClient
    .post<VerifyCodeResponse>('/auth/password-reset/verify', payload)
    .then((r) => r.data)

export const confirmPasswordReset = (payload: ConfirmResetPayload): Promise<{ message: string }> =>
  apiClient
    .post<{ message: string }>('/auth/password-reset/confirm', payload)
    .then((r) => r.data)
