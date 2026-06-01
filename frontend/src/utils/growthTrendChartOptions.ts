import type { EChartsOption } from 'echarts'
import { graphic } from 'echarts/core'
import type { GrowthDailyTrendPoint } from '../api/growthRecords'
import type { ChartThemeTokens } from '../composables/useChartTheme'
import { baseChartTheme } from '../composables/useChartTheme'

export function estimateStudyMinutes(p: GrowthDailyTrendPoint): number {
  return Math.round(
    p.completed_count * 25 + p.reflection_count * 15 + p.milestone_count * 20 + (p.growth_score || 0),
  )
}

export function buildGrowthLineOption(
  points: GrowthDailyTrendPoint[],
  tokens: ChartThemeTokens,
): EChartsOption {
  const labels = points.map((p) => p.record_date.slice(5))
  const completed = points.map((p) => p.completed_count)
  const milestones = points.map((p) => p.milestone_count)
  let acc = 0
  const cumulative = points.map((p) => {
    acc += p.completed_count
    return acc
  })

  return {
    ...baseChartTheme(tokens),
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['计划完成(日)', '里程碑(日)', '累计计划完成'],
      textStyle: { color: tokens.textMuted },
      bottom: 0,
    },
    grid: { left: 48, right: 56, top: 28, bottom: 64 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: tokens.axisLine } },
      axisLabel: { color: tokens.textMuted },
    },
    yAxis: [
      {
        type: 'value',
        name: '件/日',
        nameTextStyle: { color: tokens.textMuted },
        splitLine: { lineStyle: { color: tokens.splitLine } },
        axisLabel: { color: tokens.textMuted },
      },
      {
        type: 'value',
        name: '累计件数',
        nameTextStyle: { color: tokens.textMuted },
        splitLine: { show: false },
        axisLabel: { color: tokens.textMuted },
      },
    ],
    series: [
      {
        name: '计划完成(日)',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: completed,
        itemStyle: { color: tokens.primary },
        areaStyle: { color: 'rgba(6, 182, 212, 0.12)' },
      },
      {
        name: '里程碑(日)',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        data: milestones,
        itemStyle: { color: tokens.secondary },
      },
      {
        name: '累计计划完成',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 6,
        data: cumulative,
        itemStyle: { color: tokens.success },
      },
    ],
  }
}

export function buildGrowthBarOption(
  points: GrowthDailyTrendPoint[],
  tokens: ChartThemeTokens,
  opts: { rotateLabels?: boolean } = {},
): EChartsOption {
  const labels = points.map((p) => p.record_date.slice(5))
  const minutes = points.map((p) => estimateStudyMinutes(p))
  const scores = points.map((p) => p.growth_score || 0)

  return {
    ...baseChartTheme(tokens),
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['预估学习投入(分)', '成长积分'],
      textStyle: { color: tokens.textMuted },
      bottom: 0,
    },
    grid: { left: 48, right: 24, top: 28, bottom: 72 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: tokens.axisLine } },
      axisLabel: { color: tokens.textMuted, rotate: opts.rotateLabels ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: '数值',
      nameTextStyle: { color: tokens.textMuted },
      splitLine: { lineStyle: { color: tokens.splitLine } },
      axisLabel: { color: tokens.textMuted },
    },
    series: [
      {
        name: '预估学习投入(分)',
        type: 'bar',
        barMaxWidth: 22,
        data: minutes,
        itemStyle: {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
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
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(34,197,94,0.9)' },
            { offset: 1, color: 'rgba(34,197,94,0.2)' },
          ]),
        },
      },
    ],
  }
}
