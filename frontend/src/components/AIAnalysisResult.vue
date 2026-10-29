<script setup lang="ts">
/**
 * AI 分析结果展示组件
 * 用于展示教案分析或视频分析的详细结果
 */
import { computed } from 'vue'
import { use } from 'echarts/core'
import { RadarChart, BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { 
  Star, Warning, ReadingLamp, Document, VideoCamera,
  CircleCheck, CircleClose, TrendCharts
} from '@element-plus/icons-vue'

// 注册 ECharts 组件
use([RadarChart, BarChart, TooltipComponent, GridComponent, CanvasRenderer])

interface DimensionScore {
  key: string
  label: string
  score: number
  feedback?: string
}

interface AnalysisResult {
  type: 'lesson_plan' | 'video' | 'comprehensive'
  overall_score: number
  dimensions: DimensionScore[]
  strengths?: string[]
  weaknesses?: string[]
  suggestions?: string[]
  summary?: string
  created_at?: string
}

const props = defineProps<{
  analysis: AnalysisResult
  showChart?: boolean
  compact?: boolean
}>()

// 评分等级
const scoreLevel = computed(() => {
  const score = props.analysis.overall_score
  if (score >= 90) return { text: '优秀', color: '#10b981', bg: 'bg-emerald-50' }
  if (score >= 80) return { text: '良好', color: '#0891b2', bg: 'bg-cyan-50' }
  if (score >= 70) return { text: '中等', color: '#f59e0b', bg: 'bg-amber-50' }
  if (score >= 60) return { text: '及格', color: '#ef4444', bg: 'bg-red-50' }
  return { text: '待提高', color: '#9ca3af', bg: 'bg-gray-50' }
})

// 类型标签
const typeLabel = computed(() => {
  const labels: Record<string, { text: string; icon: any }> = {
    'lesson_plan': { text: '教案分析', icon: Document },
    'video': { text: '视频分析', icon: VideoCamera },
    'comprehensive': { text: '综合评估', icon: TrendCharts }
  }
  return labels[props.analysis.type] || { text: '分析结果', icon: Document }
})

// 雷达图配置
const radarOption = computed(() => {
  if (!props.showChart || !props.analysis.dimensions?.length) return null
  
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: props.analysis.dimensions.map(d => ({
        name: d.label,
        max: 100
      })),
      center: ['50%', '50%'],
      radius: '70%',
      axisName: {
        color: '#666',
        fontSize: 10
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(8, 145, 178, 0.02)', 'rgba(8, 145, 178, 0.05)', 
                  'rgba(8, 145, 178, 0.08)', 'rgba(8, 145, 178, 0.12)']
        }
      },
      splitLine: {
        lineStyle: { color: 'rgba(8, 145, 178, 0.15)' }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: props.analysis.dimensions.map(d => d.score),
        name: '得分',
        lineStyle: { color: '#0891b2', width: 2 },
        areaStyle: { color: 'rgba(8, 145, 178, 0.2)' },
        itemStyle: { color: '#0891b2' }
      }]
    }]
  }
})

// 条形图配置
const barOption = computed(() => {
  if (props.showChart || !props.analysis.dimensions?.length) return null
  
  const dims = props.analysis.dimensions.slice(0, 6)
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 20, bottom: 30, left: 80 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { fontSize: 10 }
    },
    yAxis: {
      type: 'category',
      data: dims.map(d => d.label),
      axisLabel: { fontSize: 10 }
    },
    series: [{
      type: 'bar',
      data: dims.map(d => ({
        value: d.score,
        itemStyle: {
          color: d.score >= 80 ? '#10b981' : d.score >= 60 ? '#f59e0b' : '#ef4444'
        }
      })),
      barWidth: 12,
      label: {
        show: true,
        position: 'right',
        fontSize: 10,
        formatter: '{c}分'
      }
    }]
  }
})
</script>

<template>
  <div class="analysis-result" :class="{ compact }">
    <!-- 头部 -->
    <div class="result-header">
      <div class="type-badge">
        <el-icon><component :is="typeLabel.icon" /></el-icon>
        <span>{{ typeLabel.text }}</span>
      </div>
      <div 
        class="overall-score"
        :class="scoreLevel.bg"
        :style="{ color: scoreLevel.color }"
      >
        <span class="score-value">{{ analysis.overall_score }}</span>
        <span class="score-label">{{ scoreLevel.text }}</span>
      </div>
    </div>

    <!-- 摘要 -->
    <div v-if="analysis.summary && !compact" class="result-summary">
      <p>{{ analysis.summary }}</p>
    </div>

    <!-- 图表 -->
    <div v-if="showChart && radarOption" class="result-chart">
      <v-chart :option="radarOption" autoresize />
    </div>

    <!-- 维度得分列表 -->
    <div class="dimensions-list" v-if="!showChart">
      <div 
        v-for="dim in analysis.dimensions" 
        :key="dim.key"
        class="dimension-item"
      >
        <div class="dim-header">
          <span class="dim-label">{{ dim.label }}</span>
          <span 
            class="dim-score"
            :class="{
              'text-emerald-600': dim.score >= 80,
              'text-amber-600': dim.score >= 60 && dim.score < 80,
              'text-red-500': dim.score < 60
            }"
          >
            {{ dim.score }}分
          </span>
        </div>
        <el-progress 
          :percentage="dim.score" 
          :stroke-width="6"
          :color="dim.score >= 80 ? '#10b981' : dim.score >= 60 ? '#f59e0b' : '#ef4444'"
          :show-text="false"
        />
        <p v-if="dim.feedback && !compact" class="dim-feedback">{{ dim.feedback }}</p>
      </div>
    </div>

    <!-- 优缺点和建议 -->
    <div v-if="!compact" class="feedback-sections">
      <div v-if="analysis.strengths?.length" class="feedback-section strengths">
        <h4 class="section-title">
          <el-icon class="text-emerald-500"><CircleCheck /></el-icon>
          优点
        </h4>
        <ul>
          <li v-for="(item, i) in analysis.strengths" :key="i">{{ item }}</li>
        </ul>
      </div>

      <div v-if="analysis.weaknesses?.length" class="feedback-section weaknesses">
        <h4 class="section-title">
          <el-icon class="text-amber-500"><Warning /></el-icon>
          待改进
        </h4>
        <ul>
          <li v-for="(item, i) in analysis.weaknesses" :key="i">{{ item }}</li>
        </ul>
      </div>

      <div v-if="analysis.suggestions?.length" class="feedback-section suggestions">
        <h4 class="section-title">
          <el-icon class="text-blue-500"><ReadingLamp /></el-icon>
          改进建议
        </h4>
        <ul>
          <li v-for="(item, i) in analysis.suggestions" :key="i">{{ item }}</li>
        </ul>
      </div>
    </div>

    <!-- 时间戳 -->
    <div v-if="analysis.created_at && !compact" class="result-timestamp">
      分析时间：{{ new Date(analysis.created_at).toLocaleString() }}
    </div>
  </div>
</template>

<style scoped>
.analysis-result {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
}

.analysis-result.compact {
  padding: 0.75rem;
  gap: 0.75rem;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.type-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
}

.overall-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
}

.score-value {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
}

.score-label {
  font-size: 0.75rem;
  font-weight: 500;
  margin-top: 0.25rem;
}

.result-summary {
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: #4b5563;
  line-height: 1.6;
}

.result-chart {
  height: 200px;
}

.dimensions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dimension-item {
  padding: 0.5rem;
  background: #fafafa;
  border-radius: 0.5rem;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.375rem;
}

.dim-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.dim-score {
  font-size: 0.875rem;
  font-weight: 600;
}

.dim-feedback {
  margin-top: 0.375rem;
  font-size: 0.75rem;
  color: #6b7280;
  line-height: 1.5;
}

.feedback-sections {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.feedback-section {
  padding: 0.75rem;
  border-radius: 0.5rem;
}

.feedback-section.strengths {
  background: #ecfdf5;
}

.feedback-section.weaknesses {
  background: #fffbeb;
}

.feedback-section.suggestions {
  background: #eff6ff;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.feedback-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feedback-section li {
  position: relative;
  padding-left: 1rem;
  font-size: 0.875rem;
  color: #4b5563;
  line-height: 1.6;
}

.feedback-section li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #9ca3af;
}

.result-timestamp {
  font-size: 0.75rem;
  color: #9ca3af;
  text-align: right;
}

/* 紧凑模式 */
.compact .result-header {
  margin-bottom: 0;
}

.compact .dimensions-list {
  gap: 0.5rem;
}

.compact .dimension-item {
  padding: 0.375rem;
}

.compact .dim-header {
  margin-bottom: 0.25rem;
}
</style>
