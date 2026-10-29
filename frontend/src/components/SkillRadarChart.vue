<script setup lang="ts">
/**
 * 能力雷达图组件
 * 展示学生在各维度的能力评估
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent 
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([RadarChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface RadarData {
  name: string
  value: number[]
}

interface RadarIndicator {
  name: string
  max: number
}

const props = withDefaults(defineProps<{
  indicators: RadarIndicator[]
  data: RadarData[]
  title?: string
  height?: string
  showLegend?: boolean
  colors?: string[]
}>(), {
  height: '400px',
  showLegend: true,
  colors: () => ['#0891b2', '#10b981', '#f59e0b']
})

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

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
  legend: props.showLegend && props.data.length > 1 ? {
    data: props.data.map(d => d.name),
    bottom: 10,
    textStyle: { color: '#64748b' }
  } : undefined,
  tooltip: {
    trigger: 'item',
    formatter: (params: any) => {
      const values = params.value
      let html = `<div style="padding: 8px 12px"><strong>${params.name}</strong><br/>`
      props.indicators.forEach((ind, i) => {
        html += `${ind.name}: <strong>${values[i]}</strong>分<br/>`
      })
      html += '</div>'
      return html
    }
  },
  radar: {
    indicator: props.indicators.map(ind => ({
      name: ind.name,
      max: ind.max || 100
    })),
    center: ['50%', props.title ? '55%' : '50%'],
    radius: props.title ? '60%' : '70%',
    shape: 'polygon',
    splitNumber: 5,
    axisName: {
      color: '#64748b',
      fontSize: 12,
      fontWeight: 500
    },
    splitLine: {
      lineStyle: {
        color: ['#e2e8f0', '#e2e8f0', '#e2e8f0', '#e2e8f0', '#e2e8f0']
      }
    },
    splitArea: {
      show: true,
      areaStyle: {
        color: ['#fafafa', '#f5f5f5', '#f0f0f0', '#eaeaea', '#e5e5e5']
      }
    },
    axisLine: {
      lineStyle: {
        color: '#d1d5db'
      }
    }
  },
  series: [{
    type: 'radar',
    data: props.data.map((d, i) => ({
      name: d.name,
      value: d.value,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: {
        width: 2,
        color: props.colors[i % props.colors.length]
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${props.colors[i % props.colors.length]}40` },
          { offset: 1, color: `${props.colors[i % props.colors.length]}10` }
        ])
      },
      itemStyle: {
        color: props.colors[i % props.colors.length],
        borderColor: '#fff',
        borderWidth: 2
      }
    }))
  }]
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

watch(() => [props.indicators, props.data], () => {
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
  <div class="radar-chart-container">
    <div ref="chartRef" class="radar-chart" :style="{ height }"></div>
    
    <!-- 维度分数详情 -->
    <div v-if="data.length === 1 && showLegend" class="dimension-details">
      <div 
        v-for="(ind, i) in indicators" 
        :key="ind.name"
        class="dimension-item"
      >
        <span class="dim-name">{{ ind.name }}</span>
        <div class="dim-bar">
          <div 
            class="dim-fill"
            :style="{ 
              width: `${(data[0].value[i] / ind.max) * 100}%`,
              background: colors[0]
            }"
          ></div>
        </div>
        <span class="dim-score" :style="{ color: colors[0] }">
          {{ data[0].value[i] }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.radar-chart-container {
  width: 100%;
}

.radar-chart {
  width: 100%;
}

.dimension-details {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
  margin-top: 16px;
}

.dimension-item {
  flex: 1 1 calc(50% - 6px);
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
}

.dim-name {
  font-size: 13px;
  color: #64748b;
  min-width: 70px;
}

.dim-bar {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease-out;
}

.dim-score {
  font-size: 14px;
  font-weight: 600;
  min-width: 32px;
  text-align: right;
}

@media (max-width: 640px) {
  .dimension-item {
    flex: 1 1 100%;
  }
}
</style>
</script>
