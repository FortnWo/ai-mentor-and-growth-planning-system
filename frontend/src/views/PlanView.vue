<script setup lang="ts">
import { isAxiosError } from 'axios'
import { ref, computed, onMounted } from 'vue'
import { createGoal, listGoals, getGoalDetail, refreshGoalBreakdown, deleteGoal, rescheduleGoalPlans, type Goal, type GoalDetail } from '../api/goals'
import { createActionPlan, getActionPlanDetail, listActionPlans, refreshActionPlan, deleteActionPlan, patchActionPlanItemCompletion, type ActionPlan, type ActionPlanDetail, type ActionPlanItem } from '../api/actionPlans'
import BreakdownPathTree from '../components/BreakdownPathTree.vue'
import { getApiErrorMessage } from '../utils/apiError'

// State
const goals = ref<Goal[]>([])
const selectedGoal = ref<GoalDetail | null>(null)
const actionPlans = ref<ActionPlan[]>([])
const selectedActionPlan = ref<ActionPlanDetail | null>(null)
const showCreateForm = ref(false)
const isLoading = ref(false)
const isRefreshing = ref(false)
const isPollingBreakdown = ref(false)
const isActionPlanFetching = ref(false)
const isActionPlanBusy = ref(false)
const isActionPlanPolling = ref(false)
const pollingGoalId = ref<number | null>(null)
const pollingActionPlanGoalId = ref<number | null>(null)
const errorMessage = ref('')
const itemBusyId = ref<number | null>(null)
const selectedMainBreakdownId = ref<number | null>(null)
const isRescheduling = ref(false)
const showGoalPicker = ref(true)

function clearError() {
  errorMessage.value = ''
}

// Form state
const formData = ref({
  title: '',
  description: '',
  priority: 'medium',
  target_date: '',
})

// Load all goals
const loadGoals = async () => {
  try {
    isLoading.value = true
    goals.value = await listGoals()
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法加载目标列表。')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const loadActionPlans = async () => {
  try {
    actionPlans.value = await listActionPlans()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法加载行动计划列表。')
    console.error(error)
  }
}

function mergeActionPlansForGoal(goalId: number, incoming: ActionPlan[]) {
  const rest = actionPlans.value.filter((plan) => plan.goal_id !== goalId)
  actionPlans.value = [...incoming, ...rest]
}

const loadActionPlansForGoal = async (goalId: number) => {
  try {
    const summaries = await listActionPlans(goalId)
    mergeActionPlansForGoal(goalId, summaries)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法加载该目标的行动计划列表。')
    console.error(error)
  }
}

async function refreshSelectedGoalFromServer(goalId: number) {
  const detail = await getGoalDetail(goalId)
  if (selectedGoal.value?.id === goalId) {
    selectedGoal.value = detail
  }
}

const pollGoalBreakdown = async (goalId: number) => {
  if (isPollingBreakdown.value && pollingGoalId.value === goalId) return

  isPollingBreakdown.value = true
  pollingGoalId.value = goalId

  const maxAttempts = 20
  const delayMs = 1500

  try {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const detail = await getGoalDetail(goalId)
      if (detail.breakdowns?.root_nodes?.length) {
        if (selectedGoal.value?.id === goalId || !selectedGoal.value) {
          selectedGoal.value = detail
        }
        void pollActionPlansForGoal(goalId)
        return
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '获取目标拆解状态时出现问题。')
    console.error(error)
  } finally {
    isPollingBreakdown.value = false
    pollingGoalId.value = null
  }
}

const pollActionPlansForGoal = async (goalId: number) => {
  if (isActionPlanPolling.value && pollingActionPlanGoalId.value === goalId) return

  isActionPlanPolling.value = true
  pollingActionPlanGoalId.value = goalId

  const maxAttempts = 40
  const delayMs = 1200

  try {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const summaries = await listActionPlans(goalId)
      mergeActionPlansForGoal(goalId, summaries)

      await refreshSelectedGoalFromServer(goalId)

      const allSettled =
        summaries.length > 0 &&
        summaries.every((plan) => plan.status !== 'in_progress')

      if (allSettled) {
        if (selectedGoal.value?.id === goalId && selectedMainBreakdownId.value != null) {
          const row = selectedGoal.value.main_action_plan_progress?.find(
            (r) => r.main_breakdown_id === selectedMainBreakdownId.value,
          )
          if (row?.plan_id) {
            try {
              selectedActionPlan.value = await getActionPlanDetail(row.plan_id)
            } catch {
              selectedActionPlan.value = null
            }
          }
        }
        return
      }

      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '获取行动计划状态时出现问题。')
    console.error(error)
  } finally {
    if (pollingActionPlanGoalId.value === goalId) {
      isActionPlanPolling.value = false
      pollingActionPlanGoalId.value = null
    }
  }
}

// Load goal detail
const selectGoal = async (goal: Goal, options?: { focusWorkspace?: boolean }) => {
  const focusWorkspace = options?.focusWorkspace !== false
  try {
    isLoading.value = true
    const detail = await getGoalDetail(goal.id)
    selectedGoal.value = detail
    selectedMainBreakdownId.value = null
    selectedActionPlan.value = null
    if (!detail.breakdowns?.root_nodes?.length) {
      void pollGoalBreakdown(goal.id)
    }
    await loadActionPlansForGoal(goal.id)
    void pollActionPlansForGoal(goal.id)
    clearError()
    if (focusWorkspace) {
      showGoalPicker.value = false
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法加载目标详情。')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

function returnToGoalPicker() {
  showGoalPicker.value = true
}

const upsertActionPlanSummary = (detail: ActionPlanDetail) => {
  const summary: ActionPlan = {
    id: detail.id,
    goal_id: detail.goal_id,
    main_breakdown_id: detail.main_breakdown_id,
    title: detail.title,
    summary: detail.summary,
    status: detail.status,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  }

  const existingIndex = actionPlans.value.findIndex((plan) => plan.id === summary.id)
  if (existingIndex >= 0) {
    actionPlans.value.splice(existingIndex, 1, summary)
    return
  }

  actionPlans.value.unshift(summary)
}

const onSelectMainBreakdown = async (mainId: number) => {
  selectedMainBreakdownId.value = mainId
  const gid = selectedGoal.value?.id
  if (!gid) return

  try {
    isActionPlanFetching.value = true
    const row = selectedGoal.value?.main_action_plan_progress?.find((r) => r.main_breakdown_id === mainId)
    if (row?.plan_id) {
      selectedActionPlan.value = await getActionPlanDetail(row.plan_id)
      if (selectedActionPlan.value?.status === 'in_progress') {
        void pollActionPlansForGoal(gid)
      }
    } else {
      selectedActionPlan.value = null
    }
    clearError()
  } catch (error) {
    selectedActionPlan.value = null
    errorMessage.value = getApiErrorMessage(error, '无法加载行动计划详情。')
    console.error(error)
  } finally {
    isActionPlanFetching.value = false
  }
}

const handleGenerateActionPlan = async () => {
  if (!selectedGoal.value) return

  try {
    isActionPlanBusy.value = true
    const details = await createActionPlan({ goal_id: selectedGoal.value.id })
    for (const detail of details) {
      upsertActionPlanSummary(detail)
    }
    if (details.some((d) => d.status === 'in_progress')) {
      void pollActionPlansForGoal(selectedGoal.value.id)
    }
    await refreshSelectedGoalFromServer(selectedGoal.value.id)
    clearError()
  } catch (error) {
    if (isTimeoutError(error) && selectedGoal.value) {
      clearError()
      void pollActionPlansForGoal(selectedGoal.value.id)
      return
    }
    errorMessage.value = getApiErrorMessage(error, '无法生成行动计划。')
    console.error(error)
  } finally {
    isActionPlanBusy.value = false
  }
}

const handleRefreshActionPlan = async () => {
  if (!selectedActionPlan.value) return

  try {
    isActionPlanBusy.value = true
    const detail = await refreshActionPlan(selectedActionPlan.value.id)
    selectedActionPlan.value = detail
    upsertActionPlanSummary(detail)
    if (detail.status === 'in_progress') {
      void pollActionPlansForGoal(selectedActionPlan.value.goal_id)
    }
    clearError()
  } catch (error) {
    if (isTimeoutError(error)) {
      clearError()
      void pollActionPlansForGoal(selectedActionPlan.value.goal_id)
      return
    }
    errorMessage.value = getApiErrorMessage(error, '无法刷新行动计划。')
    console.error(error)
  } finally {
    isActionPlanBusy.value = false
  }
}

// Create goal
const handleCreateGoal = async () => {
  if (!formData.value.title.trim()) {
    errorMessage.value = '请填写目标标题。'
    return
  }

  try {
    isLoading.value = true
    const newGoal = await createGoal({
      title: formData.value.title,
      description: formData.value.description || undefined,
      priority: formData.value.priority,
      target_date: formData.value.target_date || undefined,
    })

    goals.value.unshift(newGoal)
    await selectGoal(newGoal)
    showCreateForm.value = false
    formData.value = { title: '', description: '', priority: 'medium', target_date: '' }
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法创建目标。')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

// Refresh breakdown
const handleRefreshBreakdown = async () => {
  if (!selectedGoal.value) return

  try {
    isRefreshing.value = true
    await refreshGoalBreakdown(selectedGoal.value.id)
    await selectGoal(selectedGoal.value, { focusWorkspace: false })
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法刷新目标拆解。')
    console.error(error)
  } finally {
    isRefreshing.value = false
  }
}

// Delete goal
const handleDeleteGoal = async (goalId: number) => {
  if (!confirm('Are you sure you want to delete this goal?')) return

  try {
    await deleteGoal(goalId)
    goals.value = goals.value.filter(g => g.id !== goalId)
    actionPlans.value = actionPlans.value.filter((plan) => plan.goal_id !== goalId)
    if (selectedGoal.value?.id === goalId) {
      selectedGoal.value = null
      selectedActionPlan.value = null
      selectedMainBreakdownId.value = null
      showGoalPicker.value = true
    }
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法删除目标。')
    console.error(error)
  }
}

const handleDeleteActionPlan = async () => {
  if (!selectedActionPlan.value) return

  try {
    await deleteActionPlan(selectedActionPlan.value.id)
    actionPlans.value = actionPlans.value.filter((plan) => plan.id !== selectedActionPlan.value?.id)
    selectedActionPlan.value = null
    selectedMainBreakdownId.value = null
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法删除行动计划。')
    console.error(error)
  }
}

function isActionPlanItemCompleted(item: ActionPlanItem): boolean {
  return item.status === 'completed'
}

async function toggleActionPlanItemCompletion(item: ActionPlanItem, completed: boolean) {
  if (!selectedActionPlan.value) return

  itemBusyId.value = item.id
  clearError()
  try {
    const updated = await patchActionPlanItemCompletion(selectedActionPlan.value.id, item.id, { completed })
    const nextItems = selectedActionPlan.value.items.map((i) => (i.id === item.id ? { ...i, ...updated } : i))
    const nextDetail: ActionPlanDetail = { ...selectedActionPlan.value, items: nextItems }
    selectedActionPlan.value = nextDetail
    upsertActionPlanSummary(nextDetail)
    if (selectedGoal.value) {
      await refreshSelectedGoalFromServer(selectedGoal.value.id)
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法更新行动计划条目状态。')
    console.error(error)
  } finally {
    itemBusyId.value = null
  }
}

const handleRescheduleGoal = async () => {
  if (!selectedGoal.value) return
  if (!confirm('将根据当前日期重新拆解目标并生成各阶段行动计划，是否继续？')) return

  try {
    isRescheduling.value = true
    await rescheduleGoalPlans(selectedGoal.value.id)
    selectedMainBreakdownId.value = null
    selectedActionPlan.value = null
    await selectGoal(selectedGoal.value, { focusWorkspace: false })
    clearError()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error, '无法启动重新安排。')
    console.error(error)
  } finally {
    isRescheduling.value = false
  }
}

// Format date for display
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

const isTimeoutError = (error: unknown): boolean => {
  if (isAxiosError(error)) {
    return error.code === 'ECONNABORTED' || error.message?.toLowerCase().includes('timeout') === true
  }
  return false
}

// Computed
const hasGoals = computed(() => goals.value.length > 0)
const breakdownNodes = computed(() => selectedGoal.value?.breakdowns.root_nodes || [])
const progressByMainId = computed(() => {
  const map: Record<number, { total: number; done: number }> = {}
  for (const row of selectedGoal.value?.main_action_plan_progress ?? []) {
    map[row.main_breakdown_id] = { total: row.total_items, done: row.completed_items }
  }
  return map
})
const actionPlanItems = computed<ActionPlanItem[]>(() => selectedActionPlan.value?.items || [])
const isActionPlanLoading = computed(() => isActionPlanFetching.value || isActionPlanPolling.value)
const actionPlanErrorMessage = computed(() => selectedActionPlan.value?.error_message?.trim() || '')
const breakdownStatusMessage = computed(() => {
  if (isPollingBreakdown.value) {
    return 'AI 正在生成拆解，已自动刷新…'
  }
  return 'AI 正在生成你的行动计划，请稍后刷新。'
})
const actionPlanStatusMessage = computed(() => {
  if (isActionPlanBusy.value) {
    return '正在向 AI 提交生成请求…'
  }
  if (isActionPlanPolling.value) {
    return 'AI 正在生成你的行动计划，已自动刷新…'
  }
  if (isActionPlanFetching.value) {
    return '正在加载行动计划详情…'
  }
  return ''
})

// Lifecycle
onMounted(() => {
  void Promise.all([loadGoals(), loadActionPlans()])
})
</script>

<template>
  <div class="page page--wide plan-page">
    <div v-if="errorMessage" class="error-banner" role="alert">
      <p class="feedback feedback--error error-banner__text">{{ errorMessage }}</p>
      <button type="button" class="btn btn--secondary error-banner__dismiss" @click="clearError">关闭</button>
    </div>

    <!-- Header -->
    <section class="page-header glass-card panel hero-frame reveal">
      <p class="page-kicker">成长规划</p>
      <h1 class="page-title">目标与路线图</h1>
      <p class="page-subtitle">
        设定你的成长目标，并让 AI 帮你拆解成可执行步骤。
      </p>

      <div class="hero-actions">
        <button class="btn btn--primary" @click="showCreateForm = !showCreateForm" :disabled="isLoading">
          {{ showCreateForm ? '取消' : '+ 新建目标' }}
        </button>
      </div>
    </section>

    <!-- Create Form -->
    <section v-if="showCreateForm" class="panel create-form reveal">
      <h2 class="section-title">创建新目标</h2>
      <form @submit.prevent="handleCreateGoal" class="form-grid">
        <div class="form-group">
          <label for="goal-title">目标标题 *</label>
          <input id="goal-title" v-model="formData.title" type="text" placeholder="例如：学习前端开发" required />
        </div>

        <div class="form-group">
          <label for="goal-description">描述</label>
          <textarea id="goal-description" v-model="formData.description" placeholder="详细描述你的目标…" rows="4" />
        </div>

        <div class="form-group form-group--half">
          <label for="goal-priority">优先级</label>
          <select id="goal-priority" v-model="formData.priority">
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
          </select>
        </div>

        <div class="form-group form-group--half">
          <label for="goal-target-date">目标日期</label>
          <input id="goal-target-date" v-model="formData.target_date" type="date" />
        </div>

        <button type="submit" class="btn btn--primary btn--full" :disabled="isLoading">
          {{ isLoading ? '创建中…' : '创建目标' }}
        </button>
      </form>
    </section>

    <!-- Goals Layout -->
    <div v-if="hasGoals" class="goals-container" :class="{ 'goals-container--picker': showGoalPicker }">
      <!-- Goals List -->
      <section v-show="showGoalPicker" class="goals-list reveal">
        <h2 class="section-title">你的目标</h2>
        <div class="goal-cards">
          <div v-for="goal in goals" :key="goal.id" class="goal-card"
            :class="{ 'goal-card--selected': selectedGoal?.id === goal.id }" @click="selectGoal(goal)">
            <div class="goal-card-header">
              <h3>{{ goal.title }}</h3>
              <span class="badge" :class="`badge--${goal.priority}`">
                {{ goal.priority }}
              </span>
            </div>
            <p v-if="goal.description" class="goal-card-desc">
              {{ goal.description.substring(0, 80) }}{{ goal.description.length > 80 ? '...' : '' }}
            </p>
            <div class="goal-card-footer">
              <span class="status-badge">{{ goal.status }}</span>
              <span v-if="goal.target_date" class="date-badge">
                {{ formatDate(goal.target_date) }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section v-if="selectedGoal && !showGoalPicker" class="goal-detail reveal goal-detail--workspace-focus">
        <div class="goal-workspace-card goal-workspace-card--focused">
          <div class="goal-workspace-card__bar">
            <button type="button" class="btn btn--secondary btn--sm goal-workspace-card__back"
              @click="returnToGoalPicker">
              ← 返回目标选择
            </button>
            <div class="goal-workspace-card__bar-actions">
              <button type="button" class="btn btn--secondary btn--sm" @click="handleRescheduleGoal"
                :disabled="isRescheduling || isRefreshing">
                {{ isRescheduling ? '安排中…' : '📅 重新安排' }}
              </button>
              <button type="button" class="btn btn--secondary btn--sm" @click="handleRefreshBreakdown"
                :disabled="isRefreshing">
                {{ isRefreshing ? '刷新中…' : '🔄 刷新拆解' }}
              </button>
              <button type="button" class="btn btn--danger btn--sm" @click="handleDeleteGoal(selectedGoal.id)">
                🗑️ 删除目标
              </button>
            </div>
          </div>
          <div class="detail-split">
            <div class="detail-card detail-card--breakdown">
              <div class="detail-card__head">
                <h3 class="detail-card__title">目标拆解</h3>
                <p class="detail-card__lede">主路径节点默认展开；悬停带分支的节点可查看下级详情。</p>
              </div>
              <div v-if="breakdownNodes.length > 0" class="breakdown-path-wrap">
                <BreakdownPathTree
                  :nodes="breakdownNodes"
                  :progress-by-main-id="progressByMainId"
                  :selected-main-id="selectedMainBreakdownId"
                  @select-main="onSelectMainBreakdown"
                />
              </div>
              <p v-else class="placeholder detail-card__placeholder">
                {{ breakdownStatusMessage }}
              </p>
            </div>

            <div class="detail-card detail-card--action-plan">
              <div class="detail-card__head detail-card__head--row">
                <div>
                  <h3 class="detail-card__title">行动计划</h3>
                  <p class="detail-card__lede">
                    创建目标并拆解后，系统会为每个主节点自动生成一篇行动计划；点击左侧主节点查看对应清单。完成条目会写入成长记录并更新进度条。
                  </p>
                </div>
                <div class="detail-actions">
                  <button v-if="selectedGoal" class="btn btn--secondary btn--sm"
                    @click="handleGenerateActionPlan()"
                    :disabled="isActionPlanBusy || isActionPlanLoading || !breakdownNodes.length">
                    {{ isActionPlanBusy ? '处理中…' : '↻ 重新生成全部' }}
                  </button>
                  <button v-if="selectedActionPlan" class="btn btn--secondary btn--sm"
                    @click="handleRefreshActionPlan()"
                    :disabled="isActionPlanBusy || isActionPlanLoading">
                    {{ isActionPlanBusy ? '处理中…' : '🔄 刷新本篇' }}
                  </button>
                  <button v-if="selectedActionPlan" class="btn btn--danger btn--sm" @click="handleDeleteActionPlan"
                    :disabled="isActionPlanBusy">
                    🗑️ 移除计划
                  </button>
                </div>
              </div>

              <p v-if="actionPlanStatusMessage" class="status-hint">
                {{ actionPlanStatusMessage }}
              </p>

              <div v-if="isActionPlanLoading" class="placeholder detail-card__placeholder">
                正在加载行动计划…
              </div>
              <div v-else-if="!selectedMainBreakdownId" class="placeholder detail-card__placeholder">
                点击左侧「目标拆解」中的主节点，查看该阶段的行动计划与执行项。
              </div>
              <div v-else>
                <div v-if="selectedActionPlan" class="action-plan-inner">
                <div class="action-plan-card__header">
                  <div>
                    <h4>{{ selectedActionPlan.title }}</h4>
                    <p v-if="selectedActionPlan.summary" class="action-plan-summary">
                      {{ selectedActionPlan.summary }}
                    </p>
                  </div>
                  <span class="status-badge">{{ selectedActionPlan.status }}</span>
                </div>

                <p v-if="actionPlanErrorMessage" class="status-hint status-hint--error">
                  {{ actionPlanErrorMessage }}
                </p>

                <div v-if="actionPlanItems.length > 0" class="action-plan-list">
                  <article v-for="item in actionPlanItems" :key="item.id" class="action-plan-item"
                    :class="{ 'action-plan-item--done': isActionPlanItemCompleted(item) }">
                    <div class="action-plan-item__top">
                      <div class="action-plan-item__copy">
                        <h5>{{ item.title }}</h5>
                        <p v-if="item.description" class="action-plan-item__desc">
                          {{ item.description }}
                        </p>
                      </div>
                      <div class="action-plan-item__aside">
                        <span class="badge badge--muted">{{ item.frequency }}</span>
                        <div class="action-plan-item__actions">
                          <button v-if="!isActionPlanItemCompleted(item)" type="button" class="btn btn--primary btn--sm"
                            :disabled="isActionPlanBusy || itemBusyId === item.id"
                            @click="toggleActionPlanItemCompletion(item, true)">
                            {{ itemBusyId === item.id ? '…' : '完成' }}
                          </button>
                          <button v-else type="button" class="btn btn--secondary btn--sm"
                            :disabled="isActionPlanBusy || itemBusyId === item.id"
                            @click="toggleActionPlanItemCompletion(item, false)">
                            {{ itemBusyId === item.id ? '…' : '未完成' }}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div class="action-plan-item__meta">
                      <span>状态：<strong>{{ item.status }}</strong></span>
                      <span v-if="item.start_date">开始：<strong>{{ formatDate(item.start_date) }}</strong></span>
                      <span v-if="item.due_date">截止：<strong>{{ formatDate(item.due_date) }}</strong></span>
                      <span v-if="item.schedule">节奏：<strong>{{ item.schedule }}</strong></span>
                      <span v-if="item.breakdown_id">拆解节点：<strong>#{{ item.breakdown_id }}</strong></span>
                    </div>
                  </article>
                </div>

                <p v-else class="placeholder action-plan-empty">
                  {{ selectedActionPlan.status === 'failed'
                    ? '行动计划生成失败，请刷新重试。'
                    : '该计划有效，但 AI 没有返回条目，请刷新重新生成。' }}
                </p>
                </div>
                <p v-else class="placeholder detail-card__placeholder">
                  该主节点尚无行动计划记录，可尝试「重新生成全部」或等待后台生成完成。
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Empty State -->
    <section v-else class="panel roadmap-panel reveal reveal--delay-2">
      <div class="title-row">
        <div>
          <p class="eyebrow">开始使用</p>
          <h2 class="section-title">还没有目标</h2>
        </div>
      </div>

      <p class="placeholder">
        创建你的第一个成长目标，AI 会帮你把它拆成可执行步骤。
      </p>
    </section>
  </div>
</template>

<style scoped>
.plan-page {
  width: min(1180px, 100%);
  margin: 0 auto;
  padding: 2rem 1rem;
}

.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.error-banner__text {
  flex: 1;
  margin: 0;
  min-width: 12rem;
}

.error-banner__dismiss {
  flex-shrink: 0;
}

.status-hint {
  margin: 0.5rem 0 0;
  color: var(--secondary-text);
  font-size: 0.9rem;
}

.status-hint--error {
  color: #d14343;
}

.page-header {
  margin-bottom: 2rem;
}

.page-kicker {
  color: var(--secondary-text);
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.5rem 0;
}

.page-title {
  font-size: clamp(1.5rem, 3vw, 2.5rem);
  margin: 0 0 0.5rem 0;
  color: var(--heading);
}

.page-subtitle {
  color: var(--secondary-text);
  margin: 0 0 1.5rem 0;
  font-size: 1.05rem;
}

.hero-actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
  font-size: 0.95rem;
}

.btn--primary {
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  color: white;
}

.btn--primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn--secondary {
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--border);
}

.btn--secondary:hover:not(:disabled) {
  background: var(--surface-3);
}

.btn--danger {
  background: #fee;
  color: #d00;
  border: 1px solid #faa;
}

.btn--danger:hover:not(:disabled) {
  background: #fdd;
}

.btn--sm {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.btn--full {
  width: 100%;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.create-form {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: var(--surface-2);
  border-radius: 8px;
}

.section-title {
  font-size: 1.25rem;
  color: var(--heading);
  margin: 0 0 1rem 0;
  font-weight: 600;
}

.form-grid {
  display: grid;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group--half {
  grid-column: span 1;
}

@media (min-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }

  .form-grid> :nth-child(-n + 2) {
    grid-column: auto;
  }

  .form-grid> :last-child {
    grid-column: 1 / -1;
  }
}

.form-group label {
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: var(--text);
  font-size: 0.95rem;
}

.form-group input,
.form-group textarea,
.form-group select {
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 1rem;
  background: var(--surface-1);
  color: var(--text);
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--accent-1);
  box-shadow: 0 0 0 3px rgba(var(--accent-1-rgb), 0.1);
}

.goals-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  align-items: stretch;
}

.goals-container--picker .goals-list {
  max-height: none;
  overflow: visible;
}

.goal-detail--workspace-focus {
  max-height: min(82vh, 920px);
}

.goal-workspace-card__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.35rem;
}

.goal-workspace-card__bar-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-left: auto;
}

.goal-workspace-card__back {
  flex-shrink: 0;
}

.goal-workspace-card--focused {
  padding: 0.85rem 1rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-1);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.goal-workspace-card--focused .detail-split {
  margin-top: 0.85rem;
}

.goals-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 0;
  max-height: min(72vh, 720px);
  overflow-y: auto;
  padding-right: 0.35rem;
}

.goal-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.goal-card {
  padding: 1.25rem;
  border: 2px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--surface-2);
}

.goal-card:hover {
  border-color: var(--accent-1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.goal-card--selected {
  border-color: var(--accent-1);
  background: linear-gradient(135deg, rgba(var(--accent-1-rgb), 0.05), rgba(var(--accent-2-rgb), 0.05));
}

.goal-card-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.goal-card-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--heading);
  flex: 1;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}

.badge--low {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge--medium {
  background: #fff3e0;
  color: #f57c00;
}

.badge--high {
  background: #ffebee;
  color: #c62828;
}

.goal-card-desc {
  color: var(--secondary-text);
  margin: 0 0 1rem 0;
  font-size: 0.95rem;
}

.goal-card-footer {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.status-badge,
.date-badge {
  font-size: 0.8rem;
  padding: 0.25rem 0.5rem;
  background: var(--surface-3);
  border-radius: 4px;
  color: var(--secondary-text);
}

.goal-detail {
  padding: 1.5rem;
  background: var(--surface-2);
  border-radius: 8px;
  border: 1px solid var(--border);
  min-height: 0;
  max-height: min(78vh, 880px);
  overflow-y: auto;
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
}

.detail-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
  margin-top: 1.25rem;
}

.detail-card {
  padding: 1rem 1.1rem 1.15rem;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface-1);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  min-height: 0;
}

.detail-card__head {
  margin-bottom: 0.75rem;
}

.detail-card__head--row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.detail-card__title {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
  color: var(--heading);
}

.detail-card__lede {
  margin: 0;
  font-size: 0.82rem;
  color: var(--secondary-text);
  line-height: 1.45;
  max-width: 42ch;
}

.detail-card__placeholder {
  margin-top: 0.5rem;
}

.breakdown-path-wrap {
  max-height: min(52vh, 560px);
  overflow-y: auto;
  padding-right: 0.25rem;
}

.action-plan-inner {
  display: grid;
  gap: 0.85rem;
  margin-top: 0.35rem;
}

.action-plan-item__copy {
  flex: 1;
  min-width: 0;
}

.action-plan-item__aside {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.45rem;
  flex-shrink: 0;
}

.action-plan-item__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: flex-end;
}

.action-plan-item--done {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(240, 253, 244, 0.55);
}

@media (max-width: 960px) {
  .detail-split {
    grid-template-columns: 1fr;
  }

  .breakdown-path-wrap {
    max-height: none;
  }
}

.action-plan-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.action-plan-card__header h4 {
  margin: 0 0 0.35rem 0;
  font-size: 1.1rem;
  color: var(--heading);
}

.action-plan-summary {
  margin: 0;
  color: var(--secondary-text);
  line-height: 1.5;
}

.action-plan-list {
  display: grid;
  gap: 0.75rem;
}

.action-plan-item {
  padding: 0.9rem 1rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
}

.action-plan-item__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.action-plan-item__top h5 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
  color: var(--heading);
}

.action-plan-item__desc {
  margin: 0;
  color: var(--secondary-text);
  line-height: 1.5;
}

.action-plan-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  font-size: 0.85rem;
  color: var(--secondary-text);
}

.badge--muted {
  background: var(--surface-3);
  color: var(--secondary-text);
}

.action-plan-empty {
  padding-top: 1rem;
}

.placeholder {
  color: var(--secondary-text);
  font-style: italic;
  margin: 0;
  padding: 2rem;
  text-align: center;
}

.roadmap-panel {
  text-align: center;
  padding: 3rem 2rem;
}

.reveal {
  animation: fadeInUp 0.6s ease-out forwards;
  opacity: 0;
}

.reveal--delay-1 {
  animation-delay: 0.1s;
}

.reveal--delay-2 {
  animation-delay: 0.2s;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .goals-list {
    max-height: none;
    overflow: visible;
  }

  .goal-detail {
    max-height: none;
    overflow: visible;
  }
}

@media (max-width: 768px) {
  .detail-actions {
    width: 100%;
    flex-direction: column;
  }

  .btn--sm {
    width: 100%;
  }

  .goal-cards {
    grid-template-columns: 1fr;
  }

  .action-plan-card__header,
  .action-plan-item__top {
    flex-direction: column;
  }
}
</style>
