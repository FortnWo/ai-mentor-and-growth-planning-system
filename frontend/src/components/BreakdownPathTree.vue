<script lang="ts">
export default {
  name: 'BreakdownPathTree',
}
</script>

<script setup lang="ts">
import type { GoalBreakdownNode } from '../api/goals'
import BreakdownPathNode from './BreakdownPathNode.vue'

const props = withDefaults(
  defineProps<{
    nodes: GoalBreakdownNode[]
    progressByMainId?: Record<number, { total: number; done: number }>
    selectedMainId?: number | null
  }>(),
  {
    progressByMainId: () => ({}),
    selectedMainId: null,
  },
)

const emit = defineEmits<{
  'select-main': [id: number]
}>()

function progressFor(node: GoalBreakdownNode) {
  return props.progressByMainId[node.id] ?? null
}
</script>

<template>
  <div class="breakdown-path-tree">
    <BreakdownPathNode
      v-for="node in nodes"
      :key="node.id"
      :node="node"
      :depth="0"
      :plan-progress="progressFor(node)"
      :selected-main-id="selectedMainId"
      @select-main="(id) => emit('select-main', id)"
    />
  </div>
</template>

<style scoped>
.breakdown-path-tree {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
