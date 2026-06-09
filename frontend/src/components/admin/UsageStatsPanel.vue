<script lang="ts">
export default {
  name: 'UsageStatsPanel',
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

import type { UsageDetailEntry, UsageLogPeriod, UsageStatEntry } from '../../api/adminSystem'

const props = defineProps<{
  stats: UsageStatEntry[]
  userDetail?: UsageDetailEntry[] | null
  loading: boolean
  period: UsageLogPeriod
  showControls?: boolean
  detailTitle?: string
  emptyHint?: string
}>()

const emit = defineEmits<{
  'update:period': [UsageLogPeriod]
  refresh: []
}>()

const showControls = computed(() => props.showControls !== false)
const detailTitle = computed(() => props.detailTitle ?? '用户明细')
const emptyHint = computed(
  () => props.emptyHint ?? '暂无使用量数据（AI 使用日志功能在 Phase 5 激活后生效）。',
)

function totalCalls(stats: UsageStatEntry[]) {
  return stats.reduce((sum, row) => sum + (row.calls || 0), 0)
}

function totalTokens(stats: UsageStatEntry[]) {
  return stats.reduce((sum, row) => sum + (row.total_tokens || 0), 0)
}

function onPeriodChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value as UsageLogPeriod
  emit('update:period', value)
}
</script>

<template>
  <div class="usage-stats-panel">
    <div v-if="showControls" class="log-controls usage-stats-panel__controls">
      <select class="input input--sm" :value="period" @change="onPeriodChange">
        <option value="today">今日</option>
        <option value="week">近 7 天</option>
        <option value="month">本月</option>
      </select>
      <slot name="filters" />
      <button class="button button--ghost" :disabled="loading" type="button" @click="emit('refresh')">
        刷新
      </button>
    </div>

    <div v-if="loading" class="hint-text">加载中…</div>

    <div v-else-if="stats.length > 0">
      <div class="stats-summary">
        <div class="stat-box">
          <p class="stat-box__label">总调用次数</p>
          <p class="stat-box__value">{{ totalCalls(stats) }}</p>
        </div>
        <div class="stat-box">
          <p class="stat-box__label">总 Token 用量</p>
          <p class="stat-box__value">{{ totalTokens(stats).toLocaleString() }}</p>
        </div>
      </div>

      <div class="table-scroll">
        <table class="data-table data-table--sm">
          <thead>
            <tr>
              <th>日期</th>
              <th>调用次数</th>
              <th>Prompt Tokens</th>
              <th>Completion Tokens</th>
              <th>总 Tokens</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats" :key="row.date_label">
              <td>{{ row.date_label }}</td>
              <td>{{ row.calls }}</td>
              <td>{{ row.prompt_tokens.toLocaleString() }}</td>
              <td>{{ row.completion_tokens.toLocaleString() }}</td>
              <td>{{ row.total_tokens.toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="userDetail && userDetail.length > 0" class="user-detail">
        <p class="eyebrow usage-stats-panel__detail-title">{{ detailTitle }}</p>
        <div class="table-scroll">
          <table class="data-table data-table--sm">
            <thead>
              <tr>
                <th>日期</th>
                <th>模型</th>
                <th>任务</th>
                <th>调用</th>
                <th>Prompt</th>
                <th>Completion</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in userDetail" :key="index">
                <td>{{ row.day }}</td>
                <td>{{ row.model }}</td>
                <td>{{ row.task || '—' }}</td>
                <td>{{ row.calls }}</td>
                <td>{{ (row.prompt_tokens || 0).toLocaleString() }}</td>
                <td>{{ (row.completion_tokens || 0).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <p v-else class="hint-text">{{ emptyHint }}</p>
  </div>
</template>

<style scoped>
.usage-stats-panel {
  display: grid;
  gap: 0.75rem;
}

.usage-stats-panel__controls {
  justify-content: flex-end;
}

.usage-stats-panel__detail-title {
  margin-top: 1.5rem;
}

.hint-text {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.stats-summary {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.stat-box {
  flex: 1;
  min-width: 160px;
  padding: 1rem 1.2rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: var(--surface);
}

.stat-box__label {
  margin: 0 0 0.25rem;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.stat-box__value {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--heading);
}

.log-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.input--sm {
  max-width: 160px;
}

.table-scroll {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th,
.data-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid var(--table-row-border);
  text-align: left;
}

.data-table th {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--label-text);
  background: var(--surface);
}

.data-table--sm th,
.data-table--sm td {
  padding: 0.4rem 0.6rem;
  font-size: 0.82rem;
}
</style>
