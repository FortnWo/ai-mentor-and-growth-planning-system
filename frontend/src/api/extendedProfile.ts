import apiClient from './client'

export interface ExtendedProfile {
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

export interface ExtendedProfileUpdatePayload {
    interests?: string[]
    skills?: string[]
    goals?: string[]
    study_habits?: string[]
    personality?: string[]
    preferences?: string[]
}

export interface ExtendedProfileExtractionResult {
    interests: string[]
    skills: string[]
    goals: string[]
    study_habits: string[]
    personality: string[]
    preferences: string[]
}

export interface ExtendedProfileRefreshResponse {
    profile: ExtendedProfile
    extracted: ExtendedProfileExtractionResult
}

export const getMyExtendedProfile = (): Promise<ExtendedProfile> =>
    apiClient.get<ExtendedProfile>('/profile/extended/me').then((response) => response.data)

export const updateMyExtendedProfile = (payload: ExtendedProfileUpdatePayload): Promise<ExtendedProfile> =>
    apiClient.put<ExtendedProfile>('/profile/extended/me', payload).then((response) => response.data)

export const refreshMyExtendedProfileFromChat = (): Promise<ExtendedProfileRefreshResponse> =>
    apiClient.post<ExtendedProfileRefreshResponse>('/profile/extended/me/refresh-from-chat').then((response) => response.data)