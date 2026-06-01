import type { EChartsOption } from 'echarts'
import { computed } from 'vue'
import { useTheme } from './useTheme'

export interface ChartThemeTokens {
  text: string
  textMuted: string
  heading: string
  axisLine: string
  splitLine: string
  primary: string
  success: string
  secondary: string
}

function readCssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return raw || fallback
}

export function chartThemeTokens(): ChartThemeTokens {
  return {
    text: readCssVar('--text', '#334155'),
    textMuted: readCssVar('--text-muted', '#64748b'),
    heading: readCssVar('--heading', '#0f172a'),
    axisLine: 'rgba(15, 23, 42, 0.12)',
    splitLine: 'rgba(15, 23, 42, 0.06)',
    primary: readCssVar('--primary', '#06b6d4'),
    success: readCssVar('--success', '#22c55e'),
    secondary: readCssVar('--secondary', '#a855f7'),
  }
}

export function baseChartTheme(tokens: ChartThemeTokens): Pick<EChartsOption, 'backgroundColor' | 'textStyle'> {
  return {
    backgroundColor: 'transparent',
    textStyle: { color: tokens.text, fontFamily: 'Inter, Segoe UI, sans-serif' },
  }
}

export function useChartTheme() {
  const { theme } = useTheme()
  const tokens = computed(() => {
    void theme.value
    return chartThemeTokens()
  })
  const chartBase = computed(() => baseChartTheme(tokens.value))

  return { theme, tokens, chartBase }
}
