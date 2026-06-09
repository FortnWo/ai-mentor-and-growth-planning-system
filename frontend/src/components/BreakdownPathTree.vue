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
    mainNodeIds?: number[]
  }>(),
  {
    progressByMainId: () => ({}),
    selectedMainId: null,
    mainNodeIds: () => [],
  },
)

const emit = defineEmits<{
  'select-main': [id: number]
}>()

</script>

<template>
  <div class="breakdown-path-tree">
    <BreakdownPathNode
      v-for="node in nodes"
      :key="node.id"
      :node="node"
      :depth="0"
      :progress-by-main-id="progressByMainId"
      :selected-main-id="selectedMainId"
      :main-node-ids="mainNodeIds"
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
