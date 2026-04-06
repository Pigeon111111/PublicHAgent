<script setup lang="ts">
import { computed } from 'vue'
import LineChart from './charts/LineChart.vue'
import BarChart from './charts/BarChart.vue'
import ScatterChart from './charts/ScatterChart.vue'
import HeatmapChart from './charts/HeatmapChart.vue'
import type { ChartData } from '@/types'

const props = defineProps<{
  charts: ChartData[]
  tables: Record<string, unknown>[]
}>()

const chartComponents = computed(() => {
  return props.charts.map(chart => {
    let component
    switch (chart.type) {
      case 'line':
        component = LineChart
        break
      case 'bar':
        component = BarChart
        break
      case 'scatter':
        component = ScatterChart
        break
      case 'heatmap':
        component = HeatmapChart
        break
      default:
        component = LineChart
    }
    return {
      ...chart,
      component,
    }
  })
})

function exportToPDF() {
  window.print()
}

function exportToWord() {
  const content = props.charts.map(c => c.title).join('\n') + '\n\n' + 
    props.tables.map(t => JSON.stringify(t)).join('\n')
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'analysis_result.txt'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="result-display">
    <div class="result-actions">
      <el-button type="primary" @click="exportToPDF">
        <el-icon><Download /></el-icon>
        导出 PDF
      </el-button>
      <el-button type="success" @click="exportToWord">
        <el-icon><Document /></el-icon>
        导出 Word
      </el-button>
    </div>

    <div class="charts-section" v-if="charts.length > 0">
      <h3>图表结果</h3>
      <el-row :gutter="24">
        <el-col :span="12" v-for="(chart, index) in chartComponents" :key="index">
          <el-card class="chart-card">
            <component
              :is="chart.component"
              :title="chart.title"
              :data="chart.data"
              :options="chart.options"
            />
          </el-card>
        </el-col>
      </el-row>
    </div>

    <div class="tables-section" v-if="tables.length > 0">
      <h3>数据表格</h3>
      <el-card v-for="(table, index) in tables" :key="index" class="table-card">
        <el-table :data="(table.rows as Record<string, unknown>[]) || []" stripe border>
          <el-table-column
            v-for="(col, colIndex) in (table.columns as string[]) || []"
            :key="colIndex"
            :prop="col"
            :label="col"
          />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.result-display {
  padding: 20px;
}

.result-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.charts-section h3,
.tables-section h3 {
  margin-bottom: 16px;
  color: #303133;
}

.chart-card {
  margin-bottom: 24px;
}

.table-card {
  margin-bottom: 24px;
}

@media print {
  .result-actions {
    display: none;
  }
}
</style>
