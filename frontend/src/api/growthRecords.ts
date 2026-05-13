import apiClient from './client'

export interface GrowthRecordCreatePayload {
    title: string
    summary?: string
    content?: string
    record_type?: string
    source_type?: string
    source_ref_id?: number
    idempotency_key?: string
}

export interface GrowthRecordListItem {
    id: number
    title: string
    summary?: string
    record_date?: string
    occurred_at?: string
    record_type: string
    source_type: string
}

export const createGrowthRecord = (payload: GrowthRecordCreatePayload) =>
    apiClient.post('/growth-records', payload).then((r) => r.data)

export const listGrowthRecords = (params = {}) =>
    apiClient.get<GrowthRecordListItem[]>('/growth-records', { params }).then((r) => r.data)

export const getGrowthStats = (params = {}) => apiClient.get('/growth-records/stats', { params }).then((r) => r.data)

export interface GrowthDailyTrendPoint {
    record_date: string
    completed_count: number
    reflection_count: number
    milestone_count: number
    growth_score: number
}

export const getGrowthDailyTrend = (params: { start_date: string; end_date: string }) =>
    apiClient.get<GrowthDailyTrendPoint[]>('/growth-records/trend/daily', { params }).then((r) => r.data)

export const generateWeeklySummary = (payload: { start_date: string; end_date: string }) =>
    apiClient.post('/growth-records/summary/generate', payload).then((r) => r.data)
