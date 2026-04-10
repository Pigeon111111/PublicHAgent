<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  title?: string
  data: Record<string, unknown>
  options?: Record<string, unknown>
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  
  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chartInstance) return
  
  const defaultOptions: echarts.EChartsOption = {
    title: {
      text: props.title || '',
      left: 'center',
    },
    tooltip: {
      trigger: 'item',
    },
    legend: {
      bottom: 10,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
    },
    yAxis: {
      type: 'value',
    },
    series: (props.data.series as echarts.SeriesOption[]) || [],
  }

  const mergedOptions = { ...defaultOptions, ...props.options }
  chartInstance.setOption(mergedOptions)
}

function resizeChart() {
  chartInstance?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', resizeChart)
})

watch(() => [props.data, props.options], updateChart, { deep: true })

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance?.dispose()
})
</script>

<template>
  <div
    ref="chartRef"
    class="scatter-chart"
  />
</template>

<style scoped>
.scatter-chart {
  width: 100%;
  height: 400px;
}
</style>
