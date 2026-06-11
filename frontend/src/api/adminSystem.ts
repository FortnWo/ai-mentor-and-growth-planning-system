import apiClient from './client'

export type UsageLogPeriod = 'today' | 'week' | 'month'

export type UsageStatEntry = {
  period: string
  date_label: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export type UsageDetailEntry = {
  day: string
  model: string
  task: string | null
  calls: number
  prompt_tokens: number
  completion_tokens: number
}

export type UsageLogsResponse = {
  stats: UsageStatEntry[]
  user_detail: UsageDetailEntry[] | null
}

export const getAiUsageLogs = (
  period: UsageLogPeriod,
  username?: string,
): Promise<UsageLogsResponse> =>
  apiClient
    .get<UsageLogsResponse>('/admin/system/logs/usage', {
      params: {
        period,
        ...(username ? { username } : {}),
      },
    })
    .then((response) => response.data)

export type LlmConfigSource = {
  llm_api_key: 'env' | 'db' | 'unset'
  llm_api_base_url: 'env' | 'db' | 'unset'
  llm_model: 'env' | 'db' | 'unset'
}

export type AiConfigResponse = {
  llm_api_key_set: boolean
  llm_api_key_masked: string | null
  llm_api_base_url: string | null
  llm_model: string | null
  llm_system_prompt: string | null
  admin_llm_system_prompt: string | null
  active_preset_id: string | null
  effective_llm_api_key_set: boolean
  effective_llm_api_key_masked: string | null
  effective_llm_api_base_url: string | null
  effective_llm_model: string | null
  llm_config_source: LlmConfigSource
}

export type LlmPreset = {
  id: string
  name: string
  llm_api_base_url: string | null
  llm_model: string | null
  llm_api_key_set: boolean
  llm_api_key_masked: string | null
}

export type LlmPresetListResponse = {
  presets: LlmPreset[]
}

export type LlmPresetCreatePayload = {
  name: string
  llm_api_key?: string
  llm_api_base_url?: string
  llm_model?: string
}

export const getAiConfig = (): Promise<AiConfigResponse> =>
  apiClient.get<AiConfigResponse>('/admin/system/ai-config').then((r) => r.data)

export const getLlmPresets = (): Promise<LlmPresetListResponse> =>
  apiClient.get<LlmPresetListResponse>('/admin/system/llm-presets').then((r) => r.data)

export const createLlmPreset = (payload: LlmPresetCreatePayload): Promise<LlmPreset> =>
  apiClient.post<LlmPreset>('/admin/system/llm-presets', payload).then((r) => r.data)

export const deleteLlmPreset = (presetId: string): Promise<void> =>
  apiClient.delete(`/admin/system/llm-presets/${presetId}`).then(() => undefined)

export const activateLlmPreset = (presetId: string): Promise<{ active_preset_id: string }> =>
  apiClient
    .post<{ active_preset_id: string }>(`/admin/system/llm-presets/${presetId}/activate`)
    .then((r) => r.data)
