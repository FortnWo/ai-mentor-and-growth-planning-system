<script lang="ts">
export default {
  name: 'ModuleDashboardTree',
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

import type { ModuleMetric } from '../composables/useHomeDashboard'

const props = defineProps<{
  kicker: string
  title: string
  subtitle: string
  metrics: ModuleMetric[]
  loading: boolean
  error: boolean
  expanded: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const hasMetrics = computed(() => props.metrics.length > 0)

const hintText = computed(() =>
  props.expanded ? '点击收起本模块数据' : '点击展开本模块功能汇总',
)

function onToggle() {
  emit('toggle')
}
</script>

<template>
  <div
    class="path-node path-node--branch path-node--root"
    :class="{ 'path-node--expanded': expanded }"
  >
    <div class="path-node__trunk">
      <div
        class="path-node__body"
        role="button"
        tabindex="0"
        :aria-expanded="expanded"
        @click="onToggle"
        @keydown.enter.prevent="onToggle"
        @keydown.space.prevent="onToggle"
      >
        <div class="path-node__title-row">
          <span class="path-node__dot path-node__dot--main" aria-hidden="true" />
          <div class="path-node__heading">
            <p class="path-node__kicker">{{ kicker }}</p>
            <h3 class="path-node__title">{{ title }}</h3>
          </div>
          <span class="path-node__status">功能汇总</span>
        </div>
        <p class="path-node__desc">{{ subtitle }}</p>
        <p class="path-node__hint">{{ hintText }}</p>
      </div>
    </div>

    <div v-if="hasMetrics || loading" class="path-node__children">
      <div class="path-node__children-inner">
        <p v-if="loading" class="path-node__loading">加载中…</p>
        <template v-else>
          <div
            v-for="(metric, index) in metrics"
            :key="`${metric.label}-${index}`"
            class="path-node path-node--nested"
          >
          <div class="path-node__trunk">
            <span class="path-node__connector" aria-hidden="true" />
            <div class="path-node__body">
              <div class="path-node__title-row">
                <span class="path-node__dot path-node__dot--metric" aria-hidden="true">●</span>
                <h4 class="path-node__title path-node__title--metric">{{ metric.label }}</h4>
                <span class="path-node__value">{{ error ? '—' : metric.value }}</span>
              </div>
            </div>
          </div>
          </div>
        </template>
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

.path-node--root {
  border: none;
  background: transparent;
  border-radius: 0;
}

.path-node--nested {
  background: var(--surface-strong);
}

.path-node--expanded.path-node--root {
  border-color: transparent;
}

.path-node--root .path-node__body {
  cursor: pointer;
  border-radius: 12px;
}

.path-node--root .path-node__body:focus-visible {
  outline: 2px solid rgba(var(--accent-1-rgb), 0.55);
  outline-offset: 2px;
}

.path-node--expanded > .path-node__children {
  max-height: 2800px;
  opacity: 1;
  pointer-events: auto;
  padding-top: 0.55rem;
}

.path-node__trunk {
  display: flex;
  gap: 0.35rem;
  align-items: stretch;
  padding: 0.15rem 0 0.65rem;
}

.path-node--nested .path-node__trunk {
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
  align-items: flex-start;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.path-node__dot--main {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  margin-top: 0.45rem;
  flex-shrink: 0;
  background: linear-gradient(135deg, rgba(var(--accent-1-rgb), 0.95), rgba(var(--accent-2-rgb), 0.75));
}

.path-node__dot--metric {
  font-size: 0.55rem;
  line-height: 1;
  color: var(--text-muted);
  margin-top: 0.35rem;
}

.path-node__heading {
  flex: 1;
  min-width: 0;
}

.path-node__kicker {
  margin: 0 0 0.15rem;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.path-node__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--heading);
  flex: 1;
  min-width: 0;
}

.path-node__title--metric {
  font-family: inherit;
  font-size: 0.92rem;
  font-weight: 600;
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
  margin-top: 0.15rem;
}

.path-node__value {
  margin-top: 0.1rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--heading);
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: var(--chip-bg);
  border: 1px solid var(--border);
  max-width: 100%;
  word-break: break-word;
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

.path-node__children {
  border-top: 1px dashed var(--border);
  padding: 0 0 0.65rem;
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

.path-node__loading {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
