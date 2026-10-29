<script setup lang="ts">
/**
 * AI 成长时间线组件
 * 纵向时间轴 + 里程碑成就 + AI 预测趋势曲线
 * 每个节点 = 一次提交，显示分数变化、缩略雷达图、AI点评
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { LineChart, RadarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, MarkLineComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import api from '@/utils/request'
import { Cpu, ArrowUp, ArrowDown, Aim, Medal, TrophyBase, Promotion, Sunny, TrendCharts, DataAnalysis } from '@element-plus/icons-vue'

use([LineChart, RadarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps<{
  semesterId: number | null
}>()

const router = useRouter()
const loading = ref(false)
const submissions = ref<any[]>([])
const expandedNodes = ref<Set<number>>(new Set())

// ==================== 数据获取 ====================
const fetchSubmissions = async () => {
  if (!props.semesterId) return
  loading.value = true
  try {
    const res: any = await api.get('/submissions/my', {
      params: { semester_id: props.semesterId }
    })
    submissions.value = Array.isArray(res) ? res : (res.data || res.items || [])
  } catch (e) {
    console.warn('获取提交列表失败:', e)
    submissions.value = []
  } finally {
    loading.value = false
  }
}

// ==================== 时间线节点 ====================
interface TimelineNode {
  id: number
  date: Date
  dateStr: string
  taskTitle: string
  score: number
  prevScore: number | null
  change: number | null
  dimensions: Record<string, any> | null
  summary: string
  hasVideo: boolean
  status: string
}

const timelineNodes = computed<TimelineNode[]>(() => {
  const sorted = [...submissions.value]
    .filter(s => s.submitted_at || s.created_at)
    .sort((a, b) => {
      const da = new Date(a.submitted_at || a.created_at).getTime()
      const db = new Date(b.submitted_at || b.created_at).getTime()
      return da - db
    })

  return sorted.map((sub, idx) => {
    const analysis = typeof sub.lesson_plan_analysis === 'string'
      ? JSON.parse(sub.lesson_plan_analysis || '{}')
      : (sub.lesson_plan_analysis || {})
    const score = sub.total_score || analysis.overall_score || 0
    const prev = idx > 0 ? sorted[idx - 1] : null
    const prevAnalysis = prev
      ? (typeof prev.lesson_plan_analysis === 'string'
        ? JSON.parse(prev.lesson_plan_analysis || '{}')
        : (prev.lesson_plan_analysis || {}))
      : null
    const prevScore = prev ? (prev.total_score || prevAnalysis?.overall_score || 0) : null

    const d = new Date(sub.submitted_at || sub.created_at)
    return {
      id: sub.id,
      date: d,
      dateStr: `${d.getMonth() + 1}/${d.getDate()}`,
      taskTitle: sub.task_title || sub.task?.title || '提交作业',
      score,
      prevScore,
      change: prevScore !== null ? score - prevScore : null,
      dimensions: analysis.dimensions || null,
      summary: analysis.summary || '',
      hasVideo: !!sub.video_path,
      status: sub.status || '',
    }
  })
})

// ==================== 里程碑成就 ====================
interface Milestone {
  id: string
  icon: string
  label: string
  color: string
  bgColor: string
  nodeId?: number
}

const milestones = computed<Milestone[]>(() => {
  const ms: Milestone[] = []
  const nodes = timelineNodes.value
  if (nodes.length === 0) return ms

  // 首次提交
  ms.push({
    id: 'first',
    icon: 'Aim',
    label: '首次提交',
    color: '#0891b2',
    bgColor: '#ecfeff',
    nodeId: nodes[0].id,
  })

  // 首次 80+
  const first80 = nodes.find(n => n.score >= 80)
  if (first80) {
    ms.push({
      id: 'first80',
      icon: 'Medal',
      label: '首次 80+',
      color: '#f59e0b',
      bgColor: '#fffbeb',
      nodeId: first80.id,
    })
  }

  // 首次 90+
  const first90 = nodes.find(n => n.score >= 90)
  if (first90) {
    ms.push({
      id: 'first90',
      icon: 'TrophyBase',
      label: '首次 90+',
      color: '#10b981',
      bgColor: '#ecfdf5',
      nodeId: first90.id,
    })
  }

  // 最大单次进步
  let maxImp = 0
  let maxImpNode: TimelineNode | null = null
  for (const n of nodes) {
    if (n.change !== null && n.change > maxImp) {
      maxImp = n.change
      maxImpNode = n
    }
  }
  if (maxImpNode && maxImp >= 3) {
    ms.push({
      id: 'maxImprove',
      icon: 'Promotion',
      label: `最大进步 +${Math.round(maxImp)}`,
      color: '#0d9488',
      bgColor: '#f0fdfa',
      nodeId: maxImpNode.id,
    })
  }

  // 连续3次进步
  for (let i = 2; i < nodes.length; i++) {
    if (
      nodes[i].change !== null && nodes[i].change! > 0 &&
      nodes[i - 1].change !== null && nodes[i - 1].change! > 0 &&
      nodes[i - 2].change !== null && nodes[i - 2].change! > 0
    ) {
      ms.push({
        id: 'streak3',
        icon: 'Sunny',
        label: '连续3次进步',
        color: '#ef4444',
        bgColor: '#fef2f2',
        nodeId: nodes[i].id,
      })
      break
    }
  }

  return ms
})

// 节点对应的里程碑
const nodeMilestones = computed(() => {
  const map = new Map<number, Milestone[]>()
  for (const m of milestones.value) {
    if (m.nodeId) {
      const arr = map.get(m.nodeId) || []
      arr.push(m)
      map.set(m.nodeId, arr)
    }
  }
  return map
})

// ==================== AI 预测趋势图 ====================
const predictionText = ref('')

const predictionOption = computed(() => {
  const nodes = timelineNodes.value
  if (nodes.length < 2) return null

  const scores = nodes.map(n => n.score)
  const n = scores.length

  // 线性回归
  const xMean = (n - 1) / 2
  const yMean = scores.reduce((a, b) => a + b, 0) / n
  let numSum = 0
  let denSum = 0
  for (let i = 0; i < n; i++) {
    numSum += (i - xMean) * (scores[i] - yMean)
    denSum += (i - xMean) * (i - xMean)
  }
  const slope = denSum !== 0 ? numSum / denSum : 0

  // 预测3个未来点
  const labels: string[] = nodes.map((_n, i) => `第${i + 1}次`)
  const actual: (number | null)[] = [...scores]
  const predicted: (number | null)[] = new Array(n).fill(null)

  for (let i = 0; i < 3; i++) {
    const futureIdx = n + i
    const predScore = Math.min(100, Math.max(0, Math.round(yMean + slope * (futureIdx - xMean))))
    labels.push(`第${futureIdx + 1}次`)
    actual.push(null)
    predicted.push(predScore)
  }
  // 连接预测线的起点
  predicted[n - 1] = scores[n - 1]

  // 生成预测文本
  const lastPred = predicted[predicted.length - 1]
  if (lastPred !== null && slope > 0) {
    const targetScore = 90
    const stepsToTarget = Math.ceil((targetScore - scores[n - 1]) / slope)
    if (stepsToTarget > 0 && stepsToTarget < 20) {
      predictionText.value = `按当前趋势，第 ${n + stepsToTarget} 次提交预计可达 ${targetScore} 分`
    } else {
      predictionText.value = `AI 预测下次提交约 ${Math.min(100, Math.round(scores[n - 1] + slope))} 分`
    }
  } else if (slope < 0) {
    predictionText.value = '近期分数有所波动，建议针对薄弱维度加强练习'
  } else {
    predictionText.value = '保持当前水平，继续努力'
  }

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e7eb',
      textStyle: { color: '#374151', fontSize: 12 },
    },
    legend: {
      data: ['实际得分', 'AI 预测'],
      bottom: 0,
      textStyle: { color: '#9ca3af', fontSize: 11 },
    },
    grid: { top: 16, right: 24, bottom: 40, left: 45 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#9ca3af', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } },
      axisLabel: { color: '#9ca3af', fontSize: 11 },
    },
    series: [
      {
        name: '实际得分',
        type: 'line',
        data: actual,
        smooth: true,
        symbol: 'circle',
        symbolSize: 10,
        lineStyle: { color: '#0891b2', width: 3 },
        itemStyle: { color: '#0891b2', borderWidth: 2, borderColor: '#fff' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(99,102,241,0.25)' },
              { offset: 1, color: 'rgba(99,102,241,0.02)' },
            ],
          },
        },
        connectNulls: false,
      },
      {
        name: 'AI 预测',
        type: 'line',
        data: predicted,
        smooth: true,
        symbol: 'diamond',
        symbolSize: 8,
        lineStyle: { color: '#f59e0b', width: 2.5, type: 'dashed' },
        itemStyle: { color: '#f59e0b', borderWidth: 2, borderColor: '#fff' },
        connectNulls: false,
      },
    ],
  }
})

// ==================== 缩略雷达图配置 ====================
const getMiniRadarOption = (dimensions: Record<string, any>) => {
  if (!dimensions) return null

  const dimMap: Record<string, string> = {
    structure: '结构', objectives: '目标', key_points: '重难点',
    teaching_process: '过程', teaching_methods: '方法',
    board_design: '板书', language: '语言',
  }

  const entries = Object.entries(dimMap).filter(([key]) => dimensions[key])
  if (entries.length === 0) return null

  return {
    radar: {
      indicator: entries.map(([_, name]) => ({ name, max: 100 })),
      center: ['50%', '50%'],
      radius: '70%',
      axisName: { show: false },
      splitArea: { show: false },
      splitLine: { lineStyle: { color: 'rgba(99,102,241,0.1)' } },
      axisLine: { lineStyle: { color: 'rgba(99,102,241,0.15)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: entries.map(([key]) => dimensions[key]?.score || 0),
        lineStyle: { color: '#0891b2', width: 1.5 },
        areaStyle: { color: 'rgba(99,102,241,0.2)' },
        itemStyle: { color: '#0891b2', borderWidth: 0 },
        symbol: 'none',
      }],
    }],
  }
}

// ==================== 交互 ====================
const toggleExpand = (nodeId: number) => {
  if (expandedNodes.value.has(nodeId)) {
    expandedNodes.value.delete(nodeId)
  } else {
    expandedNodes.value.add(nodeId)
  }
}

const goToReport = (nodeId: number) => {
  router.push(`/student/ai-report/${nodeId}`)
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#0891b2'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

const getScoreLevel = (score: number) => {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '中等'
  if (score >= 60) return '及格'
  return '待提高'
}

// ==================== 生命周期 ====================
watch(() => props.semesterId, () => {
  fetchSubmissions()
}, { immediate: true })
</script>

<template>
  <div class="ai-growth-timeline" v-loading="loading">
    <!-- 无数据 -->
    <div v-if="!loading && timelineNodes.length === 0" class="empty-state">
      <div class="empty-icon"><el-icon :size="48"><DataAnalysis /></el-icon></div>
      <p>暂无提交记录，完成作业后将生成成长时间线</p>
    </div>

    <template v-if="timelineNodes.length > 0">
      <!-- 里程碑成就 -->
      <div v-if="milestones.length > 0" class="milestones-section">
        <div class="milestones-title">
          <el-icon class="milestones-icon"><TrophyBase /></el-icon>
          <span>成就徽章</span>
        </div>
        <div class="milestones-row">
          <div
            v-for="m in milestones"
            :key="m.id"
            class="milestone-badge"
            :style="{ background: m.bgColor, borderColor: m.color + '40' }"
          >
            <el-icon class="badge-icon"><component :is="m.icon" /></el-icon>
            <span class="badge-label" :style="{ color: m.color }">{{ m.label }}</span>
            <div class="badge-sparkle"></div>
          </div>
        </div>
      </div>

      <!-- AI 预测趋势图 -->
      <div v-if="predictionOption" class="prediction-section">
        <div class="prediction-header">
          <div class="prediction-title">
            <el-icon class="text-cyan-600"><Cpu /></el-icon>
            <span>AI 预测趋势</span>
          </div>
          <div v-if="predictionText" class="prediction-text">
            <el-icon class="pred-icon"><TrendCharts /></el-icon>
            {{ predictionText }}
          </div>
        </div>
        <div class="prediction-chart">
          <v-chart :option="predictionOption" autoresize style="height: 220px;" />
        </div>
      </div>

      <!-- 时间线主体 -->
      <div class="timeline-section">
        <div class="timeline-title">
          <span class="timeline-title-dot"></span>
          <span>提交时间线</span>
          <span class="timeline-count">共 {{ timelineNodes.length }} 次提交</span>
        </div>

        <div class="timeline-body">
          <div class="timeline-track"></div>

          <div
            v-for="(node, idx) in [...timelineNodes].reverse()"
            :key="node.id"
            class="timeline-node"
            :class="{ expanded: expandedNodes.has(node.id) }"
            @click="toggleExpand(node.id)"
          >
            <!-- 时间线圆点 -->
            <div class="node-dot-container">
              <div
                class="node-dot"
                :style="{
                  borderColor: getScoreColor(node.score),
                  background: expandedNodes.has(node.id)
                    ? getScoreColor(node.score)
                    : 'white',
                }"
              >
                <span v-if="expandedNodes.has(node.id)" class="dot-check">✓</span>
              </div>
              <!-- 里程碑标识 -->
              <div
                v-for="m in (nodeMilestones.get(node.id) || [])"
                :key="m.id"
                class="node-milestone"
                :style="{ background: m.bgColor, color: m.color }"
              >
                <el-icon><component :is="m.icon" /></el-icon> {{ m.label }}
              </div>
            </div>

            <!-- 节点内容 -->
            <div class="node-card">
              <div class="node-header">
                <div class="node-date">{{ node.dateStr }}</div>
                <div class="node-task-title">{{ node.taskTitle }}</div>
                <div class="node-score-group">
                  <span
                    class="node-score"
                    :style="{ color: getScoreColor(node.score) }"
                  >
                    {{ node.score }}
                  </span>
                  <span class="node-score-unit">分</span>
                  <span
                    v-if="node.change !== null && node.change !== 0"
                    class="node-change"
                    :class="node.change > 0 ? 'up' : 'down'"
                  >
                    <el-icon v-if="node.change > 0"><ArrowUp /></el-icon>
                    <el-icon v-else><ArrowDown /></el-icon>
                    {{ Math.abs(node.change) }}
                  </span>
                </div>
                <span
                  class="node-level-tag"
                  :style="{
                    color: getScoreColor(node.score),
                    background: getScoreColor(node.score) + '15',
                  }"
                >
                  {{ getScoreLevel(node.score) }}
                </span>
              </div>

              <!-- 展开详情 -->
              <Transition name="expand">
                <div v-if="expandedNodes.has(node.id)" class="node-detail">
                  <div class="detail-grid">
                    <!-- 缩略雷达图 -->
                    <div v-if="node.dimensions" class="mini-radar">
                      <v-chart
                        :option="getMiniRadarOption(node.dimensions) as any"
                        autoresize
                        style="height: 140px;"
                      />
                    </div>

                    <!-- AI 点评 -->
                    <div class="ai-comment-section">
                      <div class="ai-comment-header">
                        <span class="ai-dot"></span>
                        <span>AI 点评</span>
                      </div>
                      <p v-if="node.summary" class="ai-comment-text">
                        {{ node.summary }}
                      </p>
                      <p v-else class="ai-comment-placeholder">
                        暂无 AI 评语
                      </p>
                    </div>
                  </div>

                  <!-- 快捷操作 -->
                  <div class="detail-actions">
                    <el-button
                      v-if="node.hasVideo"
                      size="small"
                      type="primary"
                      text
                      @click.stop="goToReport(node.id)"
                    >
                      <el-icon class="mr-1"><Cpu /></el-icon>
                      AI 诊断报告
                    </el-button>
                    <el-tag
                      v-if="node.status"
                      size="small"
                      :type="node.status === 'approved' ? 'success' : node.status === 'rejected' ? 'danger' : 'info'"
                      effect="plain"
                    >
                      {{ node.status === 'approved' ? '已通过' : node.status === 'rejected' ? '需修改' : node.status === 'reviewed' ? '已评审' : '待评审' }}
                    </el-tag>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-growth-timeline {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.6;
}

.empty-state p {
  font-size: 14px;
  color: #9ca3af;
}

/* ==================== 里程碑成就 ==================== */
.milestones-section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid #f1f5f9;
}

.milestones-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 14px;
}

.milestones-icon {
  font-size: 18px;
}

.milestones-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.milestone-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 24px;
  border: 1px solid;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s;
}

.milestone-badge:hover {
  transform: translateY(-2px);
}

.badge-icon {
  font-size: 18px;
}

.badge-label {
  font-size: 13px;
  font-weight: 600;
}

.badge-sparkle {
  position: absolute;
  top: -2px;
  right: 8px;
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
  opacity: 0;
  animation: sparkle 3s infinite;
}

@keyframes sparkle {
  0%, 80%, 100% { opacity: 0; transform: scale(0); }
  90% { opacity: 0.8; transform: scale(1); }
}

/* ==================== AI 预测趋势 ==================== */
.prediction-section {
  background: white;
  border-radius: 16px;
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.prediction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f3f4f6;
  flex-wrap: wrap;
  gap: 8px;
}

.prediction-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}

.prediction-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #f59e0b;
  background: #fffbeb;
  padding: 4px 14px;
  border-radius: 20px;
  font-weight: 500;
}

.pred-icon {
  font-size: 14px;
}

.prediction-chart {
  padding: 8px 12px 4px;
}

/* ==================== 时间线主体 ==================== */
.timeline-section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid #f1f5f9;
}

.timeline-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 20px;
}

.timeline-title-dot {
  width: 4px;
  height: 16px;
  background: #0891b2;
  border-radius: 2px;
}

.timeline-count {
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
  margin-left: auto;
}

.timeline-body {
  position: relative;
  padding-left: 28px;
}

.timeline-track {
  position: absolute;
  left: 11px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #0891b2;
  border-radius: 1px;
}

.timeline-node {
  position: relative;
  margin-bottom: 16px;
  cursor: pointer;
}

.timeline-node:last-child {
  margin-bottom: 0;
}

/* 圆点 */
.node-dot-container {
  position: absolute;
  left: -28px;
  top: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.node-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 3px solid;
  background: white;
  z-index: 1;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dot-check {
  font-size: 10px;
  color: white;
  font-weight: 700;
}

.node-milestone {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
  position: absolute;
  left: 28px;
  top: -8px;
  animation: fadeInScale 0.3s ease;
}

@keyframes fadeInScale {
  from { opacity: 0; transform: scale(0.8); }
  to { opacity: 1; transform: scale(1); }
}

/* 节点卡片 */
.node-card {
  background: #f9fafb;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 14px 18px;
  transition: all 0.2s;
}

.timeline-node:hover .node-card {
  border-color: #cffafe;
  box-shadow: 0 2px 8px rgba(8, 145, 178, 0.08);
}

.timeline-node.expanded .node-card {
  border-color: #c7d2fe;
  background: white;
  box-shadow: 0 4px 16px rgba(8, 145, 178, 0.1);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.node-date {
  font-size: 12px;
  color: #9ca3af;
  font-family: 'Tabular Nums', monospace;
  min-width: 40px;
}

.node-task-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-score-group {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.node-score {
  font-size: 24px;
  font-weight: 800;
  line-height: 1;
}

.node-score-unit {
  font-size: 12px;
  color: #9ca3af;
}

.node-change {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 700;
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 8px;
}

.node-change.up {
  color: #10b981;
  background: #ecfdf5;
}

.node-change.down {
  color: #ef4444;
  background: #fef2f2;
}

.node-level-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 10px;
}

/* 展开详情 */
.node-detail {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #f3f4f6;
}

.detail-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 16px;
  align-items: start;
}

@media (max-width: 640px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

.mini-radar {
  background: #fafafa;
  border-radius: 10px;
  overflow: hidden;
}

.ai-comment-section {
  min-width: 0;
}

.ai-comment-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #0891b2;
  margin-bottom: 6px;
}

.ai-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0891b2;
  animation: ai-pulse 2s infinite;
}

@keyframes ai-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.ai-comment-text {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.7;
  margin: 0;
}

.ai-comment-placeholder {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.mr-1 {
  margin-right: 4px;
}

/* 展开动画 */
.expand-enter-active {
  animation: expandIn 0.3s ease;
}

.expand-leave-active {
  animation: expandIn 0.2s ease reverse;
}

@keyframes expandIn {
  from {
    opacity: 0;
    max-height: 0;
    margin-top: 0;
    padding-top: 0;
    overflow: hidden;
  }
  to {
    opacity: 1;
    max-height: 300px;
    margin-top: 14px;
    padding-top: 14px;
  }
}
</style>
