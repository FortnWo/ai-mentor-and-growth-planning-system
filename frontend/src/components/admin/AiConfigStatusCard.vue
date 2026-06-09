<script lang="ts">
export default {
  name: 'AiConfigStatusCard',
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  model: string | null
  baseUrl: string | null
  keyMasked: string | null
  keySet: boolean
}>()

const modelDisplay = computed(() => props.model?.trim() || '未设置')
const keyDisplay = computed(() => (props.keySet && props.keyMasked ? props.keyMasked : '未设置'))
const baseUrlDisplay = computed(() => props.baseUrl?.trim() || '未设置')
</script>

<template>
  <div class="panel ai-status-card">
    <div class="title-row">
      <div>
        <p class="eyebrow">当前连接</p>
        <h3 class="section-title section-title--sm">活跃 LLM 配置</h3>
      </div>
      <span v-if="keySet" class="chip chip--active">已配置</span>
      <span v-else class="chip chip--warn">未配置</span>
    </div>

    <dl class="status-list">
      <div class="status-list__row">
        <dt>Model</dt>
        <dd>{{ modelDisplay }}</dd>
      </div>
      <div class="status-list__row">
        <dt>API Key</dt>
        <dd class="status-list__mono">{{ keyDisplay }}</dd>
      </div>
      <div class="status-list__row">
        <dt>Base URL</dt>
        <dd class="status-list__mono status-list__truncate">{{ baseUrlDisplay }}</dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.ai-status-card {
  display: grid;
  gap: 0.75rem;
}

.section-title--sm {
  font-size: 1.05rem;
}

.status-list {
  margin: 0;
  display: grid;
  gap: 0.65rem;
}

.status-list__row {
  display: grid;
  gap: 0.2rem;
}

.status-list dt {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--label-text);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.status-list dd {
  margin: 0;
  font-size: 0.92rem;
  color: var(--heading);
  word-break: break-all;
}

.status-list__mono {
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
}

.status-list__truncate {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
