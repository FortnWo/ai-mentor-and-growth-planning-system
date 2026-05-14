import apiClient from './client'

const ACTION_PLAN_REQUEST_TIMEOUT = 60_000

export interface ActionPlan {
    id: number
    goal_id: number
    main_breakdown_id: number
    title: string
    summary: string | null
    status: string
    error_message?: string | null
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

export const createActionPlan = (payload: ActionPlanCreatePayload): Promise<ActionPlanDetail[]> =>
    apiClient
        .post<ActionPlanDetail[]>('/action-plans', payload, { timeout: ACTION_PLAN_REQUEST_TIMEOUT })
        .then((response) => response.data)

export const listActionPlans = (goalId?: number): Promise<ActionPlan[]> => {
    const params = goalId != null ? { goal_id: goalId } : {}
    return apiClient.get<ActionPlan[]>('/action-plans', { params }).then((response) => response.data)
}

export const getActionPlanDetail = (planId: number): Promise<ActionPlanDetail> =>
    apiClient.get<ActionPlanDetail>(`/action-plans/${planId}`).then((response) => response.data)

export const refreshActionPlan = (planId: number): Promise<ActionPlanDetail> =>
    apiClient
        .post<ActionPlanDetail>(`/action-plans/${planId}/refresh`, undefined, { timeout: ACTION_PLAN_REQUEST_TIMEOUT })
        .then((response) => response.data)

export interface ActionPlanItemCompletionPayload {
    completed: boolean
}

export const deleteActionPlan = (planId: number): Promise<void> =>
    apiClient.delete(`/action-plans/${planId}`).then(() => undefined)

export const patchActionPlanItemCompletion = (
    planId: number,
    itemId: number,
    payload: ActionPlanItemCompletionPayload,
): Promise<ActionPlanItem> =>
    apiClient.patch<ActionPlanItem>(`/action-plans/${planId}/items/${itemId}`, payload).then((r) => r.data)