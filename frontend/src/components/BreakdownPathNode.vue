<script lang="ts">
export default {
  name: 'BreakdownPathNode',
}
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'

import type { GoalBreakdownNode } from '../api/goals'
import BreakdownPathNode from './BreakdownPathNode.vue'

const props = withDefaults(
  defineProps<{
    node: GoalBreakdownNode
    depth?: number
    progressByMainId?: Record<number, { total: number; done: number }>
    planStatusByMainId?: Record<number, { planId: number | null; status: string | null }>
    selectedMainId?: number | null
    mainNodeIds?: number[]
  }>(),
  {
    depth: 0,
    progressByMainId: () => ({}),
    planStatusByMainId: () => ({}),
    selectedMainId: null,
    mainNodeIds: () => [],
  },
)

const emit = defineEmits<{
  'select-main': [id: number]
}>()

const expanded = ref(false)

const hasChildren = computed(() => Boolean(props.node.children?.length))
const isMainSelectable = computed(() => {
  if (props.mainNodeIds.length > 0) {
    return props.mainNodeIds.includes(props.node.id)
  }
  return props.depth === 0
})
const isClickable = computed(() => isMainSelectable.value || hasChildren.value)

const statusLabel = computed(() => {
  const s = props.node.status || 'pending'
  if (s === 'completed') return '已完成'
  if (s === 'in_progress') return '进行中'
  if (s === 'failed') return '未按期完成'
  return '待开始'
})

const planProgress = computed(() => {
  if (!isMainSelectable.value) return null
  return props.progressByMainId[props.node.id] ?? null
})

const progressPercent = computed(() => {
  if (!planProgress.value || planProgress.value.total <= 0) return null
  return Math.round((planProgress.value.done / planProgress.value.total) * 100)
})

const planMeta = computed(() => {
  if (!isMainSelectable.value) return null
  return props.planStatusByMainId[props.node.id] ?? null
})

const planItemTotal = computed(() => {
  if (!isMainSelectable.value) return 0
  return planProgress.value?.total ?? 0
})

const planItemDone = computed(() => {
  if (!isMainSelectable.value) return 0
  return planProgress.value?.done ?? 0
})

const planStatusLabel = computed(() => {
  const meta = planMeta.value
  if (!meta?.planId) return '待生成'

  const status = meta.status
  const total = planItemTotal.value
  const done = planItemDone.value

  if (status === 'failed') return '生成失败'
  if (status === 'completed' || (total > 0 && done === total)) return '已完成'
  if (status === 'in_progress' && total === 0) return '生成中'
  if (total > 0) {
    return done > 0 ? '执行中' : '已就绪'
  }
  if (status === 'pending' || status === 'in_progress') return '已就绪'
  return '待生成'
})

const planStatusClass = computed(() => {
  const meta = planMeta.value
  if (!meta?.planId) return 'path-node__plan-badge--pending'

  const status = meta.status
  const total = planItemTotal.value
  const done = planItemDone.value

  if (status === 'failed') return 'path-node__plan-badge--failed'
  if (status === 'completed' || (total > 0 && done === total)) return 'path-node__plan-badge--ready'
  if (status === 'in_progress' && total === 0) return 'path-node__plan-badge--generating'
  if (total > 0 && done > 0) return 'path-node__plan-badge--executing'
  if (total > 0 || status === 'pending' || status === 'in_progress') return 'path-node__plan-badge--ready'
  return 'path-node__plan-badge--pending'
})

const expandHintText = computed(() =>
  expanded.value ? '点击收起下级详情' : '点击展开下级详情',
)

function onBodyClick() {
  if (hasChildren.value) {
    expanded.value = !expanded.value
  }
  if (isMainSelectable.value) {
    emit('select-main', props.node.id)
  }
}
</script>

<template>
  <div
    class="path-node"
    :class="{
      'path-node--nested': depth > 0,
      'path-node--branch': hasChildren,
      'path-node--expanded': hasChildren && expanded,
      'path-node--main-selectable': isMainSelectable,
      'path-node--expandable': hasChildren && !isMainSelectable,
      'path-node--main-selected': isMainSelectable && selectedMainId === node.id,
    }"
  >
    <div class="path-node__trunk">
      <span v-if="depth > 0" class="path-node__connector" aria-hidden="true" />
      <div
        class="path-node__body"
        :role="isClickable ? 'button' : undefined"
        :tabindex="isClickable ? 0 : -1"
        :aria-expanded="hasChildren ? expanded : undefined"
        @click="onBodyClick"
        @keydown.enter.prevent="onBodyClick"
        @keydown.space.prevent="onBodyClick"
      >
        <div class="path-node__title-row">
          <span
            v-if="isMainSelectable"
            class="path-node__dot path-node__dot--main"
            aria-hidden="true"
          />
          <span
            v-else
            class="path-node__dot"
            :class="'path-node__dot--' + (node.status || 'pending')"
            aria-hidden="true"
          />
          <h4 class="path-node__title">{{ node.title }}</h4>
          <span v-if="isMainSelectable" class="path-node__plan-badge" :class="planStatusClass">
            <span
              v-if="planMeta?.planId && planMeta.status === 'in_progress' && planItemTotal === 0"
              class="path-node__plan-badge-dot"
              aria-hidden="true"
            />
            {{ planStatusLabel }}
          </span>
          <span class="path-node__status">{{ statusLabel }}</span>
        </div>
        <div v-if="isMainSelectable && progressPercent !== null" class="path-node__progress" aria-label="行动计划完成进度">
          <div class="path-node__progress-track">
            <div class="path-node__progress-fill" :style="{ width: progressPercent + '%' }" />
          </div>
          <span class="path-node__progress-label">{{ progressPercent }}%</span>
        </div>
        <p
          v-if="node.description"
          :class="['path-node__desc', hasChildren && depth > 0 ? 'path-node__desc--peek' : '']"
        >
          {{ node.description }}
        </p>
        <p v-if="isMainSelectable" class="path-node__hint">点击主节点在右侧查看该阶段的行动计划</p>
        <p v-else-if="depth === 0 && hasChildren" class="path-node__hint">展开查看各阶段主路径</p>
        <p v-if="hasChildren" class="path-node__hint">{{ expandHintText }}</p>
      </div>
    </div>

    <div v-if="hasChildren" class="path-node__children">
      <div class="path-node__children-inner">
        <BreakdownPathNode
          v-for="child in node.children"
          :key="child.id"
          :node="child"
          :depth="depth + 1"
          :main-node-ids="mainNodeIds"
          :progress-by-main-id="progressByMainId"
          :plan-status-by-main-id="planStatusByMainId"
          :selected-main-id="selectedMainId"
          @select-main="(id) => emit('select-main', id)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.path-node {
  position: relative;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.path-node--nested {
  background: var(--surface-strong);
}

.path-node--main-selectable .path-node__body,
.path-node--expandable .path-node__body {
  cursor: pointer;
  border-radius: 12px;
}

.path-node--main-selectable .path-node__body:focus-visible,
.path-node--expandable .path-node__body:focus-visible {
  outline: 2px solid rgba(var(--accent-1-rgb), 0.55);
  outline-offset: 2px;
}

.path-node--main-selected {
  border-color: rgba(var(--accent-1-rgb), 0.45);
  box-shadow: 0 8px 22px rgba(var(--accent-1-rgb), 0.12);
}

.path-node--branch.path-node--expanded {
  border-color: rgba(var(--accent-1-rgb), 0.35);
  box-shadow: 0 10px 28px rgba(var(--accent-1-rgb), 0.12);
}

.path-node__trunk {
  display: flex;
  gap: 0.35rem;
  align-items: stretch;
  padding: 0.75rem 0.85rem 0.65rem;
}

.path-node__connector {
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(var(--accent-1-rgb), 0.45), rgba(var(--accent-2-rgb), 0.2));
  flex-shrink: 0;
  margin-top: 0.2rem;
  margin-bottom: 0.2rem;
}

.path-node__body {
  flex: 1;
  min-width: 0;
}

.path-node__title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.path-node__dot {
  font-size: 0.55rem;
  line-height: 1;
  color: var(--text-muted);
}

.path-node__dot--main {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(var(--accent-1-rgb), 0.95), rgba(var(--accent-2-rgb), 0.75));
}

.path-node__dot--completed {
  color: var(--success);
}

.path-node__dot--in_progress {
  color: var(--warning);
}

.path-node__dot--failed {
  color: var(--danger);
}

.path-node__dot--pending {
  color: var(--text-muted);
}

.path-node__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--heading);
  flex: 1;
  min-width: 0;
}

.path-node__status {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: var(--chip-bg);
  border: 1px solid var(--border);
}

.path-node__plan-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--chip-bg);
  color: var(--text-muted);
}

.path-node__plan-badge--generating {
  color: var(--warning);
  border-color: rgba(var(--warning-rgb, 234, 179, 8), 0.35);
  background: rgba(var(--warning-rgb, 234, 179, 8), 0.08);
}

.path-node__plan-badge--ready,
.path-node__plan-badge--executing {
  color: var(--success);
  border-color: rgba(var(--success-rgb, 34, 197, 94), 0.35);
  background: rgba(var(--success-rgb, 34, 197, 94), 0.08);
}

.path-node__plan-badge--executing {
  color: var(--warning);
  border-color: rgba(var(--warning-rgb, 234, 179, 8), 0.35);
  background: rgba(var(--warning-rgb, 234, 179, 8), 0.08);
}

.path-node__plan-badge--failed {
  color: var(--danger);
  border-color: rgba(var(--danger-rgb, 239, 68, 68), 0.35);
  background: rgba(var(--danger-rgb, 239, 68, 68), 0.08);
}

.path-node__plan-badge-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: currentColor;
  animation: path-node-plan-pulse 1.2s ease-in-out infinite;
}

@keyframes path-node-plan-pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

.path-node__progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.path-node__progress-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--border);
  overflow: hidden;
}

.path-node__progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(var(--accent-1-rgb), 0.85), rgba(var(--accent-2-rgb), 0.75));
  transition: width 0.35s ease;
}

.path-node__progress-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  min-width: 2.5rem;
  text-align: right;
}

.path-node__desc {
  margin: 0.45rem 0 0;
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--text-muted);
}

.path-node__hint {
  margin: 0.4rem 0 0;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.path-node__desc--peek {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.path-node__children {
  border-top: 1px dashed var(--border);
  padding: 0 0.75rem 0.65rem;
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transition:
    max-height 0.38s ease,
    opacity 0.22s ease,
    padding-top 0.22s ease;
}

.path-node__children-inner {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding-left: 0.35rem;
  border-left: 2px solid rgba(var(--accent-1-rgb), 0.2);
  margin-left: 0.35rem;
}

.path-node--expanded > .path-node__children {
  max-height: 2800px;
  opacity: 1;
  pointer-events: auto;
  padding-top: 0.55rem;
}
</style>
