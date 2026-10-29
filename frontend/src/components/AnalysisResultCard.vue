<script setup lang="ts">
/**
 * AI 教案分析结果卡片组件
 * 展示 7 维度评分和建议
 */
import { computed, ref } from 'vue'
import { 
  Document, TrendCharts, Star, ReadingLamp, 
  ArrowRight, CircleCheck, InfoFilled 
} from '@element-plus/icons-vue'

interface Dimension {
  score: number
  comment: string
}

interface AnalysisResult {
  overall_score: number
  dimensions: {
    structure: Dimension
    objectives: Dimension
    key_points: Dimension
    teaching_process: Dimension
    teaching_methods: Dimension
    board_design: Dimension
    language: Dimension
  }
  highlights: string[]
  suggestions: string[]
  summary?: string
}

const props = defineProps<{
  result: AnalysisResult
  showDetails?: boolean
}>()

const emit = defineEmits<{
  (e: 'use-score', score: number): void
  (e: 'reanalyze'): void
}>()

const expanded = ref(props.showDetails ?? true)

// 维度名称映射
const dimensionLabels: Record<string, string> = {
  structure: '结构完整性',
  objectives: '教学目标',
  key_points: '重难点分析',
  teaching_process: '教学过程',
  teaching_methods: '教学方法',
  board_design: '板书设计',
  language: '教学语言'
}

// 维度权重
const dimensionWeights: Record<string, number> = {
  structure: 15,
  objectives: 15,
  key_points: 15,
  teaching_process: 20,
  teaching_methods: 15,
  board_design: 10,
  language: 10
}

// 分数等级
const getScoreLevel = (score: number) => {
  if (score >= 90) return { text: '优秀', color: '#10b981', type: 'success' }
  if (score >= 80) return { text: '良好', color: '#3b82f6', type: 'primary' }
  if (score >= 70) return { text: '中等', color: '#f59e0b', type: 'warning' }
  if (score >= 60) return { text: '及格', color: '#f97316', type: 'warning' }
  return { text: '需改进', color: '#ef4444', type: 'danger' }
}

const overallLevel = computed(() => getScoreLevel(props.result.overall_score))

// 维度列表
const dimensionList = computed(() => {
  return Object.entries(props.result.dimensions).map(([key, value]) => ({
    key,
    label: dimensionLabels[key] || key,
    weight: dimensionWeights[key] || 10,
    ...value,
    level: getScoreLevel(value.score)
  }))
})

// 计算进度条颜色
const getProgressColor = (score: number) => {
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 70) return '#f59e0b'
  if (score >= 60) return '#f97316'
  return '#ef4444'
}
</script>

<template>
  <div class="analysis-card">
    <!-- 头部：总分展示 -->
    <div class="card-header">
      <div class="score-section">
        <div class="score-circle" :style="{ '--color': overallLevel.color }">
          <span class="score-value">{{ result.overall_score }}</span>
          <span class="score-label">综合评分</span>
        </div>
        <div class="score-info">
          <el-tag :type="overallLevel.type as any" effect="dark" size="large">
            {{ overallLevel.text }}
          </el-tag>
          <p class="score-summary" v-if="result.summary">{{ result.summary }}</p>
        </div>
      </div>
      
      <div class="header-actions">
        <el-button 
          type="primary" 
          :icon="TrendCharts" 
          @click="emit('use-score', result.overall_score)"
        >
          使用此评分
        </el-button>
        <el-button :icon="ArrowRight" @click="emit('reanalyze')">
          重新分析
        </el-button>
      </div>
    </div>

    <!-- 维度评分 -->
    <div class="dimensions-section">
      <div class="section-header" @click="expanded = !expanded">
        <h4>
          <el-icon><Document /></el-icon>
          维度评分详情
        </h4>
        <el-icon class="toggle-icon" :class="{ expanded }">
          <ArrowRight />
        </el-icon>
      </div>
      
      <Transition name="fade">
        <div v-show="expanded" class="dimension-grid">
          <div 
            v-for="dim in dimensionList" 
            :key="dim.key" 
            class="dimension-item"
          >
            <div class="dim-header">
              <span class="dim-label">{{ dim.label }}</span>
              <span class="dim-weight">({{ dim.weight }}%)</span>
              <el-tag :type="dim.level.type as any" size="small" effect="plain">
                {{ dim.score }}分
              </el-tag>
            </div>
            <el-progress 
              :percentage="dim.score" 
              :stroke-width="8"
              :color="getProgressColor(dim.score)"
              :show-text="false"
            />
            <p class="dim-comment">{{ dim.comment }}</p>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 亮点与建议 -->
    <div class="feedback-section">
      <!-- 亮点 -->
      <div class="feedback-box highlights" v-if="result.highlights?.length">
        <h4>
          <el-icon class="text-green-500"><Star /></el-icon>
          亮点
        </h4>
        <ul>
          <li v-for="(item, index) in result.highlights" :key="index">
            <el-icon class="text-green-500"><CircleCheck /></el-icon>
            {{ item }}
          </li>
        </ul>
      </div>
      
      <!-- 建议 -->
      <div class="feedback-box suggestions" v-if="result.suggestions?.length">
        <h4>
          <el-icon class="text-amber-500"><ReadingLamp /></el-icon>
          改进建议
        </h4>
        <ul>
          <li v-for="(item, index) in result.suggestions" :key="index">
            <el-icon class="text-amber-500"><InfoFilled /></el-icon>
            {{ item }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

/* 头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 24px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.score-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: var(--color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--color) 30%, transparent);
}

.score-value {
  font-size: 32px;
  font-weight: 700;
  color: white;
  line-height: 1;
}

.score-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.9);
  margin-top: 4px;
}

.score-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-summary {
  font-size: 14px;
  color: #64748b;
  max-width: 300px;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 维度评分 */
.dimensions-section {
  padding: 0 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  cursor: pointer;
  user-select: none;
}

.section-header h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 0;
}

.toggle-icon {
  transition: transform 0.3s;
  color: #94a3b8;
}

.toggle-icon.expanded {
  transform: rotate(90deg);
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  padding-bottom: 20px;
}

.dimension-item {
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
  transition: all 0.2s;
}

.dimension-item:hover {
  background: #f1f5f9;
  transform: translateY(-2px);
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dim-label {
  font-weight: 600;
  color: #334155;
}

.dim-weight {
  font-size: 12px;
  color: #94a3b8;
}

.dim-comment {
  margin-top: 10px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

/* 亮点与建议 */
.feedback-section {
  display: flex;
  gap: 20px;
  padding: 20px 24px 24px;
  background: #fafafa;
  border-top: 1px solid #e2e8f0;
}

.feedback-box {
  flex: 1;
  padding: 16px;
  border-radius: 12px;
}

.feedback-box.highlights {
  background: #ecfdf5;
  border: 1px solid #d1fae5;
}

.feedback-box.suggestions {
  background: #fffbeb;
  border: 1px solid #fef3c7;
}

.feedback-box h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #334155;
}

.feedback-box ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feedback-box li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.feedback-box li .el-icon {
  margin-top: 3px;
  flex-shrink: 0;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  max-height: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: 16px;
  }
  
  .header-actions {
    flex-direction: row;
    width: 100%;
  }
  
  .header-actions .el-button {
    flex: 1;
  }
  
  .feedback-section {
    flex-direction: column;
  }
  
  .dimension-grid {
    grid-template-columns: 1fr;
  }
}
</style>
</script>
