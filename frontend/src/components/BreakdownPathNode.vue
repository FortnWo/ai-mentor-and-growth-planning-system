<script lang="ts">
export default {
  name: 'BreakdownPathNode',
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

import type { GoalBreakdownNode } from '../api/goals'
import BreakdownPathNode from './BreakdownPathNode.vue'

const props = withDefaults(
  defineProps<{
    node: GoalBreakdownNode
    depth?: number
    planProgress?: { total: number; done: number } | null
    selectedMainId?: number | null
  }>(),
  { depth: 0, planProgress: null, selectedMainId: null },
)

const emit = defineEmits<{
  'select-main': [id: number]
}>()

const hasChildren = computed(() => Boolean(props.node.children?.length))
const isRoot = computed(() => props.depth === 0)

const statusLabel = computed(() => {
  const s = props.node.status || 'pending'
  if (s === 'completed') return '已完成'
  if (s === 'in_progress') return '进行中'
  if (s === 'failed') return '未按期完成'
  return '待开始'
})

const progressPercent = computed(() => {
  if (!isRoot.value || !props.planProgress || props.planProgress.total <= 0) return null
  return Math.round((props.planProgress.done / props.planProgress.total) * 100)
})

function onSelectMain() {
  if (!isRoot.value) return
  emit('select-main', props.node.id)
}
</script>

<template>
  <div
    class="path-node"
    :class="{
      'path-node--nested': depth > 0,
      'path-node--branch': hasChildren,
      'path-node--main-selectable': isRoot,
      'path-node--main-selected': isRoot && selectedMainId === node.id,
    }"
  >
    <div class="path-node__trunk">
      <span v-if="depth > 0" class="path-node__connector" aria-hidden="true" />
      <div
        class="path-node__body"
        role="button"
        :tabindex="isRoot ? 0 : -1"
        @click="onSelectMain"
        @keydown.enter.prevent="onSelectMain"
        @keydown.space.prevent="onSelectMain"
      >
        <div class="path-node__title-row">
          <span v-if="depth > 0" class="path-node__dot" :class="'path-node__dot--' + (node.status || 'pending')" aria-hidden="true" />
          <span v-else class="path-node__dot path-node__dot--main" aria-hidden="true" />
          <h4 class="path-node__title">{{ node.title }}</h4>
          <span class="path-node__status">{{ statusLabel }}</span>
        </div>
        <div v-if="isRoot && progressPercent !== null" class="path-node__progress" aria-label="行动计划完成进度">
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
        <p v-if="isRoot" class="path-node__hint">点击主节点在右侧查看该阶段的行动计划</p>
      </div>
    </div>

    <div v-if="hasChildren" class="path-node__children">
      <p class="path-node__children-hint">悬停本节点可展开下级详情</p>
      <div class="path-node__children-inner">
        <BreakdownPathNode
          v-for="child in node.children"
          :key="child.id"
          :node="child"
          :depth="depth + 1"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.path-node {
  position: relative;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.82);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.path-node--nested {
  background: rgba(248, 250, 252, 0.95);
}

.path-node--main-selectable .path-node__body {
  cursor: pointer;
  border-radius: 12px;
}

.path-node--main-selectable .path-node__body:focus-visible {
  outline: 2px solid rgba(8, 145, 178, 0.55);
  outline-offset: 2px;
}

.path-node--main-selected {
  border-color: rgba(8, 145, 178, 0.45);
  box-shadow: 0 8px 22px rgba(8, 145, 178, 0.12);
}

.path-node--branch:hover {
  border-color: rgba(8, 145, 178, 0.35);
  box-shadow: 0 10px 28px rgba(8, 145, 178, 0.12);
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
  background: linear-gradient(180deg, rgba(8, 145, 178, 0.45), rgba(37, 99, 235, 0.2));
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
  color: #94a3b8;
}

.path-node__dot--main {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.95), rgba(37, 99, 235, 0.75));
}

.path-node__dot--completed {
  color: #22c55e;
}

.path-node__dot--in_progress {
  color: #f59e0b;
}

.path-node__dot--failed {
  color: #ef4444;
}

.path-node__dot--pending {
  color: #94a3b8;
}

.path-node__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--heading, #0f172a);
  flex: 1;
  min-width: 0;
}

.path-node__status {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted, #64748b);
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.95);
  border: 1px solid rgba(15, 23, 42, 0.06);
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
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.path-node__progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(8, 145, 178, 0.85), rgba(37, 99, 235, 0.75));
  transition: width 0.35s ease;
}

.path-node__progress-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted, #64748b);
  min-width: 2.5rem;
  text-align: right;
}

.path-node__desc {
  margin: 0.45rem 0 0;
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--text-muted, #475569);
}

.path-node__hint {
  margin: 0.4rem 0 0;
  font-size: 0.72rem;
  color: var(--text-muted, #94a3b8);
}

.path-node__desc--peek {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.path-node__children-hint {
  margin: 0 0 0.4rem;
  font-size: 0.72rem;
  color: var(--text-muted, #94a3b8);
  letter-spacing: 0.02em;
}

.path-node__children {
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
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
  border-left: 2px solid rgba(8, 145, 178, 0.2);
  margin-left: 0.35rem;
}

.path-node--branch:hover > .path-node__children {
  max-height: 2800px;
  opacity: 1;
  pointer-events: auto;
  padding-top: 0.55rem;
}

@media (hover: none) {
  .path-node__children-hint {
    display: none;
  }

  .path-node__children {
    max-height: none;
    opacity: 1;
    overflow: visible;
    pointer-events: auto;
    padding-top: 0.55rem;
  }
}
</style>
