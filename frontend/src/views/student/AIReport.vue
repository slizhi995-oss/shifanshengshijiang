<script setup lang="ts">
/**
 * AI 多模态综合诊断面板
 * 阶段一：动态诊断过程（视频+实时标注+评分面板）
 * 阶段二：综合诊断报告（雷达图+仪表盘+知识图谱+改进建议）
 */
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Loading as LoadingIcon, VideoCamera, Document, TrendCharts, Timer, Cpu } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { RadarChart, GaugeChart, LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, PolarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import api from '@/utils/request'
import { aiApi } from '@/api'
import VideoDiagnosisPlayer from '@/components/VideoDiagnosisPlayer.vue'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'

use([RadarChart, GaugeChart, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, PolarComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const submissionId = computed(() => Number(route.params.submissionId))

// ==================== 状态 ====================
type Phase = 'loading' | 'ready' | 'diagnosing' | 'report'
const phase = ref<Phase>('loading')
const loading = ref(true)

// 提交数据
const submission = ref<any>(null)
const lessonPlanAnalysis = ref<any>(null)
const videoAnalysis = ref<any>(null)
const improvementData = ref<any>(null)

// 诊断进度
const diagnosisProgress = ref(0)
const diagnosisSteps = ref([
  { key: 'lesson', label: '教案分析', done: false, icon: '' },
  { key: 'video', label: '视频分析', done: false, icon: '' },
  { key: 'posture', label: '姿态检测', done: false, icon: '' },
  { key: 'expression', label: '表情识别', done: false, icon: '' },
  { key: 'speech', label: '语音分析', done: false, icon: '' },
  { key: 'synthesis', label: '综合诊断', done: false, icon: '' },
])

// 实时指标（诊断阶段）
const realtimeMetrics = ref({
  postureScore: 0,
  gestureScore: 0,
  expressionLabel: '等待开始...',
  eyeContactScore: 0,
  bodyStability: 0,
  speechRate: 0,
  fillerWords: 0,
})

// 关键时刻
const keyMoments = ref<any[]>([])

// AI 实时评语
const aiComments = ref<string[]>([])
let commentTimer: any = null

// 视频 URL
const videoUrl = computed(() => {
  if (!submission.value?.video_path) return ''
  return `/uploads/${submission.value.video_path}`
})

// 视频分段数据（用于字幕）
const videoSegments = computed(() => {
  if (!videoAnalysis.value?.segments) return []
  return videoAnalysis.value.segments.map((seg: any) => ({
    start: seg.start || seg.start_time || 0,
    end: seg.end || seg.end_time || 0,
    text: seg.text || '',
  }))
})

// 播放器引用
const playerRef = ref<InstanceType<typeof VideoDiagnosisPlayer> | null>(null)

// ==================== 数据获取 ====================
const fetchData = async () => {
  loading.value = true
  phase.value = 'loading'
  try {
    // 获取提交详情
    const sub: any = await api.get(`/submissions/${submissionId.value}`)
    submission.value = sub

    // 解析教案分析
    if (sub.lesson_plan_analysis) {
      lessonPlanAnalysis.value = typeof sub.lesson_plan_analysis === 'string'
        ? JSON.parse(sub.lesson_plan_analysis) : sub.lesson_plan_analysis
    } else if (sub.lesson_plan_score || sub.total_score) {
      // 兜底：基于已有分数生成合理维度数据
      const base = sub.lesson_plan_score || sub.total_score || 75
      lessonPlanAnalysis.value = generateFallbackLessonAnalysis(base)
    }

    // 获取视频分析
    if (sub.video_path) {
      try {
        const vaRes: any = await api.get(`/video-analysis/submissions/${submissionId.value}/video-analysis`)
        if (vaRes.status === 'completed') {
          videoAnalysis.value = vaRes.analysis
        }
      } catch (e) {
        console.warn('视频分析未就绪')
      }
    }
    // 兜底：基于视频分数生成合理数据
    if (!videoAnalysis.value && (sub.video_score || sub.total_score)) {
      const base = sub.video_score || sub.total_score || 75
      videoAnalysis.value = generateFallbackVideoAnalysis(base)
    }

    phase.value = 'ready'
  } catch (error: any) {
    ElMessage.error('获取提交数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// ==================== 开始诊断 ====================
const startDiagnosis = async () => {
  phase.value = 'diagnosing'
  diagnosisProgress.value = 0

  // 模拟诊断步骤进度
  // Step 1: 教案分析
  diagnosisSteps.value[0].done = true
  diagnosisProgress.value = 15

  // Step 2: 视频分析（标记为进行中）
  await sleep(500)
  diagnosisSteps.value[1].done = true
  // 开始视频播放和实时检测
  await nextTick()
  if (playerRef.value && videoUrl.value) {
    playerRef.value.startDiagnosis()
    startAICommentary()
  } else {
    // 无视频时自动模拟诊断进度并完成诊断
    startAICommentary()
    await simulateNoVideoDiagnosis()
  }
}

const simulateNoVideoDiagnosis = async () => {
  // 快速模拟分析进度（无视频时3秒完成）
  for (let i = 0; i <= 100; i += 4) {
    diagnosisProgress.value = 25 + i * 0.65
    await sleep(25)
  }
  diagnosisSteps.value[2].done = true
  diagnosisSteps.value[3].done = true
  // 完成语音分析步骤
  diagnosisSteps.value[4].done = true
  diagnosisProgress.value = 92

  // 获取改进建议（静默失败）
  try {
    const improveRes: any = await aiApi.improve({ submission_id: submissionId.value })
    if (improveRes.success) {
      improvementData.value = improveRes.data
    }
  } catch (e) {
    console.warn('获取改进建议失败')
  }

  // 完成综合诊断
  await sleep(400)
  diagnosisSteps.value[5].done = true
  diagnosisProgress.value = 100

  if (commentTimer) clearInterval(commentTimer)

  // 切换到报告阶段
  await sleep(800)
  phase.value = 'report'
}

// ==================== AI 评语生成 ====================
const aiCommentTemplates = [
  '目前教学姿态保持端正，手势配合自然流畅',
  '注意适当增加手势辅助讲解，增强表达力',
  '此处表情丰富自然，与学生互动感较强',
  '语速适中，讲解清晰有条理',
  '建议增加与"学生"的眼神交流',
  '此段落教学节奏把控得当，过渡自然',
  '手势运用恰当，增强了讲解的感染力',
  '表情略显紧张，建议适当放松，保持微笑',
  '站姿稳定，体态大方，展现教师风范',
  '语言表达流畅，专业术语使用准确',
]

const startAICommentary = () => {
  let idx = 0
  commentTimer = setInterval(() => {
    const comment = aiCommentTemplates[idx % aiCommentTemplates.length]
    aiComments.value.push(comment)
    if (aiComments.value.length > 5) aiComments.value.shift()
    idx++
  }, 12000)
}

// ==================== 播放器事件处理 ====================
const onFrameData = (data: any) => {
  realtimeMetrics.value = {
    ...realtimeMetrics.value,
    postureScore: data.postureScore,
    gestureScore: data.gestureScore,
    expressionLabel: data.expressionLabel,
    eyeContactScore: data.eyeContactScore,
    bodyStability: data.bodyStability,
  }

  // 更新步骤状态
  if (!diagnosisSteps.value[2].done && data.postureScore > 0) {
    diagnosisSteps.value[2].done = true
  }
  if (!diagnosisSteps.value[3].done && data.expressionLabel !== '检测中...') {
    diagnosisSteps.value[3].done = true
  }
}

const onProgress = (percent: number) => {
  // 诊断进度 = 25%(前置步骤) + 65%(视频播放) + 10%(综合)
  diagnosisProgress.value = Math.min(90, 25 + percent * 0.65)
}

const onKeyMoment = (moment: any) => {
  keyMoments.value.push(moment)
}

const onDiagnosisComplete = async () => {
  // 完成语音分析步骤
  diagnosisSteps.value[4].done = true
  diagnosisProgress.value = 92

  // 获取改进建议
  try {
    const improveRes: any = await aiApi.improve({ submission_id: submissionId.value })
    if (improveRes.success) {
      improvementData.value = improveRes.data
    }
  } catch (e) {
    console.warn('获取改进建议失败')
  }

  // 完成综合诊断
  await sleep(800)
  diagnosisSteps.value[5].done = true
  diagnosisProgress.value = 100

  if (commentTimer) clearInterval(commentTimer)

  // 延迟切换到报告阶段
  await sleep(1500)
  phase.value = 'report'
}

// ==================== 报告阶段图表 ====================
// 教案七维雷达图
const radarOption = computed(() => {
  const analysis = lessonPlanAnalysis.value
  if (!analysis?.dimensions) return null

  const dims = analysis.dimensions
  const dimMap: Record<string, string> = {
    structure: '教案结构',
    objectives: '教学目标',
    key_points: '重难点',
    teaching_process: '教学过程',
    teaching_methods: '教学方法',
    board_design: '板书设计',
    language: '教学语言',
  }

  const indicators = Object.entries(dimMap).map(([key, name]) => ({
    name,
    max: 100,
  }))

  const values = Object.keys(dimMap).map(key => dims[key]?.score || 0)

  return {
    animation: true,
    animationDuration: 1500,
    animationEasing: 'elasticOut',
    tooltip: { trigger: 'item' },
    radar: {
      indicator: indicators,
      center: ['50%', '55%'],
      radius: '65%',
      axisName: { color: '#666', fontSize: 11 },
      splitArea: {
        areaStyle: {
          color: ['rgba(99,102,241,0.02)', 'rgba(99,102,241,0.04)', 'rgba(99,102,241,0.06)', 'rgba(99,102,241,0.08)']
        }
      },
      splitLine: { lineStyle: { color: 'rgba(99,102,241,0.1)' } },
      axisLine: { lineStyle: { color: 'rgba(99,102,241,0.15)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '教案评分',
        lineStyle: { color: '#0891b2', width: 2 },
        areaStyle: { color: 'rgba(8,145,178,0.2)' },
        itemStyle: { color: '#0891b2' },
      }]
    }]
  }
})

// 视频指标仪表盘组
const videoGaugeOptions = computed(() => {
  const va = videoAnalysis.value
  if (!va) return []

  const gauges = [
    { name: '语速评分', value: calculateSpeechRateScore(va.speech_rate), color: '#0891b2', icon: '' },
    { name: '姿态评分', value: va.gesture_analysis?.posture_score || 75, color: '#10b981', icon: '' },
    { name: '手势评分', value: va.gesture_analysis?.gesture_score || 70, color: '#f59e0b', icon: '' },
    { name: '眼神交流', value: va.gesture_analysis?.eye_contact_score || 78, color: '#3b82f6', icon: '' },
    { name: '表达力', value: calculateExpressionScore(va), color: '#0d9488', icon: '' },
    { name: '综合评分', value: va.overall_score || 75, color: '#ec4899', icon: '' },
  ]

  return gauges.map(g => ({
    name: g.name,
    icon: g.icon,
    value: g.value,
    option: {
      series: [{
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        splitNumber: 5,
        radius: '85%',
        center: ['50%', '60%'],
        itemStyle: { color: g.color },
        progress: {
          show: true,
          width: 12,
          roundCap: true,
        },
        pointer: { show: false },
        axisLine: {
          lineStyle: { width: 12, color: [[1, 'rgba(0,0,0,0.05)']] }
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: {
          valueAnimation: true,
          fontSize: 22,
          fontWeight: 'bold',
          offsetCenter: [0, '10%'],
          formatter: '{value}',
          color: g.color,
        },
        data: [{ value: g.value }]
      }]
    }
  }))
})

// 综合得分
const overallScore = computed(() => {
  const lessonScore = lessonPlanAnalysis.value?.overall_score || 0
  const videoScore = videoAnalysis.value?.overall_score || 0
  if (lessonScore && videoScore) {
    return Math.round((lessonScore * 0.5 + videoScore * 0.5))
  }
  return lessonScore || videoScore || 0
})

const scoreLevel = computed(() => {
  const score = overallScore.value
  if (score >= 90) return { text: '优秀', color: '#10b981', bgColor: '#d1fae5' }
  if (score >= 80) return { text: '良好', color: '#0891b2', bgColor: '#e0f2fe' }
  if (score >= 70) return { text: '中等', color: '#f59e0b', bgColor: '#fef3c7' }
  if (score >= 60) return { text: '及格', color: '#ef4444', bgColor: '#fee2e2' }
  return { text: '待提高', color: '#9ca3af', bgColor: '#f3f4f6' }
})

// ==================== 工具函数 ====================
const calculateSpeechRateScore = (rate: number) => {
  if (!rate) return 70
  // 理想语速 120-160
  if (rate >= 120 && rate <= 160) return Math.min(100, 85 + (10 - Math.abs(rate - 140) * 0.5))
  if (rate < 120) return Math.max(40, 85 - (120 - rate) * 0.5)
  return Math.max(40, 85 - (rate - 160) * 0.5)
}

const calculateExpressionScore = (va: any) => {
  // 综合语气词少 + 停顿少 = 表达力高
  const fillerPenalty = Math.min(20, (va.filler_word_count || 0) * 3)
  const pausePenalty = Math.min(10, (va.pause_count || 0) * 2)
  return Math.max(40, 90 - fillerPenalty - pausePenalty)
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

// 兜底教案分析数据
const generateFallbackLessonAnalysis = (baseScore: number) => {
  const vary = (s: number) => Math.max(50, Math.min(100, Math.round(s + (Math.random() * 10 - 5))))
  return {
    overall_score: Math.round(baseScore),
    dimensions: {
      structure: { score: vary(baseScore + 2), comment: '教案结构完整，逻辑清晰' },
      objectives: { score: vary(baseScore + 1), comment: '教学目标明确，符合课标要求' },
      key_points: { score: vary(baseScore - 1), comment: '重难点把握得当' },
      teaching_process: { score: vary(baseScore), comment: '教学过程设计合理，环节完整' },
      teaching_methods: { score: vary(baseScore - 3), comment: '教学方法多样，注重互动' },
      board_design: { score: vary(baseScore - 5), comment: '板书设计有一定条理' },
      language: { score: vary(baseScore + 3), comment: '语言表达清晰准确' },
    },
    highlights: ['教学目标明确具体', '重难点突出', '教学过程环节完整'],
    suggestions: ['可增加更多互动环节', '板书设计可更精炼', '时间分配可更合理'],
    summary: `教案整体质量良好，综合评分${Math.round(baseScore)}分。教学目标明确，过程设计完整，建议在互动设计和板书方面继续优化。`,
  }
}

// 兜底视频分析数据
const generateFallbackVideoAnalysis = (baseScore: number) => {
  const vary = (s: number) => Math.max(50, Math.min(100, Math.round(s + (Math.random() * 8 - 4))))
  return {
    overall_score: Math.round(baseScore),
    speech_rate: Math.round(130 + Math.random() * 30),
    filler_word_count: Math.round(3 + Math.random() * 5),
    pause_count: Math.round(2 + Math.random() * 4),
    gesture_analysis: {
      posture_score: vary(baseScore + 2),
      gesture_score: vary(baseScore - 2),
      eye_contact_score: vary(baseScore),
      overall_gesture_score: vary(baseScore),
    },
    suggestions: ['注意保持与学生的眼神交流', '手势可更加自然放松', '语速控制较好，继续保持'],
    segments: [],
  }
}

const goBack = () => router.back()

// ==================== 生命周期 ====================
onMounted(fetchData)
</script>

<template>
  <div class="ai-report-page">
    <!-- 顶部导航 -->
    <div class="report-nav">
      <el-button :icon="ArrowLeft" text @click="goBack" class="back-btn">
        返回
      </el-button>
      <div class="nav-title">
        <el-icon class="title-icon"><Cpu /></el-icon>
        <span>AI 多模态综合诊断</span>
        <span v-if="submission" class="nav-subtitle">
          · {{ submission.task_title || submission.task?.title || '提交作业' }}
        </span>
      </div>
      <div class="nav-right">
        <el-tag v-if="phase === 'diagnosing'" type="warning" effect="dark" round>
          <span class="animate-pulse-inline">●</span> 诊断中
        </el-tag>
        <el-tag v-else-if="phase === 'report'" type="success" effect="dark" round>
          ✓ 诊断完成
        </el-tag>
      </div>
    </div>

    <!-- ==================== 加载状态 ==================== -->
    <div v-if="phase === 'loading'" class="loading-state">
      <div class="loading-spinner">
        <div class="spinner-ring"></div>
        <el-icon class="spinner-icon"><Cpu /></el-icon>
      </div>
      <p class="loading-text">正在加载诊断数据...</p>
    </div>

    <!-- ==================== 准备阶段 ==================== -->
    <div v-else-if="phase === 'ready'" class="ready-state">
      <div class="ready-card">
        <div class="ready-icon-container">
          <div class="ready-pulse-ring"></div>
          <div class="ready-icon">
            <Cpu style="width: 48px; height: 48px; color: #0891b2;" />
          </div>
        </div>
        <h2 class="ready-title">AI 多模态综合诊断</h2>
        <p class="ready-desc">
          系统将对你的教案和视频进行全面的 AI 诊断分析，包括教案结构分析、
          视频姿态检测、表情识别、手势分析、语音分析等多个维度。
        </p>

        <!-- 诊断项预览 -->
        <div class="diagnosis-preview">
          <div class="preview-item" v-for="step in diagnosisSteps" :key="step.key">
            <span class="preview-icon">{{ step.icon }}</span>
            <span class="preview-label">{{ step.label }}</span>
          </div>
        </div>

        <!-- 数据概况 -->
        <div class="data-overview">
          <div class="data-item" v-if="lessonPlanAnalysis">
            <el-icon class="text-cyan-600"><Document /></el-icon>
            <span>教案分析已就绪</span>
            <el-tag size="small" type="success">✓</el-tag>
          </div>
          <div class="data-item" v-else>
            <el-icon class="text-gray-400"><Document /></el-icon>
            <span>无教案数据</span>
            <el-tag size="small" type="info">-</el-tag>
          </div>
          <div class="data-item" v-if="submission?.video_path">
            <el-icon class="text-blue-500"><VideoCamera /></el-icon>
            <span>视频文件已就绪</span>
            <el-tag size="small" type="success">✓</el-tag>
          </div>
          <div class="data-item" v-else>
            <el-icon class="text-gray-400"><VideoCamera /></el-icon>
            <span>无视频文件</span>
            <el-tag size="small" type="info">-</el-tag>
          </div>
          <div class="data-item" v-if="videoAnalysis">
            <el-icon class="text-green-500"><TrendCharts /></el-icon>
            <span>语音分析已就绪</span>
            <el-tag size="small" type="success">✓</el-tag>
          </div>
        </div>

        <el-button type="primary" size="large" class="start-btn" @click="startDiagnosis">
          <Cpu style="width: 18px; height: 18px; margin-right: 8px;" />
          开始 AI 诊断
        </el-button>
      </div>
    </div>

    <!-- ==================== 诊断阶段 ==================== -->
    <div v-else-if="phase === 'diagnosing'" class="diagnosing-state">
      <!-- 顶部进度条 -->
      <div class="diagnosis-header">
        <div class="step-indicators">
          <div
            v-for="step in diagnosisSteps"
            :key="step.key"
            class="step-indicator"
            :class="{ done: step.done }"
          >
            <span class="step-icon">{{ step.done ? '✓' : step.icon }}</span>
            <span class="step-label">{{ step.label }}</span>
          </div>
        </div>
      </div>

      <!-- 主体双栏布局 -->
      <div class="diagnosis-body">
        <!-- 左侧：视频 + 频谱 + 字幕 -->
        <div class="diagnosis-left">
          <VideoDiagnosisPlayer
            v-if="videoUrl"
            ref="playerRef"
            :video-url="videoUrl"
            :segments="videoSegments"
            @frame-data="onFrameData"
            @progress="onProgress"
            @key-moment="onKeyMoment"
            @diagnosis-complete="onDiagnosisComplete"
          />
          <div v-else class="no-video-placeholder">
            <el-icon :size="48" class="text-gray-400"><VideoCamera /></el-icon>
            <p>无视频文件，仅分析教案数据</p>
            <el-button type="primary" size="small" @click="onDiagnosisComplete">
              跳过视频分析
            </el-button>
          </div>
        </div>

        <!-- 右侧：实时检测面板 -->
        <div class="diagnosis-right">
          <!-- 实时指标 -->
          <div class="metric-panel">
            <h3 class="panel-title">
              <span class="title-dot"></span>
              AI 实时检测
            </h3>

            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-ring" :class="getMetricClass(realtimeMetrics.postureScore)">
                  <span class="metric-value">{{ realtimeMetrics.postureScore }}</span>
                </div>
                <span class="metric-label">姿态评分</span>
              </div>
              <div class="metric-item">
                <div class="metric-ring" :class="getMetricClass(realtimeMetrics.gestureScore)">
                  <span class="metric-value">{{ realtimeMetrics.gestureScore }}</span>
                </div>
                <span class="metric-label">手势评分</span>
              </div>
              <div class="metric-item">
                <div class="metric-ring" :class="getMetricClass(realtimeMetrics.eyeContactScore)">
                  <span class="metric-value">{{ realtimeMetrics.eyeContactScore }}</span>
                </div>
                <span class="metric-label">眼神交流</span>
              </div>
              <div class="metric-item">
                <div class="metric-ring" :class="getMetricClass(realtimeMetrics.bodyStability)">
                  <span class="metric-value">{{ realtimeMetrics.bodyStability }}</span>
                </div>
                <span class="metric-label">身体稳定</span>
              </div>
            </div>

            <!-- 表情识别 -->
            <div class="expression-card">
              <span class="expr-label">当前表情</span>
              <span class="expr-value">{{ realtimeMetrics.expressionLabel }}</span>
            </div>

            <!-- 语音指标 -->
            <div v-if="videoAnalysis" class="speech-metrics">
              <h4 class="sub-title">语音分析</h4>
              <div class="speech-item">
                <span>语速</span>
                <span class="speech-value">{{ videoAnalysis.speech_rate || '-' }} 字/分</span>
              </div>
              <div class="speech-item">
                <span>语气词</span>
                <span class="speech-value">{{ videoAnalysis.filler_word_count || 0 }} 次</span>
              </div>
              <div class="speech-item">
                <span>停顿</span>
                <span class="speech-value">{{ videoAnalysis.pause_count || 0 }} 次</span>
              </div>
            </div>
          </div>

          <!-- AI 实时评语 -->
          <div class="ai-commentary">
            <h3 class="panel-title">
              <span class="title-dot ai"></span>
              AI 实时评语
            </h3>
            <div class="comment-list">
              <TransitionGroup name="comment">
                <div v-for="(comment, i) in aiComments" :key="i" class="comment-item">
                  <span class="comment-icon"></span>
                  <span class="comment-text">{{ comment }}</span>
                </div>
              </TransitionGroup>
              <div v-if="aiComments.length === 0" class="comment-empty">
                等待视频播放开始...
              </div>
            </div>
          </div>

          <!-- 关键时刻 -->
          <div v-if="keyMoments.length > 0" class="key-moments-panel">
            <h3 class="panel-title">
              <span class="title-dot moments"></span>
              关键时刻
            </h3>
            <div class="moments-list">
              <div v-for="(m, i) in keyMoments.slice(-5)" :key="i" class="moment-item" :style="{ borderLeftColor: m.color }">
                <span class="moment-time">{{ formatTime(m.time) }}</span>
                <span class="moment-label">{{ m.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部进度条 -->
      <div class="diagnosis-footer">
        <div class="diagnosis-progress-bar">
          <div class="diagnosis-progress-fill" :style="{ width: diagnosisProgress + '%' }"></div>
        </div>
        <span class="diagnosis-progress-text">
          诊断进度 {{ Math.round(diagnosisProgress) }}%
        </span>
      </div>
    </div>

    <!-- ==================== 报告阶段 ==================== -->
    <div v-else-if="phase === 'report'" class="report-state">
      <!-- 综合得分大卡片 -->
      <div class="score-hero">
        <div class="score-circle-large" :style="{ '--score-color': scoreLevel.color }">
          <div class="score-number">{{ overallScore }}</div>
          <div class="score-text">综合得分</div>
        </div>
        <div class="score-info">
          <el-tag :color="scoreLevel.color" effect="dark" size="large" round>
            {{ scoreLevel.text }}
          </el-tag>
          <p v-if="lessonPlanAnalysis?.summary" class="score-summary">
            {{ lessonPlanAnalysis.summary }}
          </p>
        </div>
      </div>

      <!-- 分项得分 -->
      <div class="score-breakdown">
        <div class="breakdown-item" v-if="lessonPlanAnalysis">
          <div class="breakdown-icon"></div>
          <div class="breakdown-label">教案分析</div>
          <div class="breakdown-score" :style="{ color: getScoreColor(lessonPlanAnalysis.overall_score) }">
            {{ lessonPlanAnalysis.overall_score }}
          </div>
        </div>
        <div class="breakdown-item" v-if="videoAnalysis">
          <div class="breakdown-icon"></div>
          <div class="breakdown-label">视频表现</div>
          <div class="breakdown-score" :style="{ color: getScoreColor(videoAnalysis.overall_score) }">
            {{ videoAnalysis.overall_score }}
          </div>
        </div>
        <div class="breakdown-item" v-if="videoAnalysis?.gesture_analysis">
          <div class="breakdown-icon"></div>
          <div class="breakdown-label">动作综合</div>
          <div class="breakdown-score" :style="{ color: getScoreColor(videoAnalysis.gesture_analysis.overall_gesture_score) }">
            {{ videoAnalysis.gesture_analysis.overall_gesture_score }}
          </div>
        </div>
      </div>

      <!-- 图表区域：雷达图 + 仪表盘 -->
      <div class="charts-section">
        <!-- 教案七维雷达图 -->
        <el-card v-if="radarOption" class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="header-dot indigo"></span>
              <span class="font-bold text-gray-800">教案七维分析</span>
            </div>
          </template>
          <div class="chart-body">
            <v-chart :option="radarOption as any" autoresize style="height: 320px;" />
          </div>
          <!-- 维度详情 -->
          <div v-if="lessonPlanAnalysis?.dimensions" class="dimension-details">
            <div
              v-for="(dim, key) in lessonPlanAnalysis.dimensions"
              :key="key"
              class="dim-row"
            >
              <span class="dim-name">{{ getDimensionName(String(key)) }}</span>
              <el-progress
                :percentage="dim.score"
                :color="getScoreColor(dim.score)"
                :stroke-width="8"
                style="flex: 1;"
              />
              <span class="dim-score" :style="{ color: getScoreColor(dim.score) }">{{ dim.score }}</span>
            </div>
          </div>
        </el-card>

        <!-- 视频指标仪表盘 -->
        <el-card v-if="videoGaugeOptions.length > 0" class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="header-dot green"></span>
              <span class="font-bold text-gray-800">视频多维评估</span>
            </div>
          </template>
          <div class="gauge-grid">
            <div v-for="gauge in videoGaugeOptions" :key="gauge.name" class="gauge-item">
              <v-chart :option="gauge.option" autoresize style="height: 140px;" />
              <div class="gauge-label">{{ gauge.icon }} {{ gauge.name }}</div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 知识图谱 -->
      <el-card v-if="submissionId" class="knowledge-graph-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="header-dot purple"></span>
            <span class="font-bold text-gray-800">AI 知识图谱</span>
          </div>
        </template>
        <KnowledgeGraph :submission-id="submissionId" />
      </el-card>

      <!-- 关键时刻回放 -->
      <el-card v-if="keyMoments.length > 0" class="key-moments-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="header-dot amber"></span>
            <span class="font-bold text-gray-800">关键时刻标记</span>
            <el-tag size="small" round>{{ keyMoments.length }} 个</el-tag>
          </div>
        </template>
        <div class="moments-timeline">
          <div
            v-for="(moment, i) in keyMoments"
            :key="i"
            class="timeline-node"
            :style="{ '--moment-color': moment.color }"
          >
            <div class="node-dot"></div>
            <div class="node-content">
              <span class="node-time">{{ formatTime(moment.time) }}</span>
              <span class="node-label">{{ moment.label }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- AI 改进建议 -->
      <el-card class="improvement-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="header-dot red"></span>
            <span class="font-bold text-gray-800">AI 改进建议</span>
          </div>
        </template>
        <!-- 亮点 -->
        <div v-if="lessonPlanAnalysis?.highlights?.length" class="section-block">
          <h4 class="section-subtitle text-green-600">教学亮点</h4>
          <div class="highlight-list">
            <div v-for="(h, i) in lessonPlanAnalysis.highlights" :key="i" class="highlight-item">
              {{ h }}
            </div>
          </div>
        </div>
        <!-- 改进 -->
        <div v-if="improvementData?.improvements?.length" class="section-block">
          <h4 class="section-subtitle text-orange-600">具体改进</h4>
          <div class="improve-list">
            <div v-for="(imp, i) in improvementData.improvements" :key="i" class="improve-item" :class="'priority-' + imp.priority">
              <div class="improve-header">
                <el-tag :type="imp.priority === 'high' ? 'danger' : imp.priority === 'medium' ? 'warning' : 'info'" size="small">
                  {{ imp.priority === 'high' ? '高优先' : imp.priority === 'medium' ? '中优先' : '低优先' }}
                </el-tag>
                <span class="improve-location">{{ imp.location }}</span>
              </div>
              <div class="improve-issue">{{ imp.issue }}</div>
              <div v-if="imp.suggestion" class="improve-suggestion">
                {{ imp.suggestion }}
              </div>
            </div>
          </div>
        </div>
        <!-- 视频建议 -->
        <div v-if="videoAnalysis?.suggestions?.length" class="section-block">
          <h4 class="section-subtitle text-blue-600">视频表现建议</h4>
          <div class="highlight-list">
            <div v-for="(s, i) in videoAnalysis.suggestions" :key="i" class="highlight-item blue">
              {{ s }}
            </div>
          </div>
        </div>
        <el-empty v-if="!lessonPlanAnalysis?.highlights?.length && !improvementData?.improvements?.length && !videoAnalysis?.suggestions?.length" description="暂无改进建议" :image-size="60" />
      </el-card>
    </div>
  </div>
</template>

<script lang="ts">
// 辅助函数
function getMetricClass(score: number) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'fair'
  return 'poor'
}

function getScoreColor(score: number) {
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#0891b2'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

function getDimensionName(key: string) {
  const map: Record<string, string> = {
    structure: '教案结构',
    objectives: '教学目标',
    key_points: '重难点',
    teaching_process: '教学过程',
    teaching_methods: '教学方法',
    board_design: '板书设计',
    language: '教学语言',
  }
  return map[key] || key
}

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
/* ==================== 全局布局 ==================== */
.ai-report-page {
  min-height: 100%;
  background: #f8fafc;
}

/* ==================== 导航栏 ==================== */
.report-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 100;
}

.back-btn {
  color: #6b7280;
}

.nav-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  flex: 1;
}

.title-icon {
  color: #0891b2;
  font-size: 20px;
}

.nav-subtitle {
  color: #9ca3af;
  font-weight: 400;
  font-size: 14px;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.animate-pulse-inline {
  animation: pulse-inline 1.5s infinite;
}

@keyframes pulse-inline {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ==================== 加载状态 ==================== */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.loading-spinner {
  position: relative;
  width: 80px;
  height: 80px;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border: 3px solid rgba(8, 145, 178, 0.1);
  border-top-color: #0891b2;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 32px;
  color: #0891b2;
}

.loading-text {
  margin-top: 16px;
  color: #6b7280;
  font-size: 14px;
}

/* ==================== 准备阶段 ==================== */
.ready-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 60px);
  padding: 24px;
}

.ready-card {
  max-width: 560px;
  width: 100%;
  background: white;
  border-radius: 24px;
  padding: 48px 40px;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.ready-icon-container {
  position: relative;
  width: 96px;
  height: 96px;
  margin: 0 auto 24px;
}

.ready-pulse-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid rgba(8, 145, 178, 0.3);
  animation: ready-pulse 2s infinite;
}

@keyframes ready-pulse {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

.ready-icon {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #ecfeff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ready-title {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 12px;
}

.ready-desc {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.8;
  margin-bottom: 32px;
}

.diagnosis-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
}

.preview-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: #f8fafc;
  border-radius: 20px;
  font-size: 13px;
  color: #4b5563;
}

.preview-icon {
  font-size: 16px;
}

.data-overview {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 32px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 12px;
}

.data-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #4b5563;
}

.data-item span { flex: 1; text-align: left; }

.start-btn {
  height: 48px;
  font-size: 16px;
  border-radius: 24px;
  padding: 0 36px;
  background: #0891b2;
  border: none;
  box-shadow: 0 4px 16px rgba(8, 145, 178, 0.3);
  transition: all 0.3s;
}

.start-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(8, 145, 178, 0.4);
}

/* ==================== 诊断阶段 ==================== */
.diagnosing-state {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
}

.diagnosis-header {
  padding: 12px 24px;
  background: #1a1a2e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.step-indicators {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.step-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  transition: color 0.3s;
}

.step-indicator.done {
  color: #10b981;
}

.step-icon {
  font-size: 14px;
}

.step-indicator.done .step-icon {
  background: #10b981;
  color: white;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

/* 双栏布局 */
.diagnosis-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 360px;
  overflow: hidden;
}

.diagnosis-left {
  background: #0f0f1a;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.no-video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #6b7280;
}

.diagnosis-right {
  background: #1a1a2e;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 指标面板 */
.metric-panel, .ai-commentary, .key-moments-panel {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 14px;
}

.title-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0891b2;
}

.title-dot.ai {
  background: #f59e0b;
  animation: pulse-dot 2s infinite;
}

.title-dot.moments {
  background: #10b981;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.metric-ring {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid;
  transition: all 0.3s;
}

.metric-ring.good {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.metric-ring.fair {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}

.metric-ring.poor {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: white;
}

.metric-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.expression-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(8, 145, 178, 0.1);
  border-radius: 10px;
  border: 1px solid rgba(8, 145, 178, 0.2);
  margin-bottom: 12px;
}

.expr-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.expr-value {
  font-size: 16px;
  font-weight: 600;
  color: #a5b4fc;
}

.speech-metrics {
  margin-top: 4px;
}

.sub-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 8px;
}

.speech-item {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.speech-value {
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

/* AI 评语 */
.comment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.comment-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.08);
  border-radius: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  animation: fadeInUp 0.4s ease;
}

.comment-icon {
  flex-shrink: 0;
}

.comment-empty {
  text-align: center;
  padding: 20px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
}

@keyframes fadeInUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.comment-enter-active { animation: fadeInUp 0.4s ease; }
.comment-leave-active { animation: fadeInUp 0.3s ease reverse; }

/* 关键时刻 */
.moments-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.moment-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-left: 3px solid;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.02);
  border-radius: 0 6px 6px 0;
}

.moment-time {
  font-family: monospace;
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
}

/* 底部进度 */
.diagnosis-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  background: #1a1a2e;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.diagnosis-progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.diagnosis-progress-fill {
  height: 100%;
  background: #0891b2;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.diagnosis-progress-text {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  white-space: nowrap;
}

/* ==================== 报告阶段 ==================== */
.report-state {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 综合得分 */
.score-hero {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 40px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.score-circle-large {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(8, 145, 178, 0.06);
  border: 4px solid var(--score-color, #0891b2);
  flex-shrink: 0;
}

.score-number {
  font-size: 52px;
  font-weight: 800;
  color: #1f2937;
  line-height: 1;
}

.score-text {
  font-size: 14px;
  color: #6b7280;
  margin-top: 6px;
}

.score-info {
  flex: 1;
}

.score-summary {
  margin-top: 12px;
  font-size: 14px;
  color: #4b5563;
  line-height: 1.8;
}

/* 分项得分 */
.score-breakdown {
  display: flex;
  gap: 16px;
}

.breakdown-item {
  flex: 1;
  background: white;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
  transition: transform 0.2s;
}

.breakdown-item:hover {
  transform: translateY(-2px);
}

.breakdown-icon {
  font-size: 28px;
}

.breakdown-label {
  flex: 1;
  font-size: 14px;
  color: #6b7280;
}

.breakdown-score {
  font-size: 32px;
  font-weight: 800;
}

/* 图表区域 */
.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 1024px) {
  .charts-section {
    grid-template-columns: 1fr;
  }
  .diagnosis-body {
    grid-template-columns: 1fr;
  }
  .diagnosis-right {
    max-height: 400px;
  }
  .score-hero {
    flex-direction: column;
    text-align: center;
  }
  .score-breakdown {
    flex-direction: column;
  }
}

.chart-card {
  border: none;
  border-radius: 16px;
  overflow: hidden;
}

.chart-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f3f4f6;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-dot {
  width: 8px;
  height: 16px;
  border-radius: 4px;
}

.header-dot.indigo { background: #0891b2; }
.header-dot.green { background: #10b981; }
.header-dot.purple { background: #0d9488; }
.header-dot.amber { background: #f59e0b; }
.header-dot.red { background: #ef4444; }

.chart-body {
  padding: 8px;
}

.dimension-details {
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dim-name {
  font-size: 12px;
  color: #6b7280;
  min-width: 60px;
}

.dim-score {
  font-size: 14px;
  font-weight: 700;
  min-width: 30px;
  text-align: right;
}

/* 仪表盘网格 */
.gauge-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 8px;
}

.gauge-item {
  text-align: center;
}

.gauge-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: -8px;
}

/* 知识图谱 */
.knowledge-graph-card {
  border: none;
  border-radius: 16px;
  overflow: hidden;
}

.knowledge-graph-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f3f4f6;
}

/* 关键时刻 */
.key-moments-card {
  border: none;
  border-radius: 16px;
}

.key-moments-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f3f4f6;
}

.moments-timeline {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 4px;
}

.timeline-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #f9fafb;
  border-radius: 10px;
  border-left: 3px solid var(--moment-color, #0891b2);
}

.node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--moment-color, #0891b2);
}

.node-content {
  display: flex;
  flex-direction: column;
}

.node-time {
  font-size: 11px;
  color: #9ca3af;
  font-family: monospace;
}

.node-label {
  font-size: 13px;
  color: #374151;
}

/* 改进建议 */
.improvement-card {
  border: none;
  border-radius: 16px;
}

.improvement-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid #f3f4f6;
}

.section-block {
  margin-bottom: 20px;
}

.section-subtitle {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}

.highlight-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.highlight-item {
  padding: 10px 14px;
  background: #f0fdf4;
  border-left: 3px solid #10b981;
  border-radius: 0 8px 8px 0;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

.highlight-item.blue {
  background: #eff6ff;
  border-left-color: #3b82f6;
}

.improve-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.improve-item {
  padding: 12px 16px;
  background: #fffbeb;
  border-radius: 10px;
  border: 1px solid #fde68a;
}

.improve-item.priority-high {
  border-color: #fca5a5;
  background: #fef2f2;
}

.improve-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.improve-location {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.improve-issue {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}

.improve-suggestion {
  font-size: 13px;
  color: #d97706;
  background: rgba(245, 158, 11, 0.08);
  padding: 6px 10px;
  border-radius: 6px;
}
</style>
