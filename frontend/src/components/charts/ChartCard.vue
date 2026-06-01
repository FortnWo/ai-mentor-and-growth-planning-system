<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="chart-card">
    <h3 class="chart-title">{{ title }}</h3>
    <p v-if="description" class="chart-desc">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.chart-card {
  padding: 0.75rem 0.25rem 0;
  border-radius: var(--radius-md, 14px);
  background: rgba(248, 250, 252, 0.75);
  border: 1px solid var(--table-row-border, rgba(15, 23, 42, 0.06));
}

[data-theme='dark'] .chart-card {
  background: rgba(15, 23, 42, 0.35);
}

.chart-title {
  margin: 0 0 0.35rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--heading);
}

.chart-desc {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.45;
}
</style>
