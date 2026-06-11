<script lang="ts">
export default {
  name: 'AiConfigStatusCard',
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

import type { LlmConfigSource } from '../../api/adminSystem'

const props = defineProps<{
  model: string | null
  baseUrl: string | null
  keyMasked: string | null
  keySet: boolean
  configSource?: LlmConfigSource
}>()

const modelDisplay = computed(() => props.model?.trim() || '未设置')
const keyDisplay = computed(() => (props.keySet && props.keyMasked ? props.keyMasked : '未设置'))
const baseUrlDisplay = computed(() => props.baseUrl?.trim() || '未设置')

const hasEnvLockedFields = computed(() => {
  const source = props.configSource
  if (!source) return false
  return (
    source.llm_api_key === 'env'
    || source.llm_api_base_url === 'env'
    || source.llm_model === 'env'
  )
})

function sourceLabel(field: keyof LlmConfigSource): string | null {
  const source = props.configSource?.[field]
  if (source === 'env') return '环境变量'
  if (source === 'db') return '面板'
  return null
}
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

    <p v-if="hasEnvLockedFields" class="env-lock-hint">
      部分字段已由环境变量配置，面板修改不会覆盖运行时行为。
    </p>

    <dl class="status-list">
      <div class="status-list__row">
        <dt>
          Model
          <span v-if="sourceLabel('llm_model')" class="source-tag">{{ sourceLabel('llm_model') }}</span>
        </dt>
        <dd>{{ modelDisplay }}</dd>
      </div>
      <div class="status-list__row">
        <dt>
          API Key
          <span v-if="sourceLabel('llm_api_key')" class="source-tag">{{ sourceLabel('llm_api_key') }}</span>
        </dt>
        <dd class="status-list__mono">{{ keyDisplay }}</dd>
      </div>
      <div class="status-list__row">
        <dt>
          Base URL
          <span v-if="sourceLabel('llm_api_base_url')" class="source-tag">{{ sourceLabel('llm_api_base_url') }}</span>
        </dt>
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

.env-lock-hint {
  margin: 0;
  padding: 0.55rem 0.7rem;
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--label-text);
  background: color-mix(in srgb, var(--accent, #6366f1) 8%, transparent);
  border-radius: 0.45rem;
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
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.source-tag {
  font-size: 0.68rem;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  background: color-mix(in srgb, var(--heading) 8%, transparent);
  color: var(--label-text);
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
