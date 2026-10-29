<script setup lang="ts">
/**
 * AI 分析过程可视化组件
 * 展示 AI 分析的多步骤流水线动画
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { Document, Cpu, DataAnalysis, Finished, Film, Microphone, User, TrendCharts, FolderOpened, ChatDotRound, Aim } from '@element-plus/icons-vue'

export interface AIStep {
  label: string
  icon: string
  description: string
}

const props = withDefaults(defineProps<{
  steps?: AIStep[]
  active?: boolean
  type?: 'lesson_plan' | 'video' | 'comprehensive'
}>(), {
  active: false,
  type: 'lesson_plan'
})

const emit = defineEmits<{
  complete: []
}>()

const currentStep = ref(0)
let stepTimer: ReturnType<typeof setInterval> | null = null

const defaultSteps: Record<string, AIStep[]> = {
  lesson_plan: [
    { label: '文档解析', icon: 'Document', description: '提取教案文本内容' },
    { label: 'NLP 语义分析', icon: 'Cpu', description: '深度理解教学设计意图' },
    { label: '多维度评估', icon: 'DataAnalysis', description: '7维度教学能力评估' },
    { label: '生成报告', icon: 'Finished', description: '输出专业分析报告' }
  ],
  video: [
    { label: '视频帧提取', icon: 'Film', description: '关键帧智能采样' },
    { label: '语音识别 ASR', icon: 'Microphone', description: '语音转文字与韵律分析' },
    { label: '姿态识别', icon: 'User', description: '手势、姿态、眼神分析' },
    { label: '综合评分', icon: 'TrendCharts', description: '多模态融合评估' }
  ],
  comprehensive: [
    { label: '数据聚合', icon: 'FolderOpened', description: '汇总教案与视频分析' },
    { label: 'AI 推理', icon: 'Cpu', description: '大模型综合研判' },
    { label: '评语生成', icon: 'ChatDotRound', description: '生成专业评语与建议' },
    { label: '评分建议', icon: 'Aim', description: '输出建议分数' }
  ]
}

const activeSteps = computed(() => props.steps || defaultSteps[props.type] || defaultSteps.lesson_plan)

watch(() => props.active, (val) => {
  if (val) {
    currentStep.value = 0
    stepTimer = setInterval(() => {
      if (currentStep.value < activeSteps.value.length - 1) {
        currentStep.value++
      } else {
        if (stepTimer) clearInterval(stepTimer)
        emit('complete')
      }
    }, 1800)
  } else {
    if (stepTimer) clearInterval(stepTimer)
    currentStep.value = 0
  }
}, { immediate: true })

onUnmounted(() => {
  if (stepTimer) clearInterval(stepTimer)
})
</script>

<template>
  <div class="ai-process" v-if="active">
    <div class="process-header">
      <div class="brain-icon">
        <span class="brain-pulse"></span>
        <el-icon class="brain-el-icon" :size="28"><Cpu /></el-icon>
      </div>
      <div>
        <h3 class="process-title">AI 正在分析中</h3>
        <p class="process-subtitle">{{ activeSteps[currentStep]?.description }}</p>
      </div>
    </div>

    <div class="steps-pipeline">
      <div 
        v-for="(step, index) in activeSteps" 
        :key="index"
        class="pipeline-step"
        :class="{
          'is-completed': index < currentStep,
          'is-active': index === currentStep,
          'is-pending': index > currentStep
        }"
      >
        <div class="step-node">
          <el-icon class="step-icon" :size="22"><component :is="step.icon" /></el-icon>
          <div class="step-ring" v-if="index === currentStep"></div>
        </div>
        <div class="step-label">{{ step.label }}</div>
        <div class="step-connector" v-if="index < activeSteps.length - 1">
          <div class="connector-fill" :class="{ filled: index < currentStep }"></div>
          <div class="data-flow" v-if="index === currentStep">
            <span class="flow-dot"></span>
            <span class="flow-dot d2"></span>
            <span class="flow-dot d3"></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-process {
  background: #f8fafb;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 24px;
  margin: 16px 0;
}

.process-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.brain-icon {
  position: relative;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brain-pulse {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(8, 145, 178, 0.15);
  animation: brain-pulse 2s ease-in-out infinite;
}

@keyframes brain-pulse {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.4); opacity: 0; }
}

.brain-el-icon {
  position: relative;
  z-index: 1;
  color: #0891b2;
}

.process-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.process-subtitle {
  font-size: 13px;
  color: #0891b2;
  margin: 2px 0 0;
  animation: fade-switch 1.8s ease infinite;
}

@keyframes fade-switch {
  0%, 100% { opacity: 1; }
  45%, 55% { opacity: 0.5; }
}

/* Pipeline */
.steps-pipeline {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
}

.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 0 0 auto;
}

.step-node {
  position: relative;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 2px solid #e2e8f0;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 2;
}

.is-completed .step-node {
  background: #0891b2;
  border-color: #0891b2;
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.3);
}

.is-active .step-node {
  border-color: #0891b2;
  box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.15);
  animation: node-pulse 1.5s ease-in-out infinite;
}

@keyframes node-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.15); }
  50% { box-shadow: 0 0 0 8px rgba(8, 145, 178, 0.08); }
}

.step-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 14px;
  border: 2px solid #0891b2;
  animation: ring-expand 1.5s ease-out infinite;
}

@keyframes ring-expand {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.5); opacity: 0; }
}

.step-icon {
  font-size: 22px;
  filter: grayscale(0);
  transition: filter 0.3s;
}

.is-pending .step-icon {
  filter: grayscale(0.8);
}

.is-completed .step-icon {
  filter: brightness(10);
}

.step-label {
  margin-top: 10px;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  white-space: nowrap;
  transition: color 0.3s;
}

.is-active .step-label {
  color: #0891b2;
}

.is-completed .step-label {
  color: #334155;
}

/* Connector */
.step-connector {
  position: absolute;
  top: 26px;
  left: 52px;
  width: 60px;
  height: 2px;
  background: #e2e8f0;
  z-index: 1;
}

.connector-fill {
  height: 100%;
  width: 0;
  background: #0891b2;
  transition: width 0.6s ease;
}

.connector-fill.filled {
  width: 100%;
}

/* Data flow animation */
.data-flow {
  position: absolute;
  top: -3px;
  left: 0;
  width: 100%;
  height: 8px;
  overflow: hidden;
}

.flow-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  background: #0891b2;
  border-radius: 50%;
  animation: flow-move 1.2s ease-in-out infinite;
}

.flow-dot.d2 { animation-delay: 0.3s; }
.flow-dot.d3 { animation-delay: 0.6s; }

@keyframes flow-move {
  0% { left: 0; opacity: 0; }
  20% { opacity: 1; }
  80% { opacity: 1; }
  100% { left: 100%; opacity: 0; }
}
</style>
