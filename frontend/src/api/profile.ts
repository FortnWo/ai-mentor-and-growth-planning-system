import apiClient from './client'

export interface Profile {
  id: number
  user_id: number
  interests: string[]
  skills: string[]
  goals: string[]
  study_habits: string[]
  personality: string[]
  preferences: string[]
  last_extracted_at: string | null
  created_at: string
  updated_at: string
}

export interface ProfileUpdatePayload {
  interests?: string[]
  skills?: string[]
  goals?: string[]
  study_habits?: string[]
  personality?: string[]
  preferences?: string[]
}

export interface ProfileExtractionResult {
  interests: string[]
  skills: string[]
  goals: string[]
  study_habits: string[]
  personality: string[]
  preferences: string[]
}

export interface ProfileRefreshResponse {
  profile: Profile
  extracted: ProfileExtractionResult
}

export const getMyProfile = (): Promise<Profile> =>
  apiClient.get<Profile>('/profile/me').then((response) => response.data)

export const updateMyProfile = (payload: ProfileUpdatePayload): Promise<Profile> =>
  apiClient.put<Profile>('/profile/me', payload).then((response) => response.data)

export const refreshMyProfileFromChat = (): Promise<ProfileRefreshResponse> =>
  apiClient.post<ProfileRefreshResponse>('/profile/me/refresh-from-chat').then((response) => response.data)
