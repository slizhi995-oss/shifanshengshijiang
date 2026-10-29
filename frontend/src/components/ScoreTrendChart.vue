<script setup lang="ts">
/**
 * 成绩趋势图组件
 * 展示学生历次成绩变化趋势
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent,
  GridComponent,
  MarkLineComponent,
  MarkPointComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, BarChart, TitleComponent, TooltipComponent, 
  LegendComponent, GridComponent, MarkLineComponent, 
  MarkPointComponent, CanvasRenderer
])

interface TrendData {
  date: string
  lessonPlanScore?: number
  videoScore?: number
  totalScore: number
  taskName?: string
}

const props = withDefaults(defineProps<{
  data: TrendData[]
  title?: string
  height?: string
  showAverage?: boolean
  showComparison?: boolean
  averageScore?: number
}>(), {
  height: '350px',
  showAverage: true,
  showComparison: false,
  averageScore: 75
})

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

// 计算统计数据
const stats = computed(() => {
  if (!props.data.length) return null
  
  const scores = props.data.map(d => d.totalScore)
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length
  const max = Math.max(...scores)
  const min = Math.min(...scores)
  const latest = scores[scores.length - 1]
  const trend = scores.length > 1 ? latest - scores[scores.length - 2] : 0
  
  return { avg: avg.toFixed(1), max, min, latest, trend }
})

const option = computed(() => ({
  title: props.title ? {
    text: props.title,
    left: 'center',
    top: 10,
    textStyle: {
      fontSize: 16,
      fontWeight: 600,
      color: '#334155'
    }
  } : undefined,
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderColor: '#e2e8f0',
    borderWidth: 1,
    textStyle: { color: '#334155' },
    formatter: (params: any) => {
      const dataIndex = params[0].dataIndex
      const item = props.data[dataIndex]
      let html = `<div style="padding: 8px">
        <div style="font-weight: 600; margin-bottom: 8px">${item.taskName || item.date}</div>`
      
      if (item.lessonPlanScore !== undefined) {
        html += `<div style="display: flex; justify-content: space-between; gap: 16px">
          <span style="color: #64748b">教案分</span>
          <span style="font-weight: 600">${item.lessonPlanScore}</span>
        </div>`
      }
      if (item.videoScore !== undefined) {
        html += `<div style="display: flex; justify-content: space-between; gap: 16px">
          <span style="color: #64748b">视频分</span>
          <span style="font-weight: 600">${item.videoScore}</span>
        </div>`
      }
      html += `<div style="display: flex; justify-content: space-between; gap: 16px; margin-top: 4px; padding-top: 4px; border-top: 1px solid #e2e8f0">
        <span style="color: #0891b2; font-weight: 500">总分</span>
        <span style="color: #0891b2; font-weight: 700; font-size: 16px">${item.totalScore}</span>
      </div>
      </div>`
      return html
    }
  },
  legend: {
    data: ['总分', ...(props.data.some(d => d.lessonPlanScore !== undefined) ? ['教案分'] : []),
           ...(props.data.some(d => d.videoScore !== undefined) ? ['视频分'] : [])],
    bottom: 10,
    textStyle: { color: '#64748b' }
  },
  grid: {
    top: props.title ? 60 : 40,
    right: 30,
    bottom: 50,
    left: 50
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.date),
    axisLine: { lineStyle: { color: '#e2e8f0' } },
    axisLabel: { 
      color: '#64748b',
      fontSize: 11,
      rotate: props.data.length > 6 ? 30 : 0
    }
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#64748b' },
    splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } }
  },
  series: [
    {
      name: '总分',
      type: 'line',
      data: props.data.map(d => d.totalScore),
      smooth: true,
      symbol: 'circle',
      symbolSize: 10,
      lineStyle: {
        width: 3,
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#0891b2' },
          { offset: 1, color: '#0d9488' }
        ])
      },
      itemStyle: {
        color: '#0891b2',
        borderColor: '#fff',
        borderWidth: 2
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(8, 145, 178, 0.3)' },
          { offset: 1, color: 'rgba(8, 145, 178, 0.05)' }
        ])
      },
      markLine: props.showAverage ? {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#f59e0b', type: 'dashed', width: 2 },
        data: [{ 
          yAxis: props.averageScore, 
          label: { 
            formatter: `班级均分 ${props.averageScore}`,
            color: '#f59e0b',
            fontSize: 11
          } 
        }]
      } : undefined,
      markPoint: {
        symbol: 'pin',
        symbolSize: 40,
        data: [
          { type: 'max', name: '最高分', itemStyle: { color: '#10b981' } },
          { type: 'min', name: '最低分', itemStyle: { color: '#ef4444' } }
        ]
      }
    },
    ...(props.data.some(d => d.lessonPlanScore !== undefined) ? [{
      name: '教案分',
      type: 'line',
      data: props.data.map(d => d.lessonPlanScore),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#10b981', type: 'dashed' },
      itemStyle: { color: '#10b981' }
    }] : []),
    ...(props.data.some(d => d.videoScore !== undefined) ? [{
      name: '视频分',
      type: 'line',
      data: props.data.map(d => d.videoScore),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#f59e0b', type: 'dashed' },
      itemStyle: { color: '#f59e0b' }
    }] : [])
  ]
}))

const initChart = () => {
  if (!chartRef.value) return
  
  if (chart) {
    chart.dispose()
  }
  
  chart = echarts.init(chartRef.value)
  chart.setOption(option.value)
}

const handleResize = () => {
  chart?.resize()
}

watch(() => props.data, () => {
  if (chart) {
    chart.setOption(option.value)
  }
}, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<template>
  <div class="trend-chart-wrapper">
    <!-- 统计卡片 -->
    <div v-if="stats" class="stats-bar">
      <div class="stat-item">
        <span class="stat-label">平均分</span>
        <span class="stat-value">{{ stats.avg }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最高分</span>
        <span class="stat-value text-green-600">{{ stats.max }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最低分</span>
        <span class="stat-value text-red-500">{{ stats.min }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最新成绩</span>
        <span class="stat-value text-cyan-700">{{ stats.latest }}</span>
        <span 
          v-if="stats.trend !== 0" 
          class="trend-indicator"
          :class="stats.trend > 0 ? 'up' : 'down'"
        >
          {{ stats.trend > 0 ? '+' : '' }}{{ stats.trend }}
        </span>
      </div>
    </div>
    
    <!-- 图表 -->
    <div ref="chartRef" class="trend-chart" :style="{ height }"></div>
    
    <!-- 空状态 -->
    <div v-if="!data.length" class="empty-state">
      <el-empty description="暂无成绩数据" :image-size="80" />
    </div>
  </div>
</template>

<style scoped>
.trend-chart-wrapper {
  width: 100%;
}

.stats-bar {
  display: flex;
  gap: 24px;
  padding: 16px 20px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #334155;
}

.trend-indicator {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.trend-indicator.up {
  color: #10b981;
  background: #d1fae5;
}

.trend-indicator.down {
  color: #ef4444;
  background: #fee2e2;
}

.trend-chart {
  width: 100%;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

@media (max-width: 640px) {
  .stats-bar {
    flex-wrap: wrap;
    gap: 12px;
  }
  
  .stat-item {
    flex: 1 1 calc(50% - 6px);
  }
}
</style>
</script>
