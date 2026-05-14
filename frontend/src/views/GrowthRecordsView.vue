<script setup lang="ts">
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import {
    createGrowthRecord,
    generateWeeklySummary,
    getGrowthDailyTrend,
    getGrowthStats,
    listGrowthRecords,
    type GrowthDailyTrendPoint,
} from '../api/growthRecords'
import { authState, refreshCurrentUser } from '../stores/auth'
import { getApiErrorMessage } from '../utils/apiError'

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

const lineRef = ref<HTMLDivElement | null>(null)
const barRef = ref<HTMLDivElement | null>(null)
const recordsViewportEl = ref<HTMLElement | null>(null)
let lineChart: ECharts | null = null
let barChart: ECharts | null = null

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

function scrollRecordsToLatest() {
    nextTick(() => {
        requestAnimationFrame(() => {
            const el = recordsViewportEl.value
            if (el) {
                el.scrollTop = 0
            }
        })
    })
}

function rangeForTrend() {
    const end = new Date()
    const start = new Date(end)
    const back = trendGranularity.value === 'week' ? 6 : 29
    start.setDate(end.getDate() - back)
    return {
        start_date: start.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
    }
}

const trendRangeLabel = computed(() => {
    const { start_date, end_date } = rangeForTrend()
    return `${start_date} ～ ${end_date}`
})

function estimateStudyMinutes(p: GrowthDailyTrendPoint) {
    return Math.round(p.completed_count * 25 + p.reflection_count * 15 + p.milestone_count * 20 + (p.growth_score || 0))
}

function baseChartTheme(): Pick<EChartsOption, 'backgroundColor' | 'textStyle'> {
    return {
        backgroundColor: 'transparent',
        textStyle: { color: '#334155', fontFamily: 'Inter, Segoe UI, sans-serif' },
    }
}

function buildLineOption(points: GrowthDailyTrendPoint[]): EChartsOption {
    const labels = points.map((p) => p.record_date.slice(5))
    const completed = points.map((p) => p.completed_count)
    const milestones = points.map((p) => p.milestone_count)
    let acc = 0
    const cumulative = points.map((p) => {
        acc += p.completed_count
        return acc
    })

    return {
        ...baseChartTheme(),
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['计划完成(日)', '里程碑(日)', '累计计划完成'],
            textStyle: { color: '#64748b' },
            bottom: 0,
        },
        grid: { left: 48, right: 56, top: 28, bottom: 64 },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: labels,
            axisLine: { lineStyle: { color: 'rgba(15,23,42,0.12)' } },
            axisLabel: { color: '#64748b' },
        },
        yAxis: [
            {
                type: 'value',
                name: '件/日',
                nameTextStyle: { color: '#64748b' },
                splitLine: { lineStyle: { color: 'rgba(15,23,42,0.06)' } },
                axisLabel: { color: '#64748b' },
            },
            {
                type: 'value',
                name: '累计件数',
                nameTextStyle: { color: '#64748b' },
                splitLine: { show: false },
                axisLabel: { color: '#64748b' },
            },
        ],
        series: [
            {
                name: '计划完成(日)',
                type: 'line',
                smooth: true,
                symbolSize: 6,
                data: completed,
                itemStyle: { color: '#06b6d4' },
                areaStyle: { color: 'rgba(6,182,212,0.12)' },
            },
            {
                name: '里程碑(日)',
                type: 'line',
                smooth: true,
                symbolSize: 6,
                data: milestones,
                itemStyle: { color: '#a855f7' },
            },
            {
                name: '累计计划完成',
                type: 'line',
                yAxisIndex: 1,
                smooth: true,
                symbolSize: 6,
                data: cumulative,
                itemStyle: { color: '#22c55e' },
            },
        ],
    }
}

function buildBarOption(points: GrowthDailyTrendPoint[]): EChartsOption {
    const labels = points.map((p) => p.record_date.slice(5))
    const minutes = points.map((p) => estimateStudyMinutes(p))
    const scores = points.map((p) => p.growth_score || 0)

    return {
        ...baseChartTheme(),
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['预估学习投入(分)', '成长积分'],
            textStyle: { color: '#64748b' },
            bottom: 0,
        },
        grid: { left: 48, right: 24, top: 28, bottom: 72 },
        xAxis: {
            type: 'category',
            data: labels,
            axisLine: { lineStyle: { color: 'rgba(15,23,42,0.12)' } },
            axisLabel: { color: '#64748b', rotate: trendGranularity.value === 'month' ? 35 : 0 },
        },
        yAxis: {
            type: 'value',
            name: '数值',
            nameTextStyle: { color: '#64748b' },
            splitLine: { lineStyle: { color: 'rgba(15,23,42,0.06)' } },
            axisLabel: { color: '#64748b' },
        },
        series: [
            {
                name: '预估学习投入(分)',
                type: 'bar',
                barMaxWidth: 22,
                data: minutes,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(6,182,212,0.95)' },
                        { offset: 1, color: 'rgba(37,99,235,0.35)' },
                    ]),
                },
            },
            {
                name: '成长积分',
                type: 'bar',
                barMaxWidth: 22,
                data: scores,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(34,197,94,0.9)' },
                        { offset: 1, color: 'rgba(34,197,94,0.2)' },
                    ]),
                },
            },
        ],
    }
}

function renderCharts() {
    const pts = trendPoints.value
    if (!lineRef.value || !barRef.value) return
    if (!lineChart) lineChart = echarts.init(lineRef.value)
    if (!barChart) barChart = echarts.init(barRef.value)
    lineChart.setOption(buildLineOption(pts), true)
    barChart.setOption(buildBarOption(pts), true)
}

function disposeCharts() {
    lineChart?.dispose()
    barChart?.dispose()
    lineChart = null
    barChart = null
}

function onResize() {
    lineChart?.resize()
    barChart?.resize()
}

async function loadTrend() {
    trendLoading.value = true
    trendError.value = ''
    try {
        const q = rangeForTrend()
        trendPoints.value = await getGrowthDailyTrend(q)
        await nextTick()
        renderCharts()
    } catch (err) {
        trendPoints.value = []
        trendError.value = getApiErrorMessage(err, '趋势数据加载失败。')
        await nextTick()
        renderCharts()
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
        await generateWeeklySummary({ start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) })
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

watch(
    records,
    () => {
        if (records.value.length) {
            scrollRecordsToLatest()
        }
    },
    { deep: true },
)

onMounted(async () => {
    if (!authState.user) {
        await refreshCurrentUser()
    }
    await load()
    await loadTrend()
    await loadRangeStats()
    window.addEventListener('resize', onResize)
})

onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    disposeCharts()
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

            <div class="charts-grid">
                <div class="chart-card">
                    <h3 class="chart-title">计划执行与累计完成</h3>
                    <p class="chart-desc">折线展示每日行动计划完成、里程碑，以及本周期内行动计划累计完成件数。</p>
                    <div ref="lineRef" class="chart-host" />
                </div>
                <div class="chart-card">
                    <h3 class="chart-title">学习投入与积分</h3>
                    <p class="chart-desc">柱状对比「预估学习分钟」与当日累计成长积分（含自定义得分字段）。</p>
                    <div ref="barRef" class="chart-host" />
                </div>
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
                    <button class="button button--ghost" @click="form.title = '完成了练习题'; form.summary = '进步一点点，值得庆祝'; submit()">
                        写个示例
                    </button>
                </div>
                <div v-else ref="recordsViewportEl" class="records-viewport">
                    <ul class="record-list">
                        <li v-for="r in records" :key="r.id" class="record-item">
                            <h3>{{ r.title }}</h3>
                            <p class="muted">{{ r.record_date ?? (r.occurred_at ? new Date(r.occurred_at).toLocaleString() : '') }}</p>
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
    border: 1px solid rgba(15, 23, 42, 0.06);
    background: rgba(248, 250, 252, 0.65);
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
    color: var(--text-muted, #8ca0b8);
    max-width: 52ch;
    line-height: 1.45;
}

.segmented {
    display: inline-flex;
    padding: 3px;
    border-radius: var(--radius-md, 14px);
    background: rgba(241, 245, 249, 0.95);
    border: 1px solid rgba(15, 23, 42, 0.08);
}

.seg-btn {
    border: none;
    cursor: pointer;
    padding: 0.45rem 1rem;
    border-radius: var(--radius-sm, 10px);
    font: inherit;
    font-size: 0.9rem;
    color: var(--text-muted, #8ca0b8);
    background: transparent;
    transition: background 0.15s ease, color 0.15s ease;
}

.seg-btn--active {
    color: var(--heading);
    background: rgba(224, 242, 254, 0.95);
    box-shadow: 0 0 0 1px rgba(8, 145, 178, 0.22);
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
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(15, 23, 42, 0.08);
    min-width: 6.5rem;
}

.stat-label {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted, #8ca0b8);
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

.chart-card {
    padding: 0.75rem 0.25rem 0;
    border-radius: var(--radius-md, 14px);
    background: rgba(248, 250, 252, 0.75);
    border: 1px solid rgba(15, 23, 42, 0.06);
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
    color: var(--text-muted, #8ca0b8);
    line-height: 1.45;
}

.chart-host {
    width: 100%;
    height: 300px;
}

.record-list {
    display: grid;
    gap: 0.8rem;
}

.record-item {
    padding: 0.8rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.empty-state {
    padding: 1rem 0;
}

.muted {
    color: var(--text-muted, #8ca0b8);
    font-size: 0.9rem;
}
</style>
