<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { createGoal, listGoals, getGoalDetail, refreshGoalBreakdown, deleteGoal, type Goal, type GoalDetail } from '../api/goals'
import { createActionPlan, getActionPlanDetail, listActionPlans, refreshActionPlan, deleteActionPlan, type ActionPlan, type ActionPlanDetail, type ActionPlanItem } from '../api/actionPlans'
import BreakdownNode from '../components/BreakdownNode.vue'

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
const pollingGoalId = ref<number | null>(null)
const errorMessage = ref('')

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
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to load goals'
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const loadActionPlans = async () => {
  try {
    actionPlans.value = await listActionPlans()
  } catch (error) {
    console.error(error)
  }
}

const pollGoalBreakdown = async (goalId: number) => {
  if (isPollingBreakdown.value && pollingGoalId.value === goalId) return

  isPollingBreakdown.value = true
  pollingGoalId.value = goalId

  const maxAttempts = 10
  const delayMs = 1500

  try {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const detail = await getGoalDetail(goalId)
      if (detail.breakdowns?.root_nodes?.length) {
        if (selectedGoal.value?.id === goalId || !selectedGoal.value) {
          selectedGoal.value = detail
        }
        return
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
  } catch (error) {
    console.error(error)
  } finally {
    isPollingBreakdown.value = false
    pollingGoalId.value = null
  }
}

// Load goal detail
const selectGoal = async (goal: Goal) => {
  try {
    isLoading.value = true
    const detail = await getGoalDetail(goal.id)
    selectedGoal.value = detail
    if (!detail.breakdowns?.root_nodes?.length) {
      void pollGoalBreakdown(goal.id)
    }
    await loadActionPlanForGoal(goal.id)
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to load goal details'
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const upsertActionPlanSummary = (detail: ActionPlanDetail) => {
  const summary: ActionPlan = {
    id: detail.id,
    goal_id: detail.goal_id,
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

  const goalIndex = actionPlans.value.findIndex((plan) => plan.goal_id === summary.goal_id)
  if (goalIndex >= 0) {
    actionPlans.value.splice(goalIndex, 1, summary)
    return
  }

  actionPlans.value.unshift(summary)
}

const loadActionPlanForGoal = async (goalId: number) => {
  const summary = actionPlans.value.find((plan) => plan.goal_id === goalId)
  if (!summary) {
    selectedActionPlan.value = null
    return
  }

  try {
    isActionPlanFetching.value = true
    selectedActionPlan.value = await getActionPlanDetail(summary.id)
    errorMessage.value = ''
  } catch (error) {
    selectedActionPlan.value = null
    errorMessage.value = 'Failed to load action plan details'
    console.error(error)
  } finally {
    isActionPlanFetching.value = false
  }
}

const handleGenerateActionPlan = async () => {
  if (!selectedGoal.value) return

  try {
    isActionPlanBusy.value = true
    const detail = await createActionPlan({ goal_id: selectedGoal.value.id })
    selectedActionPlan.value = detail
    upsertActionPlanSummary(detail)
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to generate action plan'
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
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to refresh action plan'
    console.error(error)
  } finally {
    isActionPlanBusy.value = false
  }
}

// Create goal
const handleCreateGoal = async () => {
  if (!formData.value.title.trim()) {
    errorMessage.value = 'Goal title is required'
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
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to create goal'
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
    // Reload goal detail
    await selectGoal(selectedGoal.value)
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to refresh breakdown'
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
    }
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to delete goal'
    console.error(error)
  }
}

const handleDeleteActionPlan = async () => {
  if (!selectedActionPlan.value) return

  try {
    await deleteActionPlan(selectedActionPlan.value.id)
    actionPlans.value = actionPlans.value.filter((plan) => plan.id !== selectedActionPlan.value?.id)
    selectedActionPlan.value = null
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = 'Failed to delete action plan'
    console.error(error)
  }
}

// Format date for display
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString()
}

// Computed
const hasGoals = computed(() => goals.value.length > 0)
const breakdownNodes = computed(() => selectedGoal.value?.breakdowns.root_nodes || [])
const actionPlanItems = computed<ActionPlanItem[]>(() => selectedActionPlan.value?.items || [])
const hasActionPlan = computed(() => Boolean(selectedActionPlan.value))

// Lifecycle
onMounted(() => {
  void Promise.all([loadGoals(), loadActionPlans()])
})
</script>

<template>
  <div class="page page--wide plan-page">
    <!-- Error Alert -->
    <div v-if="errorMessage" class="error-alert">
      {{ errorMessage }}
    </div>

    <!-- Header -->
    <section class="page-header glass-card panel hero-frame reveal">
      <p class="page-kicker">Growth Planning</p>
      <h1 class="page-title">Goals & Roadmap</h1>
      <p class="page-subtitle">
        Define your growth goals and let AI help break them down into actionable steps.
      </p>

      <div class="hero-actions">
        <button class="btn btn--primary" @click="showCreateForm = !showCreateForm" :disabled="isLoading">
          {{ showCreateForm ? 'Cancel' : '+ New Goal' }}
        </button>
      </div>
    </section>

    <!-- Create Form -->
    <section v-if="showCreateForm" class="panel create-form reveal">
      <h2 class="section-title">Create New Goal</h2>
      <form @submit.prevent="handleCreateGoal" class="form-grid">
        <div class="form-group">
          <label for="goal-title">Goal Title *</label>
          <input id="goal-title" v-model="formData.title" type="text" placeholder="e.g., Learn Web Development"
            required />
        </div>

        <div class="form-group">
          <label for="goal-description">Description</label>
          <textarea id="goal-description" v-model="formData.description" placeholder="Describe your goal in detail..."
            rows="4" />
        </div>

        <div class="form-group form-group--half">
          <label for="goal-priority">Priority</label>
          <select id="goal-priority" v-model="formData.priority">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div class="form-group form-group--half">
          <label for="goal-target-date">Target Date</label>
          <input id="goal-target-date" v-model="formData.target_date" type="date" />
        </div>

        <button type="submit" class="btn btn--primary btn--full" :disabled="isLoading">
          {{ isLoading ? 'Creating...' : 'Create Goal' }}
        </button>
      </form>
    </section>

    <!-- Goals Layout -->
    <div v-if="hasGoals" class="goals-container">
      <!-- Goals List -->
      <section class="goals-list reveal">
        <h2 class="section-title">Your Goals</h2>
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

      <!-- Goal Detail & Breakdown -->
      <section v-if="selectedGoal" class="goal-detail reveal">
        <div class="detail-header">
          <h2>{{ selectedGoal.title }}</h2>
          <div class="detail-actions">
            <button class="btn btn--secondary btn--sm" @click="handleRefreshBreakdown" :disabled="isRefreshing">
              {{ isRefreshing ? 'Refreshing...' : '🔄 Refresh' }}
            </button>
            <button class="btn btn--danger btn--sm" @click="handleDeleteGoal(selectedGoal.id)">
              🗑️ Delete
            </button>
          </div>
        </div>

        <p v-if="selectedGoal.description" class="detail-description">
          {{ selectedGoal.description }}
        </p>

        <div class="detail-meta">
          <span>Status: <strong>{{ selectedGoal.status }}</strong></span>
          <span>Priority: <strong>{{ selectedGoal.priority }}</strong></span>
          <span v-if="selectedGoal.target_date">
            Target: <strong>{{ formatDate(selectedGoal.target_date) }}</strong>
          </span>
        </div>

        <!-- Breakdown Tree -->
        <div class="breakdown-section">
          <h3 class="breakdown-title">Goal Breakdown</h3>
          <div v-if="breakdownNodes.length > 0" class="breakdown-tree">
            <BreakdownNode v-for="node in breakdownNodes" :key="node.id" :node="node" />
          </div>
          <p v-else class="placeholder">
            AI is generating your action plan. Please refresh in a moment.
          </p>
        </div>

        <!-- Action Plan -->
        <div class="action-plan-section">
          <div class="section-row">
            <h3 class="breakdown-title">Action Plan</h3>
            <div class="detail-actions">
              <button v-if="selectedGoal" class="btn btn--secondary btn--sm"
                @click="hasActionPlan ? handleRefreshActionPlan() : handleGenerateActionPlan()"
                :disabled="isActionPlanBusy || isActionPlanFetching">
                {{ isActionPlanBusy ? 'Processing...' : hasActionPlan ? '🔄 Refresh Plan' : '✨ Generate Plan' }}
              </button>
              <button v-if="selectedActionPlan" class="btn btn--danger btn--sm" @click="handleDeleteActionPlan"
                :disabled="isActionPlanBusy">
                🗑️ Remove Plan
              </button>
            </div>
          </div>

          <div v-if="isActionPlanFetching" class="placeholder">
            Loading action plan...
          </div>
          <div v-else-if="selectedActionPlan" class="action-plan-card">
            <div class="action-plan-card__header">
              <div>
                <h4>{{ selectedActionPlan.title }}</h4>
                <p v-if="selectedActionPlan.summary" class="action-plan-summary">
                  {{ selectedActionPlan.summary }}
                </p>
              </div>
              <span class="status-badge">{{ selectedActionPlan.status }}</span>
            </div>

            <div v-if="actionPlanItems.length > 0" class="action-plan-list">
              <article v-for="item in actionPlanItems" :key="item.id" class="action-plan-item">
                <div class="action-plan-item__top">
                  <div>
                    <h5>{{ item.title }}</h5>
                    <p v-if="item.description" class="action-plan-item__desc">
                      {{ item.description }}
                    </p>
                  </div>
                  <span class="badge badge--muted">{{ item.frequency }}</span>
                </div>

                <div class="action-plan-item__meta">
                  <span>Status: <strong>{{ item.status }}</strong></span>
                  <span v-if="item.start_date">Start: <strong>{{ formatDate(item.start_date) }}</strong></span>
                  <span v-if="item.due_date">Due: <strong>{{ formatDate(item.due_date) }}</strong></span>
                  <span v-if="item.schedule">Schedule: <strong>{{ item.schedule }}</strong></span>
                  <span v-if="item.breakdown_id">Breakdown ID: <strong>#{{ item.breakdown_id }}</strong></span>
                </div>
              </article>
            </div>

            <p v-else class="placeholder action-plan-empty">
              This plan is valid, but AI returned no items. Refresh to regenerate.
            </p>
          </div>
          <p v-else class="placeholder">
            Select a goal and generate an action plan to see a structured execution list here.
          </p>
        </div>
      </section>
    </div>

    <!-- Empty State -->
    <section v-else class="panel roadmap-panel reveal reveal--delay-2">
      <div class="title-row">
        <div>
          <p class="eyebrow">Getting Started</p>
          <h2 class="section-title">No goals yet</h2>
        </div>
      </div>

      <p class="placeholder">
        Create your first growth goal to get started. AI will help break it down into actionable steps.
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

.error-alert {
  background-color: #fee;
  border-left: 4px solid #f44;
  color: #d00;
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 4px;
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
  gap: 2rem;
}

.goals-list {
  display: flex;
  flex-direction: column;
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
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.detail-header h2 {
  margin: 0;
  color: var(--heading);
  font-size: 1.4rem;
}

.detail-actions {
  display: flex;
  gap: 0.5rem;
}

.detail-description {
  color: var(--secondary-text);
  margin-bottom: 1rem;
  line-height: 1.5;
}

.detail-meta {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}

.detail-meta span {
  color: var(--secondary-text);
}

.detail-meta strong {
  color: var(--heading);
}

.breakdown-section {
  margin-top: 1.5rem;
}

.action-plan-section {
  margin-top: 1.75rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}

.section-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.breakdown-title {
  font-size: 1.1rem;
  color: var(--heading);
  margin: 0 0 1rem 0;
}

.action-plan-card {
  display: grid;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-1);
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

.breakdown-tree {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.breakdown-node {
  padding: 0.75rem 0;
  border-left: 3px solid var(--accent-1);
  padding-left: 1rem;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.node-status {
  font-size: 0.6rem;
  color: var(--accent-1);
}

.node-status.status-in_progress {
  color: #ff9800;
}

.node-status.status-completed {
  color: #4caf50;
}

.node-title {
  font-weight: 500;
  color: var(--heading);
}

.node-description {
  margin: 0.25rem 0 0 0;
  color: var(--secondary-text);
  font-size: 0.95rem;
}

.node-children {
  margin-top: 0.5rem;
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

@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .section-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .detail-actions {
    width: 100%;
    flex-direction: column;
  }

  .btn--sm {
    width: 100%;
  }

  .detail-meta {
    gap: 1rem;
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
