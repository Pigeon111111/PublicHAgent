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
      position: 'top',
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: (props.data.xAxis as string[]) || [],
      splitArea: {
        show: true,
      },
    },
    yAxis: {
      type: 'category',
      data: (props.data.yAxis as string[]) || [],
      splitArea: {
        show: true,
      },
    },
    visualMap: {
      min: (props.data.min as number) || 0,
      max: (props.data.max as number) || 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
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
  <div class="heatmap-chart" ref="chartRef" />
</template>

<style scoped>
.heatmap-chart {
  width: 100%;
  height: 400px;
}
</style>
