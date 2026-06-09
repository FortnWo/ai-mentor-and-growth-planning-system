<script lang="ts">
export default {
  name: 'AppEChart',
}
</script>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useChartTheme } from '../../composables/useChartTheme'

echarts.use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = withDefaults(
  defineProps<{
    option: EChartsOption
    height?: string
    loading?: boolean
    autoresize?: boolean
  }>(),
  {
    height: '300px',
    loading: false,
    autoresize: true,
  },
)

const { chartBase } = useChartTheme()

const mergedOption = computed<EChartsOption>(() => ({
  ...chartBase.value,
  ...props.option,
  textStyle: {
    ...chartBase.value.textStyle,
    ...(props.option.textStyle as object | undefined),
  },
}))

const updateOptions = { notMerge: false, replaceMerge: ['series', 'xAxis'] }

const chartRef = ref<InstanceType<typeof VChart> | null>(null)

function resizeChart() {
  const inst = chartRef.value as { resize?: () => void; chart?: ECharts } | null
  inst?.resize?.()
  inst?.chart?.resize?.()
}

watch(mergedOption, () => {
  void nextTick(resizeChart)
})

onMounted(() => {
  void nextTick(resizeChart)
})

</script>

<template>
  <VChart
    ref="chartRef"
    class="app-echart"
    :option="mergedOption"
    :update-options="updateOptions"
    :autoresize="autoresize"
    :loading="loading"
  />
</template>

<style scoped>
.app-echart {
  width: 100%;
  height: v-bind(height);
}
</style>
