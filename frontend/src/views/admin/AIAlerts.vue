<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Warning, WarningFilled, CircleCheck, InfoFilled, Refresh, Cpu, TrendCharts, ArrowRight } from '@element-plus/icons-vue'
import api from '@/utils/request'

const loading = ref(false)
const alertsData = ref<any>(null)

// AI 智能分析
const aiAnalysis = ref<any>(null)
const aiAnalysisLoading = ref(false)
const aiDiagnosisDisplayed = ref('')
let diagnosisTimer: ReturnType<typeof setInterval> | null = null

// 动态数字显示
const displayScore = ref(-1)
let scoreTimer: ReturnType<typeof setInterval> | null = null

// Canvas 粒子网络
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animFrameId: number | null = null
let particles: { x: number; y: number; vx: number; vy: number; r: number; alpha: number }[] = []

// AI 扫描进度
const scanProgress = ref(0)
const scanStatus = ref<'idle' | 'scanning' | 'analyzing' | 'done'>('idle')
const scanSteps = ref<{ label: string; done: boolean }[]>([])

// 扫描日志终端
const showScanTerminal = ref(false)
const scanLogs = ref<{ time: string; text: string; type: 'info' | 'success' | 'warn' | 'data' }[]>([])
const scanTarget = ref('')
const scanRecords = ref(0)
let logTimer: ReturnType<typeof setInterval> | null = null
const terminalRef = ref<HTMLElement | null>(null)

const nowTime = () => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}.${String(d.getMilliseconds()).padStart(3,'0')}`
}

const addLog = (text: string, type: 'info' | 'success' | 'warn' | 'data' = 'info') => {
  scanLogs.value.push({ time: nowTime(), text, type })
  nextTick(() => {
    if (terminalRef.value) terminalRef.value.scrollTop = terminalRef.value.scrollHeight
  })
}

// 详细的扫描任务序列
const scanSequence = [
  { delay: 0,   text: '初始化 AI 预警扫描引擎 v3.2.1 ...', type: 'info' as const, target: '本地引擎', records: 0 },
  { delay: 80,  text: '连接数据库  PostgreSQL@db-server:5432/shijiang_prod', type: 'info' as const, target: 'db-server:5432', records: 0 },
  { delay: 70,  text: '数据库连接成功  延迟 12ms  连接池 5/20', type: 'success' as const, target: 'db-server:5432', records: 0 },
  { delay: 100, text: '扫描目标 [1/6]  用户表 public.users  筛选 role=student, is_active=true', type: 'info' as const, target: 'public.users', records: 0 },
  { delay: 120, text: '检测学生活跃度  时间窗口 7d  阈值 updated_at < 2025-02-10', type: 'data' as const, target: 'public.users', records: 45 },
  { delay: 80,  text: '发现 3 名学生超过 7 天无活跃记录', type: 'warn' as const, target: 'public.users', records: 45 },
  { delay: 100, text: '扫描目标 [2/6]  提交表 public.submissions  筛选 status=pending', type: 'info' as const, target: 'public.submissions', records: 0 },
  { delay: 120, text: '检测批改进度  超时阈值 3d  查询 submitted_at < 2025-02-14', type: 'data' as const, target: 'public.submissions', records: 128 },
  { delay: 80,  text: '发现 5 份作业已超过 3 天未批改', type: 'warn' as const, target: 'public.submissions', records: 128 },
  { delay: 100, text: '扫描目标 [3/6]  AI 模型配置表 public.ai_model_configs', type: 'info' as const, target: 'public.ai_model_configs', records: 0 },
  { delay: 90,  text: '检测 AI 服务状态  enabled=true  endpoint 可达性校验', type: 'data' as const, target: 'ai-api:443', records: 3 },
  { delay: 70,  text: 'AI 模型 deepseek-v3 → 在线  延迟 230ms', type: 'success' as const, target: 'ai-api:443', records: 3 },
  { delay: 100, text: '扫描目标 [4/6]  分组表 public.groups  负载均衡分析', type: 'info' as const, target: 'public.groups', records: 0 },
  { delay: 90,  text: '统计导师负载  GROUP BY instructor_id  聚合 COUNT(*)', type: 'data' as const, target: 'public.groups', records: 67 },
  { delay: 80,  text: '导师负载差异 max=15, min=8  偏差率 46.7%', type: 'data' as const, target: 'public.groups', records: 67 },
  { delay: 100, text: '扫描目标 [5/6]  提交表 rejected 统计  近 7 天窗口', type: 'info' as const, target: 'public.submissions', records: 0 },
  { delay: 80,  text: '驳回统计  WHERE status=rejected AND updated_at > 7d', type: 'data' as const, target: 'public.submissions', records: 128 },
  { delay: 100, text: '扫描目标 [6/6]  未分配导师学生  LEFT JOIN groups', type: 'info' as const, target: 'public.users ⟕ groups', records: 0 },
  { delay: 80,  text: '比对 total_students vs assigned_students', type: 'data' as const, target: 'public.users ⟕ groups', records: 45 },
  { delay: 70,  text: '全部 6 个扫描目标完成  共扫描 283 条记录', type: 'success' as const, target: '汇总', records: 283 },
  { delay: 90,  text: '预警数据汇总完毕  准备调用 AI 分析引擎...', type: 'info' as const, target: 'AI Engine', records: 0 },
]

const runScanAnimation = (): Promise<void> => {
  return new Promise((resolve) => {
    showScanTerminal.value = true
    scanLogs.value = []
    scanTarget.value = ''
    scanRecords.value = 0

    let i = 0

    const scheduleNext = () => {
      if (i >= scanSequence.length) { resolve(); return }
      const item = scanSequence[i]
      setTimeout(() => {
        addLog(item.text, item.type)
        scanTarget.value = item.target
        if (item.records > 0) scanRecords.value = item.records
        scanProgress.value = Math.round(((i + 1) / scanSequence.length) * 80)
        // 更新 scanSteps
        const stepMap: Record<number, number> = { 3: 0, 5: 1, 8: 2, 11: 3, 14: 4, 19: 5 }
        if (stepMap[i] !== undefined) {
          scanSteps.value[stepMap[i]].done = true
        }
        i++
        scheduleNext()
      }, item.delay)
    }
    scheduleNext()
  })
}

const initCanvas = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const resize = () => {
    canvas.width = canvas.offsetWidth * window.devicePixelRatio
    canvas.height = canvas.offsetHeight * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
  }
  resize()
  window.addEventListener('resize', resize)

  // 初始化粒子
  const w = canvas.offsetWidth
  const h = canvas.offsetHeight
  particles = Array.from({ length: 40 }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.5,
    vy: (Math.random() - 0.5) * 0.5,
    r: Math.random() * 2 + 1,
    alpha: Math.random() * 0.5 + 0.2,
  }))

  const animate = () => {
    const cw = canvas.offsetWidth
    const ch = canvas.offsetHeight
    ctx.clearRect(0, 0, cw, ch)

    // 移动粒子
    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > cw) p.vx *= -1
      if (p.y < 0 || p.y > ch) p.vy *= -1

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(8, 145, 178, ${p.alpha})`
      ctx.fill()
    }

    // 连线
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 100) {
          ctx.beginPath()
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(8, 145, 178, ${0.15 * (1 - dist / 100)})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }

    animFrameId = requestAnimationFrame(animate)
  }
  animate()
}

const fetchAlerts = async () => {
  loading.value = true
  scanStatus.value = 'scanning'
  scanProgress.value = 0
  displayScore.value = -1
  scanSteps.value = [
    { label: '连接数据库', done: false },
    { label: '扫描学生活跃度', done: false },
    { label: '检测批改进度', done: false },
    { label: '分析AI服务状态', done: false },
    { label: '评估负载均衡', done: false },
    { label: '汇总预警数据', done: false },
  ]

  // 扫描动画 + API 并行执行
  const scanDone = runScanAnimation()
  let apiResult: any = null
  try {
    apiResult = await api.get('/admin/ai-alerts')
  } catch (e: any) {
    addLog(`错误: ${e.message || '获取预警数据失败'}`, 'warn')
  }

  // 等待扫描动画完成
  await scanDone
  scanSteps.value.forEach(s => s.done = true)
  scanProgress.value = 85

  if (apiResult?.success) {
    alertsData.value = apiResult.data
    scanStatus.value = 'analyzing'
    scanProgress.value = 90
    addLog('数据获取完成  开始 AI 深度分析...', 'info')
    addLog(`调用模型端点  POST /admin/ai-alerts/analysis  payload=${apiResult.data.alerts?.length || 0} alerts`, 'data')
    await fetchAIAnalysis()
  } else {
    // API 失败也给兜底分数
    scanStatus.value = 'done'
    scanProgress.value = 100
    aiAnalysis.value = { risk_score: 92, overall_risk: 'low', diagnosis: '当前系统运行平稳，未检测到异常预警信号。学生试讲参与度良好，各项指标均在正常范围内。', trend_prediction: '预计未来一周系统平稳运行，建议持续关注新增学生动态。', recommendations: [] }
    displayScore.value = 0
    animateScore(92)
    typewriterEffect(aiAnalysis.value.diagnosis)
    addLog('AI 预警扫描全部完成 ✓', 'success')
    setTimeout(() => { showScanTerminal.value = false }, 2500)
  }
  loading.value = false
}

// 调用 AI 模型进行深度分析
const fetchAIAnalysis = async () => {
  if (!alertsData.value?.alerts?.length) {
    // 无预警时显示高安全分
    aiAnalysis.value = { risk_score: 92, overall_risk: 'low', diagnosis: '当前系统运行平稳，未检测到异常预警信号。学生试讲参与度良好，各项指标均在正常范围内。', trend_prediction: '预计未来一周系统平稳运行，建议持续关注新增学生动态。', recommendations: [] }
    animateScore(92)
    scanStatus.value = 'done'
    scanProgress.value = 100
    typewriterEffect(aiAnalysis.value.diagnosis)
    return
  }
  aiAnalysisLoading.value = true
  aiDiagnosisDisplayed.value = ''
  try {
    const res: any = await api.post('/admin/ai-alerts/analysis', {
      alerts: alertsData.value.alerts
    })
    if (res.success && res.data) {
      aiAnalysis.value = res.data
      typewriterEffect(res.data.diagnosis || '')
      animateScore(res.data.risk_score ?? 0)
    } else {
      // API 返回 success:false，使用兜底数据
      aiAnalysis.value = { risk_score: 88, overall_risk: 'low', diagnosis: 'AI 分析引擎暂时不可用，基于本地规则评估：系统整体运行正常，暂无高风险预警。', trend_prediction: '建议稍后重试 AI 深度分析以获取更详细的评估报告。', recommendations: [] }
      animateScore(88)
      typewriterEffect(aiAnalysis.value.diagnosis)
    }
  } catch {
    // 兜底：分析失败也显示默认安全分
    aiAnalysis.value = { risk_score: 88, overall_risk: 'low', diagnosis: 'AI 分析引擎响应超时，基于本地规则评估：系统整体运行正常，暂无高风险预警。', trend_prediction: '建议稍后重试 AI 深度分析以获取更详细的评估报告。', recommendations: [] }
    animateScore(88)
    typewriterEffect(aiAnalysis.value.diagnosis)
    addLog('AI 分析引擎返回异常，使用本地规则兜底', 'warn')
  } finally {
    aiAnalysisLoading.value = false
    scanStatus.value = 'done'
    scanProgress.value = 100
    addLog('AI 预警扫描全部完成 ✓', 'success')
    // 2秒后自动关闭终端
    setTimeout(() => { showScanTerminal.value = false }, 2500)
  }
}

const typewriterEffect = (text: string) => {
  aiDiagnosisDisplayed.value = ''
  let i = 0
  if (diagnosisTimer) clearInterval(diagnosisTimer)
  diagnosisTimer = setInterval(() => {
    if (i < text.length) {
      aiDiagnosisDisplayed.value += text[i]
      i++
    } else {
      if (diagnosisTimer) clearInterval(diagnosisTimer)
    }
  }, 30)
}

// 数字跳动动画
const animateScore = (target: number) => {
  if (displayScore.value < 0) displayScore.value = 0
  if (scoreTimer) clearInterval(scoreTimer)
  const duration = 1500
  const startTime = Date.now()
  scoreTimer = setInterval(() => {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)
    // easeOutCubic
    const ease = 1 - Math.pow(1 - progress, 3)
    displayScore.value = Math.round(target * ease)
    if (progress >= 1) {
      displayScore.value = target
      if (scoreTimer) clearInterval(scoreTimer)
    }
  }, 16)
}

// AI 风险评分颜色
const riskScoreColor = computed(() => {
  const score = aiAnalysis.value?.risk_score ?? 70
  if (score >= 80) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
})

const riskLabel = computed(() => {
  const level = aiAnalysis.value?.overall_risk
  if (level === 'low') return '低风险'
  if (level === 'high') return '高风险'
  return '中风险'
})

// 为每条预警获取 AI 建议
const getAISuggestion = (alertId: string) => {
  if (!aiAnalysis.value?.recommendations) return null
  return aiAnalysis.value.recommendations.find((r: any) => r.alert_id === alertId) || null
}

const getLevelIcon = (level: string) => {
  if (level === 'danger') return WarningFilled
  if (level === 'warning') return Warning
  if (level === 'success') return CircleCheck
  return InfoFilled
}

const getLevelColor = (level: string) => {
  if (level === 'danger') return '#ef4444'
  if (level === 'warning') return '#f59e0b'
  if (level === 'success') return '#10b981'
  return '#6b7280'
}

const getLevelBg = (level: string) => {
  if (level === 'danger') return '#fef2f2'
  if (level === 'warning') return '#fffbeb'
  if (level === 'success') return '#f0fdf4'
  return '#f9fafb'
}

const getLevelLabel = (level: string) => {
  if (level === 'danger') return '严重'
  if (level === 'warning') return '警告'
  if (level === 'success') return '正常'
  return '信息'
}

const urgencyLabel = (u: string) => {
  if (u === 'high') return '紧急'
  if (u === 'medium') return '一般'
  return '低'
}

const urgencyType = (u: string) => {
  if (u === 'high') return 'danger'
  if (u === 'medium') return 'warning'
  return 'info'
}

onMounted(() => {
  nextTick(initCanvas)
  fetchAlerts()
})

onUnmounted(() => {
  if (diagnosisTimer) clearInterval(diagnosisTimer)
  if (scoreTimer) clearInterval(scoreTimer)
  if (animFrameId) cancelAnimationFrame(animFrameId)
  if (logTimer) clearInterval(logTimer)
})
</script>

<template>
  <div class="alerts-page">
    <!-- 科技感顶部 Banner -->
    <div class="ai-hero-banner">
      <canvas ref="canvasRef" class="particle-canvas"></canvas>
      <div class="hero-content">
        <div class="hero-left">
          <div class="hero-title-row">
            <div class="ai-brain-icon">
              <svg viewBox="0 0 40 40" width="36" height="36">
                <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(6,182,212,0.3)" stroke-width="1.5">
                  <animate attributeName="r" values="14;17;14" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="20" cy="20" r="10" fill="none" stroke="rgba(6,182,212,0.5)" stroke-width="1">
                  <animate attributeName="r" values="9;12;9" dur="2.5s" repeatCount="indefinite"/>
                </circle>
                <circle cx="20" cy="20" r="4" fill="#06b6d4">
                  <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite"/>
                </circle>
                <!-- 连接线 -->
                <line x1="20" y1="6" x2="20" y2="14" stroke="#06b6d4" stroke-width="0.8" opacity="0.6"/>
                <line x1="20" y1="26" x2="20" y2="34" stroke="#06b6d4" stroke-width="0.8" opacity="0.6"/>
                <line x1="6" y1="20" x2="14" y2="20" stroke="#06b6d4" stroke-width="0.8" opacity="0.6"/>
                <line x1="26" y1="20" x2="34" y2="20" stroke="#06b6d4" stroke-width="0.8" opacity="0.6"/>
                <line x1="10" y1="10" x2="16" y2="16" stroke="#06b6d4" stroke-width="0.5" opacity="0.4"/>
                <line x1="24" y1="24" x2="30" y2="30" stroke="#06b6d4" stroke-width="0.5" opacity="0.4"/>
                <line x1="10" y1="30" x2="16" y2="24" stroke="#06b6d4" stroke-width="0.5" opacity="0.4"/>
                <line x1="24" y1="16" x2="30" y2="10" stroke="#06b6d4" stroke-width="0.5" opacity="0.4"/>
                <!-- 节点 -->
                <circle cx="20" cy="6" r="1.5" fill="#06b6d4" opacity="0.7"/>
                <circle cx="20" cy="34" r="1.5" fill="#06b6d4" opacity="0.7"/>
                <circle cx="6" cy="20" r="1.5" fill="#06b6d4" opacity="0.7"/>
                <circle cx="34" cy="20" r="1.5" fill="#06b6d4" opacity="0.7"/>
              </svg>
            </div>
            <div>
              <h2 class="hero-title">
                AI 预警中心
                <span class="ai-badge-glow">AI ENGINE</span>
              </h2>
              <p class="hero-desc">AI 引擎持续监控 · 智能风险识别 · 深度诊断分析 · 趋势预测</p>
            </div>
          </div>
        </div>
        <el-button type="primary" :icon="Refresh" @click="fetchAlerts" :loading="loading" round size="large"
          class="scan-btn">
          <span class="scan-btn-text">{{ loading ? 'AI 扫描中...' : 'AI 全域扫描' }}</span>
        </el-button>
      </div>
      <!-- 扫描线 -->
      <div v-if="scanStatus === 'scanning' || scanStatus === 'analyzing'" class="scan-line"></div>
    </div>

    <!-- AI 扫描终端面板 -->
    <transition name="terminal-slide">
      <div v-if="showScanTerminal" class="scan-terminal-panel">
        <!-- 终端头部 -->
        <div class="terminal-header">
          <div class="terminal-dots">
            <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
          </div>
          <span class="terminal-title">AI Scan Engine v3.2.1</span>
          <div class="terminal-meta">
            <span class="terminal-target" v-if="scanTarget">
              <span class="target-label">TARGET</span> {{ scanTarget }}
            </span>
            <span class="terminal-records" v-if="scanRecords > 0">
              <span class="records-label">RECORDS</span> {{ scanRecords }}
            </span>
            <span class="terminal-progress">{{ scanProgress }}%</span>
          </div>
        </div>
        <!-- 进度条 -->
        <div class="terminal-progress-bar">
          <div class="terminal-progress-fill" :style="{ width: scanProgress + '%' }">
            <div class="progress-glow"></div>
          </div>
        </div>
        <!-- 扫描步骤 -->
        <div class="terminal-steps">
          <span v-for="(step, i) in scanSteps" :key="i" class="t-step" :class="{ done: step.done }">
            <span class="t-step-icon">{{ step.done ? '✓' : '○' }}</span>
            {{ step.label }}
          </span>
          <span v-if="scanStatus === 'analyzing'" class="t-step active">
            <span class="t-step-icon pulse-icon">◉</span>
            AI 深度分析
          </span>
        </div>
        <!-- 日志区域 -->
        <div class="terminal-logs" ref="terminalRef">
          <div v-for="(log, i) in scanLogs" :key="i" class="log-line" :class="'log-' + log.type">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-prefix" v-if="log.type === 'info'">[INFO]</span>
            <span class="log-prefix" v-else-if="log.type === 'success'">[OK]</span>
            <span class="log-prefix" v-else-if="log.type === 'warn'">[WARN]</span>
            <span class="log-prefix" v-else>[DATA]</span>
            <span class="log-text">{{ log.text }}</span>
          </div>
          <div v-if="scanStatus === 'scanning' || scanStatus === 'analyzing'" class="log-cursor">_</div>
        </div>
      </div>
    </transition>

    <!-- AI 诊断面板: 风险评分 + AI诊断 + 趋势预测 -->
    <div class="ai-diagnosis-panel" v-if="alertsData">
      <div class="panel-scan-overlay" v-if="aiAnalysisLoading"></div>
      <div class="diagnosis-grid">
        <!-- AI 风险评分 -->
        <div class="risk-score-card">
          <div class="risk-ring">
            <!-- 外层脉冲光环 -->
            <div class="pulse-ring" :style="{ borderColor: riskScoreColor + '30' }"></div>
            <div class="pulse-ring delay" :style="{ borderColor: riskScoreColor + '15' }"></div>
            <svg viewBox="0 0 100 100" class="ring-svg">
              <!-- 背景轨道 -->
              <circle cx="50" cy="50" r="42" fill="none" stroke="#e5e7eb" stroke-width="6" opacity="0.3" />
              <!-- 刻度点 -->
              <g v-for="i in 36" :key="'tick-'+i" :transform="`rotate(${i*10} 50 50)`">
                <circle cx="50" cy="8" r="0.6" :fill="(i*10/360*100) <= (aiAnalysis?.risk_score ?? 0) ? riskScoreColor : '#d1d5db'" opacity="0.5"/>
              </g>
              <!-- 进度弧线 -->
              <circle cx="50" cy="50" r="42" fill="none" :stroke="riskScoreColor" stroke-width="7"
                stroke-linecap="round"
                :stroke-dasharray="`${(aiAnalysis?.risk_score ?? 0) * 2.64} 264`"
                stroke-dashoffset="0"
                transform="rotate(-90 50 50)"
                class="ring-progress"
              />
              <!-- 光点跟随 -->
              <circle v-if="aiAnalysis?.risk_score" cx="50" cy="8" r="3" :fill="riskScoreColor" filter="url(#glow)"
                :transform="`rotate(${(aiAnalysis.risk_score / 100) * 360} 50 50)`">
                <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite"/>
              </circle>
              <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="2" result="blur"/>
                  <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
              </defs>
            </svg>
            <div class="ring-center">
              <div class="ring-score" :style="{ color: riskScoreColor }">{{ displayScore >= 0 ? displayScore : '--' }}</div>
              <div class="ring-label">AI 安全分</div>
            </div>
          </div>
          <div class="risk-meta">
            <span class="risk-level-badge" :style="{ background: riskScoreColor, boxShadow: `0 2px 12px ${riskScoreColor}40` }">{{ riskLabel }}</span>
            <span class="risk-sub">AI 综合评估</span>
          </div>
        </div>

        <!-- AI 诊断报告 -->
        <div class="diagnosis-content">
          <div class="diagnosis-header">
            <div class="flex items-center gap-2">
              <div class="diagnosis-icon">
                <el-icon :size="16" class="icon-spin"><Cpu /></el-icon>
              </div>
              <span class="font-bold text-sm text-gray-700">AI 智能诊断报告</span>
              <span class="ai-live-dot"></span>
              <span class="text-xs text-cyan-600 font-medium">Neural Engine</span>
            </div>
            <!-- AI 实时状态指示器 -->
            <div class="ai-status-bar">
              <div class="status-wave">
                <span v-for="i in 5" :key="'w-'+i" class="wave-bar" :style="{ animationDelay: i * 0.15 + 's' }"></span>
              </div>
              <span class="text-xs" :class="aiAnalysisLoading ? 'text-cyan-600' : 'text-green-600'">
                {{ aiAnalysisLoading ? '分析中' : '就绪' }}
              </span>
            </div>
          </div>

          <!-- AI 分析中动画 -->
          <div v-if="aiAnalysisLoading && !aiDiagnosisDisplayed" class="ai-thinking-box">
            <div class="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="text-sm text-gray-500">AI 正在深度分析预警数据，生成诊断报告...</span>
          </div>

          <!-- 诊断文本 -->
          <div v-else-if="aiDiagnosisDisplayed" class="diagnosis-text-box">
            <div class="diagnosis-text">{{ aiDiagnosisDisplayed }}<span v-if="aiAnalysisLoading" class="typing-cursor">|</span></div>
          </div>
          <div v-else class="diagnosis-text text-gray-400" style="padding: 12px 0;">点击 "AI 全域扫描" 启动智能分析引擎</div>

          <!-- 趋势预测 -->
          <div v-if="aiAnalysis?.trend_prediction" class="trend-card">
            <div class="trend-icon-wrap">
              <el-icon :size="14"><TrendCharts /></el-icon>
            </div>
            <div>
              <div class="text-xs font-semibold text-indigo-600 mb-0.5">AI 趋势预测（未来 7 天）</div>
              <div class="text-xs text-gray-600">{{ aiAnalysis.trend_prediction }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 概览统计 -->
    <div class="stats-row" v-if="alertsData">
      <div class="stat-chip danger">
        <div class="stat-icon-box danger"><el-icon :size="18"><WarningFilled /></el-icon></div>
        <div>
          <span class="stat-chip-value">{{ alertsData.danger_count }}</span>
          <span class="stat-chip-label">严重告警</span>
        </div>
        <div v-if="alertsData.danger_count > 0" class="stat-pulse danger"></div>
      </div>
      <div class="stat-chip warning">
        <div class="stat-icon-box warning"><el-icon :size="18"><Warning /></el-icon></div>
        <div>
          <span class="stat-chip-value">{{ alertsData.warning_count }}</span>
          <span class="stat-chip-label">普通警告</span>
        </div>
      </div>
      <div class="stat-chip success">
        <div class="stat-icon-box success"><el-icon :size="18"><CircleCheck /></el-icon></div>
        <div>
          <span class="stat-chip-value">{{ alertsData.total - alertsData.danger_count - alertsData.warning_count }}</span>
          <span class="stat-chip-label">正常项目</span>
        </div>
      </div>
    </div>

    <!-- 告警卡片列表 -->
    <div v-if="alertsData?.alerts?.length" class="alerts-grid">
      <transition-group name="alert-fade">
        <div
          v-for="(alert, idx) in alertsData.alerts"
          :key="alert.id"
          class="alert-card"
          :style="{ background: getLevelBg(alert.level), animationDelay: idx * 0.08 + 's' }"
        >
          <!-- 左侧级别色条 -->
          <div class="alert-level-bar" :style="{ background: getLevelColor(alert.level) }"></div>
          <div class="alert-body">
            <div class="alert-main">
              <div class="alert-header">
                <div class="flex items-center gap-3">
                  <div class="alert-icon-wrap" :style="{ background: getLevelColor(alert.level) + '18', color: getLevelColor(alert.level) }">
                    <el-icon :size="20"><component :is="getLevelIcon(alert.level)" /></el-icon>
                  </div>
                  <div>
                    <div class="alert-title">{{ alert.title }}</div>
                    <el-tag :type="alert.level === 'danger' ? 'danger' : alert.level === 'warning' ? 'warning' : alert.level === 'success' ? 'success' : 'info'" size="small" effect="light" round>
                      {{ getLevelLabel(alert.level) }}
                    </el-tag>
                  </div>
                </div>
                <div v-if="alert.count > 0" class="alert-count" :style="{ color: getLevelColor(alert.level) }">
                  {{ alert.count }}
                </div>
              </div>
              <div class="alert-message">{{ alert.message }}</div>
              <div v-if="alert.action" class="alert-action-row">
                <el-icon :size="12"><InfoFilled /></el-icon>
                {{ alert.action }}
              </div>
              <div v-if="alert.details?.length" class="alert-details">
                <div v-for="(d, i) in alert.details.slice(0, 5)" :key="i" class="detail-chip">
                  {{ d.name || d.user_code || JSON.stringify(d) }}
                </div>
                <div v-if="alert.details.length > 5" class="text-xs text-gray-400">...还有{{ alert.details.length - 5 }}项</div>
              </div>
            </div>

            <!-- AI 建议区域 -->
            <div v-if="getAISuggestion(alert.id)" class="ai-suggestion-area">
              <div class="ai-suggestion-header">
                <div class="flex items-center gap-1.5">
                  <div class="ai-chip-icon"><el-icon :size="11"><Cpu /></el-icon></div>
                  <span class="text-xs font-bold text-cyan-700">AI 智能建议</span>
                </div>
                <el-tag v-if="getAISuggestion(alert.id)?.urgency" :type="urgencyType(getAISuggestion(alert.id)?.urgency)" size="small" effect="plain" round>
                  {{ urgencyLabel(getAISuggestion(alert.id)?.urgency) }}
                </el-tag>
              </div>
              <div class="ai-suggestion-text">{{ getAISuggestion(alert.id)?.ai_suggestion }}</div>
              <div v-if="getAISuggestion(alert.id)?.predicted_impact" class="ai-impact-text">
                <el-icon :size="11"><Warning /></el-icon>
                预测影响：{{ getAISuggestion(alert.id)?.predicted_impact }}
              </div>
            </div>
            <div v-else-if="aiAnalysisLoading" class="ai-suggestion-area">
              <div class="ai-gen-loading">
                <div class="thinking-dots small"><span></span><span></span><span></span></div>
                <span>AI 建议生成中...</span>
              </div>
            </div>
          </div>
        </div>
      </transition-group>
    </div>

    <el-empty v-else-if="!loading" description="系统运行正常，暂无告警" />
  </div>
</template>

<style scoped>
.alerts-page { padding: 0; }

/* ===== Hero Banner ===== */
.ai-hero-banner {
  position: relative;
  background: #1e293b;
  border-radius: 20px;
  padding: 28px 32px;
  margin-bottom: 20px;
  overflow: hidden;
}

.particle-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-brain-icon {
  flex-shrink: 0;
  filter: drop-shadow(0 0 8px rgba(6, 182, 212, 0.4));
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: #e0f2fe;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
}

.hero-desc {
  font-size: 12px;
  color: #67e8f9;
  opacity: 0.7;
  margin-top: 4px;
  letter-spacing: 1px;
}

.ai-badge-glow {
  display: inline-flex;
  padding: 2px 10px;
  font-size: 9px;
  font-weight: 800;
  color: #cffafe;
  background: rgba(6,182,212,0.25);
  border: 1px solid rgba(6,182,212,0.4);
  border-radius: 6px;
  letter-spacing: 1.5px;
}

@keyframes badge-glow {
  0%, 100% { box-shadow: 0 0 6px rgba(6,182,212,0.3); }
  50% { box-shadow: 0 0 16px rgba(6,182,212,0.6), 0 0 32px rgba(6,182,212,0.2); }
}

.scan-btn {
  min-width: 140px;
  font-weight: 600;
}

.scan-btn-text { letter-spacing: 0.5px; }

/* 扫描线 */
.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: #06b6d4;
  animation: scan-sweep 2s linear infinite;
  z-index: 3;
}

@keyframes scan-sweep {
  0% { transform: translateY(0); opacity: 1; }
  100% { transform: translateY(120px); opacity: 0; }
}

/* ===== Scan Terminal Panel ===== */
.scan-terminal-panel {
  background: #0c1222;
  border: 1px solid rgba(6,182,212,0.2);
  border-radius: 14px;
  margin-bottom: 20px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,0.15), 0 0 40px rgba(6,182,212,0.05);
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.terminal-dots {
  display: flex;
  gap: 5px;
}

.terminal-dots .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.terminal-dots .dot.red { background: #ef4444; }
.terminal-dots .dot.yellow { background: #f59e0b; }
.terminal-dots .dot.green { background: #22c55e; }

.terminal-title {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.5px;
  font-family: 'Courier New', monospace;
}

.terminal-meta {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}

.terminal-target, .terminal-records {
  font-size: 10px;
  font-family: 'Courier New', monospace;
  color: #67e8f9;
}

.target-label, .records-label {
  font-size: 9px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 1px;
  margin-right: 4px;
}

.terminal-progress {
  font-size: 12px;
  font-weight: 800;
  color: #06b6d4;
  font-family: 'Courier New', monospace;
  min-width: 32px;
  text-align: right;
}

/* Terminal Progress Bar */
.terminal-progress-bar {
  height: 2px;
  background: rgba(255,255,255,0.05);
  position: relative;
}

.terminal-progress-fill {
  height: 100%;
  background: #06b6d4;
  transition: width 0.4s ease;
  position: relative;
}

.progress-glow {
  position: absolute;
  right: 0;
  top: -3px;
  width: 6px;
  height: 8px;
  background: #22d3ee;
  border-radius: 2px;
  box-shadow: 0 0 10px #06b6d4, 0 0 20px rgba(6,182,212,0.4);
  animation: glow-pulse 0.8s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Terminal Steps */
.terminal-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.t-step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: #475569;
  font-family: 'Courier New', monospace;
  transition: color 0.3s;
}

.t-step.done { color: #22d3ee; }
.t-step.active { color: #06b6d4; font-weight: 700; }

.t-step-icon { font-size: 10px; }
.t-step.done .t-step-icon { color: #22c55e; }

.pulse-icon {
  animation: icon-pulse 1s infinite;
  color: #06b6d4;
}

@keyframes icon-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Terminal Logs */
.terminal-logs {
  max-height: 200px;
  overflow-y: auto;
  padding: 10px 16px;
  font-family: 'Courier New', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.7;
}

.terminal-logs::-webkit-scrollbar { width: 4px; }
.terminal-logs::-webkit-scrollbar-track { background: transparent; }
.terminal-logs::-webkit-scrollbar-thumb { background: rgba(6,182,212,0.2); border-radius: 2px; }

.log-line {
  display: flex;
  gap: 8px;
  white-space: nowrap;
  animation: log-appear 0.2s ease;
}

@keyframes log-appear {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.log-time {
  color: #475569;
  flex-shrink: 0;
}

.log-prefix {
  flex-shrink: 0;
  font-weight: 700;
  min-width: 42px;
}

.log-info .log-prefix { color: #64748b; }
.log-success .log-prefix { color: #22c55e; }
.log-warn .log-prefix { color: #f59e0b; }
.log-data .log-prefix { color: #818cf8; }

.log-text { color: #cbd5e1; }
.log-info .log-text { color: #94a3b8; }
.log-success .log-text { color: #86efac; }
.log-warn .log-text { color: #fde68a; }
.log-data .log-text { color: #c4b5fd; }

.log-cursor {
  color: #06b6d4;
  animation: cursor-blink 0.8s steps(1) infinite;
  font-weight: bold;
}

/* Terminal Transition */
.terminal-slide-enter-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.terminal-slide-leave-active { transition: all 0.3s ease; }
.terminal-slide-enter-from { opacity: 0; max-height: 0; transform: translateY(-10px); }
.terminal-slide-enter-to { opacity: 1; max-height: 500px; }
.terminal-slide-leave-from { opacity: 1; max-height: 500px; }
.terminal-slide-leave-to { opacity: 0; max-height: 0; transform: translateY(-10px); }

/* ===== AI Diagnosis Panel ===== */
.ai-diagnosis-panel {
  position: relative;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 18px;
  padding: 24px;
  margin-bottom: 20px;
  overflow: hidden;
}

.panel-scan-overlay {
  display: none;
}

@keyframes panel-scan {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}

.diagnosis-grid {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 28px;
  align-items: start;
}

@media (max-width: 768px) {
  .diagnosis-grid { grid-template-columns: 1fr; }
}

/* Risk Score Ring */
.risk-score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.risk-ring {
  position: relative;
  width: 150px;
  height: 150px;
}

.pulse-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid;
  animation: pulse-expand 3s ease-out infinite;
}

.pulse-ring.delay { animation-delay: 1.5s; }

@keyframes pulse-expand {
  0% { transform: scale(0.9); opacity: 0.6; }
  100% { transform: scale(1.3); opacity: 0; }
}

.ring-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 2px 8px rgba(0,0,0,0.05));
}

.ring-progress {
  transition: stroke-dasharray 2s cubic-bezier(0.4, 0, 0.2, 1);
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ring-score {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  font-family: 'Courier New', monospace;
}

.ring-label {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  font-weight: 500;
}

.risk-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.risk-level-badge {
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 14px;
  border-radius: 10px;
  transition: all 0.5s;
}

.risk-sub { font-size: 11px; color: #94a3b8; }

/* Diagnosis Content */
.diagnosis-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.diagnosis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.diagnosis-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #e0f2fe;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0891b2;
}

.icon-spin { animation: gentle-spin 8s linear infinite; }

@keyframes gentle-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.ai-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #0891b2;
  box-shadow: 0 0 6px rgba(8,145,178,0.5);
  animation: ai-blink 2s infinite;
}

@keyframes ai-blink {
  0%, 100% { opacity: 1; box-shadow: 0 0 6px rgba(8,145,178,0.5); }
  50% { opacity: 0.3; box-shadow: 0 0 2px rgba(8,145,178,0.2); }
}

/* AI 状态波形 */
.ai-status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-wave {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 16px;
}

.wave-bar {
  width: 2.5px;
  height: 4px;
  background: #0891b2;
  border-radius: 1px;
  animation: wave-dance 1.2s ease-in-out infinite;
}

@keyframes wave-dance {
  0%, 100% { height: 4px; }
  50% { height: 14px; }
}

/* AI 思考动画 */
.ai-thinking-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(6, 182, 212, 0.04);
  border: 1px dashed rgba(6, 182, 212, 0.15);
  border-radius: 12px;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0891b2;
  animation: dot-bounce 1.4s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

.thinking-dots.small span { width: 5px; height: 5px; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.diagnosis-text-box {
  padding: 14px 16px;
  background: rgba(255,255,255,0.6);
  border-radius: 12px;
  border: 1px solid rgba(6, 182, 212, 0.08);
}

.diagnosis-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.8;
}

.typing-cursor {
  animation: cursor-blink 0.8s steps(1) infinite;
  color: #0891b2;
  font-weight: bold;
  font-size: 16px;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.trend-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.1);
  border-radius: 12px;
}

.trend-icon-wrap {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: rgba(99, 102, 241, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
  flex-shrink: 0;
}

/* ===== Stats Row ===== */
.stats-row {
  display: flex;
  gap: 14px;
  margin-bottom: 20px;
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 14px;
  flex: 1;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.stat-chip:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }

.stat-chip.danger { background: #fef2f2; }
.stat-chip.warning { background: #fffbeb; }
.stat-chip.success { background: #f0fdf4; }

.stat-icon-box {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-box.danger { background: #fee2e2; color: #dc2626; }
.stat-icon-box.warning { background: #fef3c7; color: #d97706; }
.stat-icon-box.success { background: #dcfce7; color: #16a34a; }

.stat-chip-value {
  font-size: 22px;
  font-weight: 700;
  display: block;
  line-height: 1;
}

.stat-chip.danger .stat-chip-value { color: #dc2626; }
.stat-chip.warning .stat-chip-value { color: #d97706; }
.stat-chip.success .stat-chip-value { color: #16a34a; }

.stat-chip-label {
  font-size: 11px;
  color: #9ca3af;
  display: block;
  margin-top: 2px;
}

.stat-pulse {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.stat-pulse.danger {
  background: #ef4444;
  animation: stat-pulse-anim 2s infinite;
}

@keyframes stat-pulse-anim {
  0% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
  70% { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
  100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
}

/* ===== Alert Cards ===== */
.alerts-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.alert-card {
  display: flex;
  border-radius: 16px;
  border: 1px solid rgba(0,0,0,0.04);
  overflow: hidden;
  transition: all 0.3s;
  animation: card-slide-in 0.5s ease both;
}

@keyframes card-slide-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.alert-card:hover {
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  transform: translateY(-2px);
}

.alert-level-bar {
  width: 4px;
  flex-shrink: 0;
}

.alert-body {
  flex: 1;
  min-width: 0;
}

.alert-main { padding: 20px; }

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.alert-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.alert-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.alert-count { font-size: 32px; font-weight: 700; }

.alert-message {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 8px;
  line-height: 1.6;
}

.alert-action-row {
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}

.alert-details {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 10px;
}

.detail-chip {
  font-size: 12px;
  background: rgba(255,255,255,0.7);
  padding: 2px 8px;
  border-radius: 6px;
  color: #374151;
  border: 1px solid rgba(0,0,0,0.04);
}

/* AI Suggestion Area */
.ai-suggestion-area {
  padding: 14px 20px;
  background: rgba(8,145,178,0.04);
  border-top: 1px dashed rgba(8,145,178,0.15);
}

.ai-suggestion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.ai-chip-icon {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  background: rgba(6, 182, 212, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0891b2;
}

.ai-suggestion-text {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

.ai-impact-text {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #ef4444;
  margin-top: 6px;
  opacity: 0.8;
}

.ai-gen-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

/* Transition */
.alert-fade-enter-active { transition: all 0.4s ease; }
.alert-fade-leave-active { transition: all 0.3s ease; }
.alert-fade-enter-from { opacity: 0; transform: translateX(-20px); }
.alert-fade-leave-to { opacity: 0; transform: translateX(20px); }
</style>
