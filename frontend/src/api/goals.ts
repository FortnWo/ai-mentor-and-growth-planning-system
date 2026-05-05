import apiClient from './client'

export interface GoalBreakdownNode {
    id: number
    title: string
    description: string | null
    level: number
    sequence: number
    status: string
    due_date: string | null
    children: GoalBreakdownNode[]
    created_at: string
    updated_at: string
}

export interface GoalBreakdownTree {
    goal_id: number
    title: string
    description: string | null
    root_nodes: GoalBreakdownNode[]
}

export interface Goal {
    id: number
    user_id: number
    title: string
    description: string | null
    status: string
    priority: string
    target_date: string | null
    created_at: string
    updated_at: string
}

export interface GoalDetail extends Goal {
    breakdowns: GoalBreakdownTree
}

export interface GoalCreatePayload {
    title: string
    description?: string
    priority?: string
    target_date?: string
}

export interface GoalUpdatePayload {
    title?: string
    description?: string
    status?: string
    priority?: string
    target_date?: string
}

export const createGoal = (payload: GoalCreatePayload): Promise<Goal> =>
    apiClient.post<Goal>('/goals', payload).then((response) => response.data)

export const listGoals = (status?: string): Promise<Goal[]> => {
    const params = status ? { status } : {}
    return apiClient.get<Goal[]>('/goals', { params }).then((response) => response.data)
}

export const getGoalDetail = (goalId: number): Promise<GoalDetail> =>
    apiClient.get<GoalDetail>(`/goals/${goalId}`).then((response) => response.data)

export const updateGoal = (goalId: number, payload: GoalUpdatePayload): Promise<Goal> =>
    apiClient.put<Goal>(`/goals/${goalId}`, payload).then((response) => response.data)

export const refreshGoalBreakdown = (goalId: number): Promise<{ message: string }> =>
    apiClient.post<{ message: string }>(`/goals/${goalId}/refresh-breakdown`).then((response) => response.data)

export const deleteGoal = (goalId: number): Promise<void> =>
    apiClient.delete(`/goals/${goalId}`).then(() => undefined)
