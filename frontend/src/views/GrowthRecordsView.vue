<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
    createGrowthRecord,
    generateWeeklySummary,
    getGrowthDailyTrend,
    getGrowthStats,
    listGrowthRecords,
    type GrowthDailyTrendPoint,
} from '../api/growthRecords'
import AppEChart from '../components/charts/AppEChart.vue'
import ChartCard from '../components/charts/ChartCard.vue'
import { useChartTheme } from '../composables/useChartTheme'
import { authState, refreshCurrentUser } from '../stores/auth'
import { getApiErrorMessage } from '../utils/apiError'
import { formatLocalDate } from '../utils/localDate'
import { buildGrowthBarOption, buildGrowthLineOption } from '../utils/growthTrendChartOptions'

const records = ref([] as any[])
const loading = ref(false)
const feedback = ref('')
const summaryFeedback = ref('')
const listError = ref('')
const formError = ref('')
const summaryError = ref('')
const statsError = ref('')

const form = reactive({ title: '', summary: '' })

const trendGranularity = ref<'week' | 'month'>('week')
const trendPoints = ref<GrowthDailyTrendPoint[]>([])
const trendLoading = ref(false)
const trendError = ref('')

const rangeStats = ref({
    completed_count: 0,
    reflection_count: 0,
    milestone_count: 0,
    growth_score: 0,
    consecutive_days: 0,
})

const { tokens } = useChartTheme()

function clearListError() {
    listError.value = ''
}

function clearTrendError() {
    trendError.value = ''
}

function clearFormError() {
    formError.value = ''
}

function clearSummaryError() {
    summaryError.value = ''
}

function clearStatsError() {
    statsError.value = ''
}

function rangeForTrend() {
    const end = new Date()
    const start = new Date(end)
    const back = trendGranularity.value === 'week' ? 6 : 29
    start.setDate(end.getDate() - back)
    return {
        start_date: formatLocalDate(start),
        end_date: formatLocalDate(end),
    }
}

function isTrendPeriodEmpty(points: GrowthDailyTrendPoint[]): boolean {
    if (points.length === 0) return true
    return points.every(
        (p) =>
            (p.completed_count ?? 0) === 0 &&
            (p.reflection_count ?? 0) === 0 &&
            (p.milestone_count ?? 0) === 0 &&
            (p.growth_score ?? 0) === 0,
    )
}

const trendPeriodEmpty = computed(
    () => !trendLoading.value && !trendError.value && isTrendPeriodEmpty(trendPoints.value),
)

const showTrendEmptyHint = computed(() => trendPeriodEmpty.value && records.value.length > 0)

async function reloadTrendData() {
    clearTrendError()
    clearStatsError()
    await loadTrend()
    await loadRangeStats()
}

const trendRangeLabel = computed(() => {
    const { start_date, end_date } = rangeForTrend()
    return `${start_date} ～ ${end_date}`
})

const lineOption = computed(() => buildGrowthLineOption(trendPoints.value, tokens.value))

const barOption = computed(() =>
    buildGrowthBarOption(trendPoints.value, tokens.value, {
        rotateLabels: trendGranularity.value === 'month',
    }),
)

async function loadTrend() {
    trendLoading.value = true
    trendError.value = ''
    try {
        const q = rangeForTrend()
        trendPoints.value = await getGrowthDailyTrend(q)
    } catch (err) {
        trendPoints.value = []
        trendError.value = getApiErrorMessage(err, '趋势数据加载失败。')
    } finally {
        trendLoading.value = false
    }
}

async function loadRangeStats() {
    try {
        const q = rangeForTrend()
        const data = await getGrowthStats(q)
        clearStatsError()
        rangeStats.value = {
            completed_count: data.completed_count ?? 0,
            reflection_count: data.reflection_count ?? 0,
            milestone_count: data.milestone_count ?? 0,
            growth_score: data.growth_score ?? 0,
            consecutive_days: data.consecutive_days ?? 0,
        }
    } catch (err) {
        rangeStats.value = {
            completed_count: 0,
            reflection_count: 0,
            milestone_count: 0,
            growth_score: 0,
            consecutive_days: 0,
        }
        statsError.value = getApiErrorMessage(err, '周期统计加载失败。')
    }
}

async function load() {
    loading.value = true
    listError.value = ''
    try {
        const items = await listGrowthRecords({ limit: 20 })
        records.value = items
    } catch (err) {
        records.value = []
        listError.value = getApiErrorMessage(err, '成长记录列表加载失败。')
    } finally {
        loading.value = false
    }
}

async function submit() {
    clearFormError()
    feedback.value = ''
    try {
        const payload = {
            title: form.title.trim() || '记录一个小胜利',
            summary: form.summary.trim() || undefined,
            idempotency_key: `ui-${Date.now()}`,
        }
        await createGrowthRecord(payload)
        feedback.value = '已记录今天的小胜利 🎉'
        form.title = ''
        form.summary = ''
        await load()
        await loadTrend()
        await loadRangeStats()
    } catch (err) {
        feedback.value = ''
        formError.value = getApiErrorMessage(err, '记录失败，请稍后重试。')
    }
}

async function triggerWeeklySummary() {
    clearSummaryError()
    summaryFeedback.value = ''
    try {
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - 6)
        await generateWeeklySummary({
            start_date: formatLocalDate(start),
            end_date: formatLocalDate(end),
        })
        summaryFeedback.value = '已触发周总结生成（后台），稍后可在「周总结」查看或刷新。'
    } catch (err) {
        summaryError.value = getApiErrorMessage(err, '触发周总结失败。')
    }
}

watch(trendGranularity, async () => {
    clearTrendError()
    clearStatsError()
    await loadTrend()
    await loadRangeStats()
})

onMounted(async () => {
    if (!authState.user) {
        await refreshCurrentUser()
    }
    await load()
    await loadTrend()
    await loadRangeStats()
})
</script>

<template>
    <div class="page page--wide growth-page">
        <section class="page-header glass-card panel hero-frame">
            <div class="title-row">
                <div>
                    <p class="page-kicker">成长记录</p>
                    <h1 class="page-title">记录你的每一次小进步</h1>
                    <p class="page-subtitle">鼓励温暖的文字，让成长的轨迹更清晰。</p>
                </div>
            </div>
        </section>

        <div v-if="listError" class="error-banner" role="alert">
            <p class="feedback feedback--error error-banner__text">{{ listError }}</p>
            <button type="button" class="button button--ghost error-banner__dismiss" @click="clearListError">关闭</button>
        </div>

        <section class="panel trend-panel">
            <div class="trend-header">
                <div>
                    <h2 class="section-title">成长趋势</h2>
                    <p class="trend-hint">{{ trendRangeLabel }} · 预估学习投入按记录类型与积分折算分钟，仅供趋势参考。</p>
                </div>
                <div class="segmented" role="tablist">
                    <button
                        type="button"
                        class="seg-btn"
                        :class="{ 'seg-btn--active': trendGranularity === 'week' }"
                        @click="trendGranularity = 'week'"
                    >
                        按周
                    </button>
                    <button
                        type="button"
                        class="seg-btn"
                        :class="{ 'seg-btn--active': trendGranularity === 'month' }"
                        @click="trendGranularity = 'month'"
                    >
                        按月
                    </button>
                </div>
            </div>

            <div class="stat-strip">
                <div class="stat-chip">
                    <span class="stat-label">计划完成</span>
                    <span class="stat-value">{{ rangeStats.completed_count }}</span>
                </div>
                <div class="stat-chip">
                    <span class="stat-label">反思记录</span>
                    <span class="stat-value">{{ rangeStats.reflection_count }}</span>
                </div>
                <div class="stat-chip">
                    <span class="stat-label">里程碑</span>
                    <span class="stat-value">{{ rangeStats.milestone_count }}</span>
                </div>
                <div class="stat-chip">
                    <span class="stat-label">成长积分</span>
                    <span class="stat-value">{{ rangeStats.growth_score }}</span>
                </div>
                <div class="stat-chip">
                    <span class="stat-label">连续活跃</span>
                    <span class="stat-value">{{ rangeStats.consecutive_days }} 天</span>
                </div>
            </div>

            <div v-if="statsError" class="stats-error" role="alert">
                <span class="feedback feedback--error feedback--compact">{{ statsError }}</span>
                <button type="button" class="button button--ghost stats-error__dismiss" @click="clearStatsError">关闭</button>
            </div>

            <p v-if="trendLoading" class="muted">图表加载中…</p>
            <div v-else-if="trendError" class="trend-error-row" role="alert">
                <p class="feedback feedback--error trend-error-row__text">{{ trendError }}</p>
                <button type="button" class="button button--ghost" @click="clearTrendError">关闭</button>
            </div>

            <p v-if="showTrendEmptyHint" class="trend-empty-hint muted" role="status">
                当前周期（{{ trendRangeLabel }}）内暂无统计数据；时间线中的记录可能落在其他日期。
                <button type="button" class="button button--ghost trend-empty-hint__retry" @click="reloadTrendData">
                    重试加载
                </button>
            </p>

            <div v-if="!trendLoading && !trendError" class="charts-grid">
                <ChartCard title="计划执行与累计完成" description="折线展示每日行动计划完成、里程碑，以及本周期内行动计划累计完成件数。">
                    <AppEChart :key="`${trendRangeLabel}-line`" :option="lineOption" />
                </ChartCard>
                <ChartCard title="学习投入与积分" description="柱状对比「预估学习分钟」与当日累计成长积分（含自定义得分字段）。">
                    <AppEChart :key="`${trendRangeLabel}-bar`" :option="barOption" />
                </ChartCard>
            </div>
        </section>

        <div class="grid-2 growth-grid">
            <section class="panel form-card">
                <h2 class="section-title">记录一个小胜利</h2>
                <label class="field">
                    <span class="label">标题</span>
                    <input v-model="form.title" class="input" placeholder="比如：完成复习 30 分钟" />
                </label>
                <label class="field">
                    <span class="label">简短描述</span>
                    <textarea v-model="form.summary" class="textarea" rows="3" placeholder="写下你的感受或下一步"></textarea>
                </label>
                <div class="actions">
                    <button class="button button--primary" @click="submit">记录小胜利</button>
                    <button class="button button--ghost" @click="triggerWeeklySummary">生成本周总结</button>
                </div>
                <p v-if="formError" class="feedback feedback--error">{{ formError }}</p>
                <p v-if="feedback" class="feedback feedback--success">{{ feedback }}</p>
                <div v-if="summaryError" class="summary-error-row" role="alert">
                    <span class="feedback feedback--error summary-error-row__text">{{ summaryError }}</span>
                    <button type="button" class="button button--ghost summary-error-row__dismiss" @click="clearSummaryError">关闭</button>
                </div>
                <p v-if="summaryFeedback" class="feedback feedback--muted">{{ summaryFeedback }}</p>
            </section>

            <section class="panel timeline-panel">
                <h2 class="section-title">时间线</h2>
                <div v-if="loading" class="muted">加载中…</div>
                <div v-else-if="records.length === 0" class="empty-state">
                    <p>还没有成长记录。试着记录一个小胜利，或者从行动计划中自动回写。</p>
                    <button
                        class="button button--ghost"
                        @click="form.title = '完成了练习题'; form.summary = '进步一点点，值得庆祝'; submit()"
                    >
                        写个示例
                    </button>
                </div>
                <div v-else class="records-viewport">
                    <ul class="record-list">
                        <li v-for="r in records" :key="r.id" class="record-item">
                            <h3>{{ r.title }}</h3>
                            <p class="muted">
                                {{ r.record_date ?? (r.occurred_at ? new Date(r.occurred_at).toLocaleString() : '') }}
                            </p>
                            <p v-if="r.summary">{{ r.summary }}</p>
                            <p v-if="r.ai_summary" class="muted">AI 摘要：{{ r.ai_summary }}</p>
                        </li>
                    </ul>
                </div>
            </section>
        </div>
    </div>
</template>

<style scoped>
.growth-page {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.error-banner {
    display: flex;
    align-items: flex-start;
    gap: 0.85rem;
    flex-wrap: wrap;
    margin: 0 0 1rem;
}

.error-banner__text {
    flex: 1;
    margin: 0;
    min-width: 12rem;
}

.error-banner__dismiss {
    flex-shrink: 0;
}

.growth-grid {
    align-items: start;
}

.stats-error {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0 0 0.75rem;
}

.feedback--compact {
    margin: 0;
    padding: 0.55rem 0.75rem;
    font-size: 0.88rem;
}

.stats-error__dismiss {
    font-size: 0.82rem;
    padding: 0.35rem 0.75rem;
}

.trend-error-row {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    flex-wrap: wrap;
    margin: 0 0 0.75rem;
}

.trend-error-row__text {
    flex: 1;
    margin: 0;
    min-width: 10rem;
}

.trend-empty-hint {
    margin: 0 0 0.75rem;
    line-height: 1.5;
}

.trend-empty-hint__retry {
    display: inline-block;
    margin-left: 0.35rem;
    font-size: 0.88rem;
    padding: 0.25rem 0.65rem;
    vertical-align: baseline;
}

.summary-error-row {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    flex-wrap: wrap;
    margin: 0.5rem 0 0;
}

.summary-error-row__text {
    flex: 1;
    margin: 0;
    min-width: 8rem;
}

.summary-error-row__dismiss {
    flex-shrink: 0;
    font-size: 0.82rem;
    padding: 0.35rem 0.75rem;
}

.timeline-panel {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    min-height: 0;
}

.records-viewport {
    max-height: min(56vh, 520px);
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 0.35rem;
    margin-top: 0.15rem;
    border-radius: var(--radius-md, 14px);
    border: 1px solid var(--table-row-border);
    background: rgba(248, 250, 252, 0.65);
}

[data-theme='dark'] .records-viewport {
    background: rgba(15, 23, 42, 0.35);
}

.trend-panel {
    margin-bottom: 1.25rem;
}

.trend-header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
}

.trend-hint {
    margin: 0.35rem 0 0;
    font-size: 0.85rem;
    color: var(--text-muted);
    max-width: 52ch;
    line-height: 1.45;
}

.segmented {
    display: inline-flex;
    padding: 3px;
    border-radius: var(--radius-md, 14px);
    background: var(--chip-bg);
    border: 1px solid var(--table-row-border);
}

.seg-btn {
    border: none;
    cursor: pointer;
    padding: 0.45rem 1rem;
    border-radius: var(--radius-sm, 10px);
    font: inherit;
    font-size: 0.9rem;
    color: var(--text-muted);
    background: transparent;
    transition: background 0.15s ease, color 0.15s ease;
}

.seg-btn--active {
    color: var(--heading);
    background: rgba(var(--accent-1-rgb), 0.12);
    box-shadow: 0 0 0 1px rgba(var(--accent-1-rgb), 0.22);
}

.stat-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-bottom: 1.25rem;
}

.stat-chip {
    padding: 0.55rem 0.85rem;
    border-radius: var(--radius-sm, 10px);
    background: var(--surface);
    border: 1px solid var(--table-row-border);
    min-width: 6.5rem;
}

.stat-label {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
}

.stat-value {
    font-family: var(--font-display, inherit);
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--heading);
}

.charts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.25rem;
}

.record-list {
    display: grid;
    gap: 0.8rem;
}

.record-item {
    padding: 0.8rem;
    border-bottom: 1px solid var(--table-row-border);
}

.empty-state {
    padding: 1rem 0;
}

.muted {
    color: var(--text-muted);
    font-size: 0.9rem;
}
</style>
