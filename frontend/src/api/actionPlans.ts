import apiClient from './client'

export interface ActionPlan {
    id: number
    goal_id: number
    title: string
    summary: string | null
    status: string
    created_at: string
    updated_at: string
}

export interface ActionPlanItem {
    id: number
    plan_id: number
    breakdown_id: number | null
    title: string
    description: string | null
    frequency: string
    schedule: string | null
    status: string
    start_date: string | null
    due_date: string | null
    sequence: number
    created_at: string
    updated_at: string
}

export interface ActionPlanDetail extends ActionPlan {
    items: ActionPlanItem[]
}

export interface ActionPlanCreatePayload {
    goal_id: number
}

export const createActionPlan = (payload: ActionPlanCreatePayload): Promise<ActionPlanDetail> =>
    apiClient.post<ActionPlanDetail>('/action-plans', payload).then((response) => response.data)

export const listActionPlans = (): Promise<ActionPlan[]> =>
    apiClient.get<ActionPlan[]>('/action-plans').then((response) => response.data)

export const getActionPlanDetail = (planId: number): Promise<ActionPlanDetail> =>
    apiClient.get<ActionPlanDetail>(`/action-plans/${planId}`).then((response) => response.data)

export const refreshActionPlan = (planId: number): Promise<ActionPlanDetail> =>
    apiClient.post<ActionPlanDetail>(`/action-plans/${planId}/refresh`).then((response) => response.data)

export const deleteActionPlan = (planId: number): Promise<void> =>
    apiClient.delete(`/action-plans/${planId}`).then(() => undefined)