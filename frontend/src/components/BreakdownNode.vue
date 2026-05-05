<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'BreakdownNode',
})
</script>

<script setup lang="ts">
import type { GoalBreakdownNode } from '../api/goals'

defineProps<{
  node: GoalBreakdownNode
}>()
</script>

<template>
  <div class="breakdown-node" :style="{ marginLeft: (node.level * 1.5) + 'rem' }">
    <div class="node-header">
      <span class="node-status" :class="'status-' + node.status">●</span>
      <span class="node-title">{{ node.title }}</span>
    </div>
    <p v-if="node.description" class="node-description">
      {{ node.description }}
    </p>
    <div class="node-children">
      <BreakdownNode v-for="child in node.children" :key="child.id" :node="child" />
    </div>
  </div>
</template>
