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

export interface UserTrait {
  trait_type: string
  trait_key: string
  source: string
  confidence: number | null
  trait_score: number
  last_observed_at: string | null
}

export interface ProfileInsights {
  last_extracted_at: string | null
  portrait_summary: string | null
  portrait_summary_at: string | null
  traits: UserTrait[]
}

export const TRAIT_TYPE_LABELS: Record<string, string> = {
  interest: '兴趣',
  skill: '技能',
  goal_signal: '目标',
  study_habit: '学习习惯',
  personality: '性格',
  preference: '偏好',
}

export const TRAIT_SOURCE_LABELS: Record<string, string> = {
  chat_extraction: '聊天',
  profile_update: '手动',
}

export const TRAIT_TYPE_ORDER = [
  'interest',
  'skill',
  'goal_signal',
  'study_habit',
  'personality',
  'preference',
]

export const getMyProfile = (): Promise<Profile> =>
  apiClient.get<Profile>('/profile/me').then((response) => response.data)

export const updateMyProfile = (payload: ProfileUpdatePayload): Promise<Profile> =>
  apiClient.put<Profile>('/profile/me', payload).then((response) => response.data)

export const getMyProfileInsights = (): Promise<ProfileInsights> =>
  apiClient.get<ProfileInsights>('/profile/me/insights').then((response) => response.data)

export const refreshMyProfileFromChat = (): Promise<ProfileRefreshResponse> =>
  apiClient.post<ProfileRefreshResponse>('/profile/me/refresh-from-chat').then((response) => response.data)
