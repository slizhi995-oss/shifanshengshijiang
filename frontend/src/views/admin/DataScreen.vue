<script setup lang="ts">
/**
 * 智慧试讲 - 数据视界 (Data Horizon)
 * 高端数据大屏展示
 */
import { ref, onMounted, onUnmounted, reactive, nextTick } from 'vue'
import { useResizeObserver } from '@vueuse/core'
import * as echarts from 'echarts'
import { 
  FullScreen, Refresh, Monitor, DataLine, 
  Trophy, UserFilled, Reading, Timer 
} from '@element-plus/icons-vue'
import api from '@/utils/request'

// ECharts 主题色
const colors = {
  primary: '#00f6ff',
  secondary: '#0891b2',
  success: '#00e676',
  warning: '#ffc400',
  danger: '#ff1744',
  text: '#b3e5fc',
  grid: 'rgba(0, 246, 255, 0.1)'
}

const loading = ref(false)
const isFullscreen = ref(false)
const containerRef = ref<HTMLElement | null>(null)
const currentTime = ref(new Date())
let timer: any = null
let logTimer: any = null

// AI 实时日志
const aiLogEntries = ref<{ time: string; action: string; status: string }[]>([])
const aiLogFallbackTemplates = [
  { action: '教案分析完成', status: 'success' },
  { action: '视频语音识别处理中', status: 'processing' },
  { action: '手势姿态分析完成', status: 'success' },
  { action: '教案改进建议生成', status: 'success' },
  { action: 'AI 备课助手会话', status: 'processing' },
  { action: '综合评分计算完成', status: 'success' },
]

// 雷达图真实数据
const radarData = ref<{ indicators: string[]; values: number[] }>({ indicators: [], values: [] })

const fetchAILogs = async () => {
  try {
    const res: any = await api.get('/admin/data-screen/ai-logs', { params: { limit: 8 } })
    if (Array.isArray(res) && res.length > 0) {
      aiLogEntries.value = res
    } else {
      // 无真实日志时用兜底模拟
      startLogFallback()
    }
  } catch {
    startLogFallback()
  }
}

const fetchRadarData = async () => {
  try {
    const res: any = await api.get('/admin/data-screen/ability-radar')
    if (res && res.indicators) {
      radarData.value = { indicators: res.indicators, values: res.values }
    }
  } catch { /* use defaults */ }
}

const startLogFallback = () => {
  const addLog = () => {
    const tpl = aiLogFallbackTemplates[Math.floor(Math.random() * aiLogFallbackTemplates.length)]
    const now = new Date()
    aiLogEntries.value.unshift({
      time: `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`,
      action: tpl.action,
      status: tpl.status
    })
    if (aiLogEntries.value.length > 8) aiLogEntries.value.pop()
  }
  for (let i = 0; i < 5; i++) addLog()
  logTimer = setInterval(addLog, 5000)
}

// 统计数据
const stats = reactive({
  totalStudents: 0,
  totalInstructors: 0,
  dailyActive: 0,
  aiAnalysisCount: 0,
  avgScore: 0,
  passRate: 0,
  participationRate: 0,
  totalinteractions: 0
})

// 图表容器 DOM 引用
const submissionTrendRef = ref<HTMLElement | null>(null)
const scoreDistributionRef = ref<HTMLElement | null>(null)
const abilityRadarRef = ref<HTMLElement | null>(null)
const activityMapRef = ref<HTMLElement | null>(null)

// ECharts 实例
const charts = {
  submission: null as echarts.ECharts | null,
  distribution: null as echarts.ECharts | null,
  radar: null as echarts.ECharts | null,
  gauge: null as echarts.ECharts | null
}

// 数字滚动动画
const animateNumber = (key: keyof typeof stats, target: number, duration = 1500) => {
  const start = stats[key] as number
  const diff = target - start
  if (diff === 0) return
  const startTime = performance.now()
  const step = (currentTime: number) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    // easeOutExpo
    const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
    ;(stats as any)[key] = Math.round(start + diff * eased)
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

// 获取数据
const fetchData = async () => {
  loading.value = true
  try {
    // 并行请求所有数据
    const [overviewRes, trendsRes, distributionRes] = await Promise.allSettled([
      api.get('/admin/data-screen/overview'),
      api.get('/admin/data-screen/trends', { params: { days: 7 } }),
      api.get('/admin/data-screen/distribution')
    ])

    // 处理概览数据
    if (overviewRes.status === 'fulfilled' && overviewRes.value) {
      const data = overviewRes.value as any
      animateNumber('totalStudents', data.totalStudents || 0)
      animateNumber('totalInstructors', data.totalInstructors || 0)
      animateNumber('dailyActive', data.totalSubmissions || 0)
      animateNumber('aiAnalysisCount', data.aiAnalysisCount || 0)
      animateNumber('avgScore', data.averageScore || 0)
      animateNumber('passRate', data.completionRate || 0)
      animateNumber('participationRate', data.participationRate || 0)
      animateNumber('totalinteractions', (data.totalSubmissions || 0) + (data.aiAnalysisCount || 0))
    }

    // 等待 DOM 更新后渲染图表
    await nextTick()

    // 渲染趋势图
    const trendData = overviewRes.status === 'fulfilled' && trendsRes.status === 'fulfilled' ? trendsRes.value : undefined
    renderSubmissionTrend(trendData as any)

    // 渲染成绩分布
    const distData = distributionRes.status === 'fulfilled' ? distributionRes.value : undefined
    renderScoreDistribution(distData as any)

    // 渲染雷达图和活跃度（直接传入原始值，避免动画未完成时读到 0）
    const rawParticipation = overviewRes.status === 'fulfilled' ? (overviewRes.value as any)?.participationRate || 0 : 0
    renderAbilityRadar()
    renderActivityMap(rawParticipation)
  } catch (error) {
    console.error('数据大屏加载失败:', error)
    // 即便请求失败也渲染默认图表
    await nextTick()
    renderSubmissionTrend()
    renderScoreDistribution()
    renderAbilityRadar()
    renderActivityMap(85)
  } finally {
    loading.value = false
  }
}

// 1. 提交趋势图
const renderSubmissionTrend = (data?: any) => {
  if (!submissionTrendRef.value) return
  
  // 默认模拟数据
  let dates = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  let values = [120, 132, 101, 134, 90, 230, 210]
  let approvals = [100, 110, 90, 120, 80, 210, 190]

  if (data && data.dates && data.dates.length > 0) {
    dates = data.dates
    values = data.submissions
    approvals = data.approvals
  }

  if (charts.submission) charts.submission.dispose()
  charts.submission = echarts.init(submissionTrendRef.value)
  
  charts.submission.setOption({
    backgroundColor: 'transparent',
    animationDuration: 1500,
    animationEasing: 'cubicInOut',
    animationDelay: (idx: number) => idx * 150,
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.8)', borderColor: colors.primary, textStyle: { color: '#fff' } },
    legend: { textStyle: { color: colors.text }, right: 10 },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: colors.grid } },
      axisLabel: { color: colors.text }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } },
      axisLabel: { color: colors.text }
    },
    series: [
      {
        name: '提交数',
        type: 'line',
        smooth: true,
        showSymbol: true,
        data: values,
        lineStyle: { color: colors.primary, width: 3 },
        itemStyle: { color: colors.primary },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 246, 255, 0.4)' },
            { offset: 1, color: 'rgba(0, 246, 255, 0)' }
          ])
        },
        animationDuration: 2000,
        animationEasing: 'cubicOut'
      },
      {
        name: '通过数',
        type: 'line',
        smooth: true,
        showSymbol: true,
        data: approvals,
        lineStyle: { color: colors.success, width: 3 },
        itemStyle: { color: colors.success },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 230, 118, 0.4)' },
            { offset: 1, color: 'rgba(0, 230, 118, 0)' }
          ])
        },
        animationDuration: 2000,
        animationDelay: 300,
        animationEasing: 'cubicOut'
      }
    ]
  })
}

// 2. 成绩分布
const renderScoreDistribution = (data?: any) => {
  if (!scoreDistributionRef.value) return
  
  let chartData = [
    { value: 40, name: '优秀 (90+)', itemStyle: { color: colors.success } },
    { value: 38, name: '良好 (80-89)', itemStyle: { color: colors.primary } },
    { value: 32, name: '中等 (70-79)', itemStyle: { color: colors.warning } },
    { value: 15, name: '及格 (60-69)', itemStyle: { color: colors.secondary } },
    { value: 8, name: '需努力 (<60)', itemStyle: { color: colors.danger } }
  ]

  if (data && Array.isArray(data) && data.length > 0) {
    const colorMap: Record<string, string> = {
      '优秀': colors.success, '良好': colors.primary, 
      '中等': colors.warning, '及格': colors.secondary, '不及格': colors.danger
    }
    chartData = data.map((item: any) => {
      let color = colors.secondary
      if (item.name.includes('优秀')) color = colors.success
      else if (item.name.includes('良好')) color = colors.primary
      else if (item.name.includes('中等')) color = colors.warning
      else if (item.name.includes('不及格')) color = colors.danger
      return { value: item.value, name: item.name, itemStyle: { color } }
    })
  }

  if (charts.distribution) charts.distribution.dispose()
  charts.distribution = echarts.init(scoreDistributionRef.value)
  
  charts.distribution.setOption({
    animationDuration: 1200,
    animationEasing: 'elasticOut',
    animationDelay: (idx: number) => idx * 200,
    tooltip: { trigger: 'item', backgroundColor: 'rgba(0,0,0,0.8)', textStyle: { color: '#fff' } },
    legend: { bottom: '5%', textStyle: { color: colors.text, fontSize: 11 }, itemWidth: 15, itemHeight: 10, itemGap: 8 },
    series: [
      {
        name: '成绩分布',
        type: 'pie',
        radius: [20, 70],
        center: ['50%', '40%'],
        roseType: 'area',
        itemStyle: { borderRadius: 5 },
        data: chartData,
        label: { show: false },
        labelLine: { show: false },
        animationType: 'scale',
        animationEasing: 'elasticOut',
        animationDelay: (idx: number) => idx * 200
      }
    ]
  })
}

// 3. 教学能力雷达 - 使用真实API数据
const renderAbilityRadar = () => {
  if (!abilityRadarRef.value) return
  
  const indicators = radarData.value.indicators.length > 0
    ? radarData.value.indicators
    : ['教案设计', '教学目标', '知识讲解', '教学过程', '教学方法', '板书设计']
  const values = radarData.value.values.length > 0
    ? radarData.value.values
    : [0, 0, 0, 0, 0, 0]

  if (charts.radar) charts.radar.dispose()
  charts.radar = echarts.init(abilityRadarRef.value)
  
  charts.radar.setOption({
    animationDuration: 1800,
    animationEasing: 'cubicInOut',
    tooltip: {},
    radar: {
      indicator: indicators.map(name => ({ name, max: 100 })),
      radius: '60%',
      splitLine: { lineStyle: { color: colors.grid } },
      splitArea: { show: false },
      axisName: { color: colors.text, fontSize: 12, padding: [3, 5] }
    },
    series: [
      {
        name: '能力评估',
        type: 'radar',
        animationDuration: 2000,
        animationEasing: 'elasticOut',
        data: [
          {
            value: values,
            name: '全校平均',
            itemStyle: { color: colors.primary },
            areaStyle: { color: 'rgba(0, 246, 255, 0.2)' },
            lineStyle: { width: 2 }
          }
        ]
      }
    ]
  })
}

// 4. 活跃热度 - 使用真实数据
const renderActivityMap = (rawRate?: number) => {
  if (!activityMapRef.value) return
  
  // 使用直接传入的原始值（避免动画未完成读到 0）
  const activityRate = rawRate ?? stats.participationRate ?? 0

  if (charts.gauge) charts.gauge.dispose()
  charts.gauge = echarts.init(activityMapRef.value)
  
  charts.gauge.setOption({
    animationDuration: 2000,
    animationEasing: 'cubicOut',
    series: [{
      type: 'gauge',
      animationDuration: 2500,
      animationEasing: 'cubicInOut',
      center: ['50%', '55%'],
      radius: '85%',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      itemStyle: { color: colors.secondary },
      progress: { show: true, width: 25 },
      pointer: { show: false },
      axisLine: { lineStyle: { width: 25 } },
      axisTick: { distance: -38, splitNumber: 5, lineStyle: { width: 2, color: '#999' } },
      splitLine: { distance: -44, length: 12, lineStyle: { width: 3, color: '#999' } },
      axisLabel: { distance: -18, color: '#999', fontSize: 10 },
      anchor: { show: false },
      title: { show: false },
      detail: {
        valueAnimation: true,
        width: '60%',
        lineHeight: 36,
        borderRadius: 8,
        offsetCenter: [0, '-10%'],
        fontSize: 26,
        fontWeight: 'bolder',
        formatter: '{value}%\n参与率',
        color: '#fff'
      },
      data: [{ value: activityRate }]
    }]
  })
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    containerRef.value?.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

// 监听尺寸变化
useResizeObserver(containerRef, () => {
  Object.values(charts).forEach(c => c?.resize())
})

onMounted(async () => {
  await fetchRadarData()
  await fetchData()
  fetchAILogs()
  timer = setInterval(() => {
    currentTime.value = new Date()
  }, 1000)
  
  // 定期刷新 AI 日志
  logTimer = setInterval(fetchAILogs, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (logTimer) clearInterval(logTimer)
  Object.values(charts).forEach(chart => chart?.dispose())
})
</script>

<template>
  <div class="data-screen-container" ref="containerRef">
    <!-- 背景特效 -->
    <div class="bg-mesh"></div>
    
    <!-- 头部 -->
    <header class="screen-header">
      <div class="header-left">
        <span class="time">{{ currentTime.toLocaleTimeString() }}</span>
        <span class="date">{{ currentTime.toLocaleDateString() }}</span>
      </div>
      <div class="header-center">
        <h1 class="glow-text">智慧师范生试讲数据中心</h1>
        <div class="header-decoration"></div>
      </div>
      <div class="header-right">
        <div class="actions">
          <el-button link class="action-btn" @click="fetchData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button link class="action-btn" @click="toggleFullscreen">
            <el-icon><FullScreen /></el-icon> {{ isFullscreen ? '缩放' : '全屏' }}
          </el-button>
        </div>
      </div>
    </header>

    <!-- 主体 -->
    <main class="chart-grid">
      <!-- 左栏 -->
      <aside class="left-col">
        <div class="data-card monitor-card">
          <div class="card-title"><el-icon><Monitor /></el-icon> 实时数据概览</div>
          <div class="monitor-grid">
            <div class="monitor-item">
              <div class="label">学生总数</div>
              <div class="value num-font">{{ stats.totalStudents }}</div>
            </div>
            <div class="monitor-item">
              <div class="label">今日活跃</div>
              <div class="value num-font text-active">{{ stats.dailyActive }}</div>
            </div>
            <div class="monitor-item">
              <div class="label">AI 分析</div>
              <div class="value num-font text-purple">{{ stats.aiAnalysisCount }}</div>
            </div>
            <div class="monitor-item">
              <div class="label">导师在线</div>
              <div class="value num-font text-warn">{{ stats.totalInstructors }}</div>
            </div>
          </div>
        </div>

        <div class="data-card trend-card">
          <div class="card-title"><el-icon><DataLine /></el-icon> 试讲提交趋势</div>
          <div class="chart-container" ref="submissionTrendRef"></div>
        </div>
      </aside>

      <!-- 中栏 -->
      <section class="center-col">
        <!-- 核心数字 -->
        <div class="hero-stats">
          <div class="hero-item">
            <div class="hero-label">系统总交互量</div>
            <div class="hero-value neon-font">{{ stats.totalinteractions.toLocaleString() }}</div>
          </div>
          <div class="hero-item">
            <div class="hero-label">平均成绩</div>
            <div class="hero-value neon-font text-success">{{ stats.avgScore }}</div>
          </div>
        </div>

        <!-- 中央主图 -->
        <div class="center-map-container">
          <div class="map-bg"></div>
          <div class="chart-container" ref="activityMapRef"></div>
           <div class="center-decoration">
              <div class="circle c1"></div>
              <div class="circle c2"></div>
              <div class="circle c3"></div>
           </div>
        </div>
      </section>

      <!-- 右栏 -->
      <aside class="right-col">
        <div class="data-card distribution-card">
          <div class="card-title"><el-icon><Trophy /></el-icon> 成绩分布</div>
          <div class="chart-container" ref="scoreDistributionRef"></div>
        </div>

        <div class="data-card radar-card">
          <div class="card-title"><el-icon><Reading /></el-icon> 教学能力画像</div>
          <div class="chart-container" ref="abilityRadarRef"></div>
        </div>
      </aside>

      <!-- 底部 AI 实时日志 -->
      <div class="ai-log-bar">
        <div class="data-card ai-log-card">
          <div class="card-title">
            <span class="ai-status-dot"></span>
            AI 引擎实时动态
          </div>
          <div class="log-scroll">
            <div
              v-for="(log, idx) in aiLogEntries"
              :key="idx"
              class="log-entry"
              :class="{ 'is-new': idx === 0 }"
            >
              <span class="log-time">{{ log.time }}</span>
              <span class="log-dot" :class="log.status"></span>
              <span class="log-text">{{ log.action }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

.data-screen-container {
  width: 100%;
  height: 100vh;
  background-color: #03081a;
  color: #fff;
  overflow-x: hidden;
  overflow-y: auto; /* Allow vertical scroll if height is too small */
  display: flex;
  flex-direction: column;
  position: relative;
  font-family: 'Inter', sans-serif;
  box-sizing: border-box; /* Critical for padding calculation */
}

/* 背景网格 */
.bg-mesh {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(0, 246, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 246, 255, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  z-index: 1;
  pointer-events: none;
}

/* 头部 */
.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 30px;
  z-index: 10;
  border-bottom: 1px solid rgba(0, 246, 255, 0.1);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-left .time {
  font-family: 'Share Tech Mono', monospace;
  font-size: 22px;
  color: #00f6ff;
}

.header-left .date {
  font-size: 12px;
  color: #8daac4;
}

.header-center {
  text-align: center;
  flex: 1;
}

.glow-text {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 6px;
  background: linear-gradient(180deg, #fff 0%, #00f6ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: none;
  filter: drop-shadow(0 0 20px rgba(0, 246, 255, 0.3));
  margin: 0;
}

.header-decoration {
  height: 2px;
  width: 200px;
  margin: 8px auto 0;
  background: linear-gradient(90deg, transparent, #00f6ff, transparent);
}

.header-right {
  display: flex;
  align-items: center;
}

.action-btn {
  color: #8daac4 !important;
  font-size: 14px;
  transition: color 0.2s;
}

.action-btn:hover {
  color: #00f6ff !important;
}

.map-bg {
  position: absolute;
  width: 100%;
  height: 100%;
  background: radial-gradient(ellipse at center, rgba(123, 97, 255, 0.1) 0%, transparent 70%);
}

/* 布局网格 */
.chart-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 28% 44% 28%;
  grid-template-rows: 1fr auto;
  gap: 20px;
  padding: 20px;
  z-index: 10;
  box-sizing: border-box;
  min-height: 0;
}

/* AI 日志栏 */
.ai-log-bar {
  grid-column: 1 / -1;
}

.ai-log-card {
  height: auto !important;
}

.ai-log-card .card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.ai-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #00e676;
  box-shadow: 0 0 8px #00e676;
  animation: ai-blink 1.5s infinite;
}

@keyframes ai-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.log-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.log-scroll::-webkit-scrollbar { height: 3px; }
.log-scroll::-webkit-scrollbar-thumb { background: rgba(0, 246, 255, 0.2); border-radius: 3px; }

.log-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: rgba(0, 246, 255, 0.05);
  border: 1px solid rgba(0, 246, 255, 0.1);
  border-radius: 8px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.3s;
}

.log-entry.is-new {
  animation: log-in 0.4s ease;
}

@keyframes log-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.log-time {
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px;
  color: #64748b;
}

.log-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.log-dot.success { background: #00e676; }
.log-dot.processing { background: #ffc400; animation: ai-blink 1s infinite; }

.log-text {
  font-size: 13px;
  color: #b3e5fc;
}

/* 卡片通用样式 */
.data-card {
  background: rgba(12, 23, 50, 0.6);
  border: 1px solid rgba(0, 246, 255, 0.2);
  border-radius: 12px;
  padding: 15px;
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
  overflow: hidden;
  animation: cardFadeIn 0.8s ease-out both;
}
.data-card:nth-child(1) { animation-delay: 0.1s; }
.data-card:nth-child(2) { animation-delay: 0.3s; }

@keyframes cardFadeIn {
  from { opacity: 0; transform: translateY(20px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.data-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #00f6ff, transparent);
}

.card-title {
  font-size: 18px;
  color: #fff;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-left: 4px solid #00f6ff;
  padding-left: 10px;
}

.chart-container {
  flex: 1;
  min-height: 240px;
}

/* 监控面板 */
.monitor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  height: 100%;
}

.monitor-item {
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 10px;
}

.monitor-item .label {
  color: #8daac4;
  font-size: 14px;
}

.monitor-item .value {
  font-size: 24px;
  font-weight: bold;
  margin-top: 5px;
}

/* 左侧栏 */
.left-col, .right-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: colSlideIn 0.6s ease-out both;
}
.left-col { animation-delay: 0.2s; }
.right-col { animation-delay: 0.5s; }

@keyframes colSlideIn {
  from { opacity: 0; transform: translateX(-30px); }
  to { opacity: 1; transform: translateX(0); }
}
.right-col { animation-name: colSlideInRight; }
@keyframes colSlideInRight {
  from { opacity: 0; transform: translateX(30px); }
  to { opacity: 1; transform: translateX(0); }
}

.monitor-card { height: 35%; }
.trend-card { height: 60%; }

.distribution-card { height: 45%; }
.radar-card { height: 50%; }

/* 中间栏 */
.center-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: centerFadeIn 1s ease-out 0.3s both;
}

@keyframes centerFadeIn {
  from { opacity: 0; transform: scale(0.92); }
  to { opacity: 1; transform: scale(1); }
}

.hero-stats {
  display: flex;
  justify-content: space-around;
  padding: 20px;
  background: rgba(0, 246, 255, 0.05);
  border-radius: 12px;
  border: 1px solid rgba(0, 246, 255, 0.1);
  animation: heroPopIn 0.8s ease-out 0.5s both;
}
@keyframes heroPopIn {
  from { opacity: 0; transform: translateY(-15px); }
  to { opacity: 1; transform: translateY(0); }
}

.hero-item {
  text-align: center;
}

.hero-label {
  color: #00f6ff;
  font-size: 16px;
  margin-bottom: 10px;
}

.hero-value {
  font-size: 48px;
  font-weight: bold;
  text-shadow: 0 0 20px rgba(0, 246, 255, 0.4);
}

.center-map-container {
  flex: 1;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 装饰动画 */
.center-decoration {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.circle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 1px solid rgba(0, 246, 255, 0.1);
}

.c1 { width: 300px; height: 300px; animation: rotate 10s linear infinite; border-top-color: #00f6ff; }
.c2 { width: 450px; height: 450px; animation: rotate 15s linear infinite reverse; border-bottom-color: #0891b2; }
.c3 { width: 600px; height: 600px; border: 1px dashed rgba(255,255,255,0.1); }

@keyframes rotate {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 字体与颜色 */
.num-font { font-family: 'Share Tech Mono', monospace; }
.neon-font { font-family: 'Orbitron', sans-serif; }
.text-active { color: #00e676; }
.text-purple { color: #0891b2; }
.text-warn { color: #ffc400; }
.text-success { color: #00f6ff; }

/* 响应式 */
@media (max-width: 1400px) {
  .chart-grid {
    grid-template-columns: 30% 70%;
    grid-template-rows: auto auto;
  }
  .right-col {
    grid-column: 1 / -1;
    flex-direction: row;
  }
}
</style>
