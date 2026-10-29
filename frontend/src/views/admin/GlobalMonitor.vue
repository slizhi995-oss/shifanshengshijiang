<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { VideoCamera, Cpu, Warning, TrendCharts, User, DataLine, Refresh, Search } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { aiApi } from '@/api/ai'
import VideoAnalysisCard from '@/components/VideoAnalysisCard.vue'

const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const instructors = ref<any[]>([])
const selectedInstructorId = ref<number | null>(null)
const monitorData = ref<any[]>([])
const loading = ref(false)
const pagination = ref({ page: 1, page_size: 20, total: 0 })

// 展开行控制
const expandedRows = ref<string[]>([])

// 视频分析对话框
const videoAnalysisDialogVisible = ref(false)
const currentAnalysisSubmissionId = ref<number | null>(null)
const currentAnalysisSubmission = ref<any>(null)

// 筛选条件
const filterCollege = ref('')
const filterMajor = ref('')
const filterClass = ref('')
const filterRisk = ref('')

// AI 数据叙事
const aiNarrative = ref('')
const aiNarrativeLoading = ref(false)
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

// Canvas 粒子网络
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animFrameId: number | null = null
let particles: { x: number; y: number; vx: number; vy: number; r: number; alpha: number }[] = []

// AI 监控状态
const monitorStatus = ref<'idle' | 'scanning' | 'done'>('idle')
const lastScanTime = ref('')

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
  const w = canvas.offsetWidth, h = canvas.offsetHeight
  particles = Array.from({ length: 35 }, () => ({
    x: Math.random() * w, y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
    r: Math.random() * 1.5 + 0.8, alpha: Math.random() * 0.4 + 0.15,
  }))
  const animate = () => {
    const cw = canvas.offsetWidth, ch = canvas.offsetHeight
    ctx.clearRect(0, 0, cw, ch)
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy
      if (p.x < 0 || p.x > cw) p.vx *= -1
      if (p.y < 0 || p.y > ch) p.vy *= -1
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(6,182,212,${p.alpha})`; ctx.fill()
    }
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 90) {
          ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(6,182,212,${0.12 * (1 - dist / 90)})`
          ctx.lineWidth = 0.5; ctx.stroke()
        }
      }
    }
    animFrameId = requestAnimationFrame(animate)
  }
  animate()
}

// AI 风险评估 - 根据提交数据智能计算
const getAIRisk = (row: any): { level: string; color: string; label: string; score: number } => {
  const stats = row.stats
  if (!stats) return { level: 'unknown', color: '#9ca3af', label: '未知', score: 0 }
  const totalTasks = stats.total_tasks || 0
  if (totalTasks === 0) return { level: 'none', color: '#d1d5db', label: '无任务', score: 0 }
  const submittedRate = stats.submitted / totalTasks
  const rejectedRate = stats.rejected / totalTasks
  let riskScore = 100
  riskScore -= (1 - submittedRate) * 50
  riskScore -= rejectedRate * 30
  riskScore -= (stats.pending / totalTasks) * 10
  riskScore = Math.max(0, Math.min(100, riskScore))
  if (riskScore >= 80) return { level: 'low', color: '#10b981', label: '健康', score: Math.round(riskScore) }
  if (riskScore >= 60) return { level: 'medium', color: '#f59e0b', label: '关注', score: Math.round(riskScore) }
  return { level: 'high', color: '#ef4444', label: '高风险', score: Math.round(riskScore) }
}

// AI 异常检测统计
const aiStats = computed(() => {
  const data = monitorData.value
  if (!data.length) return { total: 0, highRisk: 0, mediumRisk: 0, healthy: 0, zeroSubmit: 0, avgCompletion: 0 }
  let highRisk = 0, mediumRisk = 0, healthy = 0, zeroSubmit = 0, totalCompletion = 0
  data.forEach(row => {
    const risk = getAIRisk(row)
    if (risk.level === 'high') highRisk++
    else if (risk.level === 'medium') mediumRisk++
    else if (risk.level === 'low') healthy++
    if (row.stats?.submitted === 0 && row.stats?.total_tasks > 0) zeroSubmit++
    const total = row.stats?.total_tasks || 0
    if (total > 0) totalCompletion += (row.stats.approved / total) * 100
  })
  return { total: data.length, highRisk, mediumRisk, healthy, zeroSubmit,
    avgCompletion: data.length > 0 ? Math.round(totalCompletion / data.length) : 0 }
})

// AI 风险分布百分比
const riskDistribution = computed(() => {
  const s = aiStats.value
  const total = s.total || 1
  return {
    highPct: Math.round((s.highRisk / total) * 100),
    medPct: Math.round((s.mediumRisk / total) * 100),
    lowPct: Math.round((s.healthy / total) * 100),
  }
})

// 筛选选项
const collegeOptions = computed(() => {
  const set = new Set<string>()
  monitorData.value.forEach(item => { if (item.student?.college) set.add(item.student.college) })
  return Array.from(set)
})
const majorOptions = computed(() => {
  const set = new Set<string>()
  monitorData.value.forEach(item => { if (item.student?.major) set.add(item.student.major) })
  return Array.from(set)
})
const classOptions = computed(() => {
  const set = new Set<string>()
  monitorData.value.forEach(item => { if (item.student?.class_name) set.add(item.student.class_name) })
  return Array.from(set)
})

// 过滤后的数据
const filteredData = computed(() => {
  return monitorData.value.filter(item => {
    if (filterCollege.value && item.student?.college !== filterCollege.value) return false
    if (filterMajor.value && item.student?.major !== filterMajor.value) return false
    if (filterClass.value && item.student?.class_name !== filterClass.value) return false
    if (filterRisk.value) {
      const risk = getAIRisk(item)
      if (filterRisk.value !== risk.level) return false
    }
    return true
  })
})

const fetchSemesters = async () => {
  const res: any = await api.get('/semesters')
  semesters.value = res.filter((s: any) => s.status === 'active' || s.status === 'completed')
  if (semesters.value.length > 0) {
    selectedSemesterId.value = semesters.value[0].id
    fetchInstructors()
    fetchMonitorData()
  }
}

const fetchInstructors = async () => {
  if (!selectedSemesterId.value) return
  try {
    const res: any = await api.get(`/admin/instructors/${selectedSemesterId.value}`)
    instructors.value = res
  } catch (error) {}
}

const fetchMonitorData = async () => {
  if (!selectedSemesterId.value) return
  loading.value = true
  monitorStatus.value = 'scanning'
  try {
    const params: any = { page: pagination.value.page, page_size: pagination.value.page_size }
    if (selectedInstructorId.value) params.instructor_id = selectedInstructorId.value
    const res: any = await api.get(`/admin/monitor/${selectedSemesterId.value}`, { params })
    monitorData.value = res.items
    pagination.value.total = res.total
    lastScanTime.value = new Date().toLocaleTimeString()
    fetchAINarrative()
  } finally {
    loading.value = false
    monitorStatus.value = 'done'
  }
}

// AI 数据叙事
const typewriterEffect = (text: string) => {
  aiNarrativeDisplayed.value = ''
  let i = 0
  if (narrativeTimer) clearInterval(narrativeTimer)
  narrativeTimer = setInterval(() => {
    if (i < text.length) { aiNarrativeDisplayed.value += text[i]; i++ }
    else { if (narrativeTimer) clearInterval(narrativeTimer) }
  }, 30)
}

const fetchAINarrative = async () => {
  if (!monitorData.value.length) return
  aiNarrativeLoading.value = true
  try {
    const stats = aiStats.value
    const narrativeStats: Record<string, any> = {
      total_students: stats.total, high_risk_count: stats.highRisk,
      medium_risk_count: stats.mediumRisk, healthy_count: stats.healthy,
      zero_submit_count: stats.zeroSubmit, avg_completion: stats.avgCompletion,
      context: '全局监控页面，管理员视角分析所有学生的试讲提交情况'
    }
    const res = await aiApi.dataNarrative({ role: 'admin', stats: narrativeStats })
    if (res.success && res.data?.narrative) {
      aiNarrative.value = res.data.narrative
      typewriterEffect(res.data.narrative)
    }
  } catch { aiNarrative.value = '' }
  finally { aiNarrativeLoading.value = false }
}

const handleSemesterChange = () => {
  selectedInstructorId.value = null
  filterCollege.value = ''; filterMajor.value = ''; filterClass.value = ''; filterRisk.value = ''
  fetchInstructors(); fetchMonitorData()
}

const handleRowClick = (row: any) => {
  const rowKey = String(row.student.id)
  const idx = expandedRows.value.indexOf(rowKey)
  if (idx > -1) expandedRows.value.splice(idx, 1)
  else expandedRows.value.push(rowKey)
}

const handlePageChange = (page: number) => {
  pagination.value.page = page; fetchMonitorData()
}

const openFile = (path: string) => {
  if (!path) return; window.open(`/uploads/${path}`, '_blank')
}

const viewVideoAnalysis = (submission: any, event: Event) => {
  event.stopPropagation()
  currentAnalysisSubmission.value = submission
  currentAnalysisSubmissionId.value = submission.id
  videoAnalysisDialogVisible.value = true
}

onMounted(() => {
  nextTick(initCanvas)
  fetchSemesters()
})

onUnmounted(() => {
  if (narrativeTimer) clearInterval(narrativeTimer)
  if (animFrameId) cancelAnimationFrame(animFrameId)
})
</script>

<style scoped>
.monitor-page { padding: 0; }

/* ===== Hero Banner ===== */
.ai-hero-banner {
  position: relative;
  background: #1e293b;
  border-radius: 20px;
  padding: 24px 28px;
  margin-bottom: 20px;
  overflow: hidden;
}
.particle-canvas { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.hero-content { position: relative; z-index: 2; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
.hero-left { display: flex; align-items: center; gap: 14px; }
.hero-title { font-size: 20px; font-weight: 700; color: #e0f2fe; margin: 0; display: flex; align-items: center; gap: 10px; }
.hero-desc { font-size: 12px; color: #67e8f9; opacity: 0.7; margin-top: 3px; letter-spacing: 0.5px; }
.ai-badge-glow {
  display: inline-flex; padding: 2px 10px; font-size: 9px; font-weight: 800; color: #cffafe;
  background: rgba(6,182,212,0.25);
  border: 1px solid rgba(6,182,212,0.4); border-radius: 6px; letter-spacing: 1.5px;
}
@keyframes badge-glow {
  0%, 100% { box-shadow: 0 0 6px rgba(6,182,212,0.3); }
  50% { box-shadow: 0 0 16px rgba(6,182,212,0.6), 0 0 32px rgba(6,182,212,0.2); }
}
.hero-controls { display: flex; align-items: center; gap: 10px; }
.hero-status { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #94a3b8; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.5); }
.status-dot.scanning { background: #06b6d4; animation: dot-blink 1s infinite; }
@keyframes dot-blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
.scan-line {
  position: absolute; top: 0; left: 0; width: 100%; height: 2px;
  background: #06b6d4;
  animation: scan-sweep 2s linear infinite; z-index: 3;
}
@keyframes scan-sweep { 0%{transform:translateY(0);opacity:1;} 100%{transform:translateY(100px);opacity:0;} }
/* AI Brain Icon */
.ai-brain-icon { flex-shrink: 0; filter: drop-shadow(0 0 6px rgba(6,182,212,0.4)); }

/* ===== AI Dashboard Grid ===== */
.ai-dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
@media (max-width: 900px) { .ai-dashboard-grid { grid-template-columns: 1fr; } }

/* Stats Panel */
.ai-stats-panel {
  background: white;
  border: 1px solid #f1f5f9;
  border-radius: 16px;
  padding: 20px;
}
.panel-title { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.panel-title-icon {
  width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  background: #ecfeff; color: #0891b2;
}
.panel-title span { font-size: 14px; font-weight: 600; color: #1e293b; }
.ai-tag-sm { font-size: 9px; font-weight: 700; color: #fff; background: #0891b2; border-radius: 3px; padding: 1px 5px; letter-spacing: 0.5px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.stat-item {
  text-align: center;
  padding: 12px 8px;
  border-radius: 12px;
  transition: all 0.2s;
  cursor: pointer;
  position: relative;
}
.stat-item:hover { transform: translateY(-2px); }
.stat-item.danger { background: #fef2f2; }
.stat-item.warning { background: #fffbeb; }
.stat-item.success { background: #f0fdf4; }
.stat-item.info { background: #f0f9ff; }
.stat-item.active { box-shadow: 0 0 0 2px #0891b2; }
.stat-value { font-size: 24px; font-weight: 800; line-height: 1; }
.stat-item.danger .stat-value { color: #ef4444; }
.stat-item.warning .stat-value { color: #d97706; }
.stat-item.success .stat-value { color: #059669; }
.stat-item.info .stat-value { color: #2563eb; }
.stat-label { font-size: 11px; color: #64748b; margin-top: 4px; }
.stat-pulse { position: absolute; top: 6px; right: 6px; width: 7px; height: 7px; border-radius: 50%; background: #ef4444; animation: sp 2s infinite; }
@keyframes sp { 0%{box-shadow:0 0 0 0 rgba(239,68,68,.4)} 70%{box-shadow:0 0 0 6px rgba(239,68,68,0)} 100%{box-shadow:0 0 0 0 rgba(239,68,68,0)} }

/* Risk Distribution */
.risk-distrib-panel {
  background: white;
  border: 1px solid #f1f5f9;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
}
.risk-bar-wrap { display: flex; border-radius: 8px; overflow: hidden; height: 28px; margin-bottom: 16px; }
.risk-seg { display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: white; transition: width 0.8s ease; min-width: 0; }
.risk-seg.high { background: #ef4444; }
.risk-seg.med { background: #f59e0b; }
.risk-seg.low { background: #10b981; }
.risk-legend { display: flex; gap: 16px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #4b5563; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.legend-dot.high { background: #ef4444; }
.legend-dot.med { background: #f59e0b; }
.legend-dot.low { background: #10b981; }
.legend-num { font-weight: 700; }

/* Quick Stats Row */
.quick-stats-row { display: flex; gap: 10px; margin-top: auto; padding-top: 12px; border-top: 1px solid #f1f5f9; }
.quick-stat { flex: 1; text-align: center; padding: 8px; background: #f8fafc; border-radius: 8px; }
.quick-stat-val { font-size: 16px; font-weight: 700; color: #1e293b; }
.quick-stat-label { font-size: 10px; color: #94a3b8; margin-top: 2px; }

/* ===== AI Narrative ===== */
.ai-narrative-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 16px;
  padding: 18px 22px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}
.ai-narrative-inner { display: flex; gap: 14px; align-items: flex-start; position: relative; z-index: 1; }
.ai-narrative-icon {
  width: 36px; height: 36px; min-width: 36px; border-radius: 10px;
  background: #e0f2fe;
  display: flex; align-items: center; justify-content: center; color: #0891b2;
}
.icon-spin { animation: gspin 8s linear infinite; }
@keyframes gspin { 0%{transform:rotate(0)} 100%{transform:rotate(360deg)} }
.ai-narrative-body { flex: 1; min-width: 0; }
.ai-narrative-label { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ai-live-dot { width: 6px; height: 6px; border-radius: 50%; background: #0891b2; box-shadow: 0 0 4px rgba(8,145,178,0.5); animation: ai-blink 2s infinite; }
@keyframes ai-blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
.narrative-text { font-size: 13px; color: #374151; line-height: 1.8; }
.narrative-loading { font-size: 13px; color: #94a3b8; display: flex; align-items: center; gap: 8px; }
.thinking-dots { display: flex; gap: 3px; }
.thinking-dots span { width: 5px; height: 5px; border-radius: 50%; background: #0891b2; animation: tdb 1.4s ease-in-out infinite; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes tdb { 0%,80%,100%{transform:scale(.6);opacity:.4} 40%{transform:scale(1);opacity:1} }
.typing-cursor { animation: cblink .8s steps(1) infinite; color: #0891b2; font-weight: bold; }
@keyframes cblink { 0%,100%{opacity:1} 50%{opacity:0} }
/* wave status bar in narrative */
.ai-status-bar { display: flex; align-items: center; gap: 5px; margin-left: auto; }
.status-wave { display: flex; align-items: center; gap: 2px; height: 14px; }
.wave-bar { width: 2px; height: 3px; background: #0891b2; border-radius: 1px; animation: wd 1.2s ease-in-out infinite; }
@keyframes wd { 0%,100%{height:3px} 50%{height:12px} }

/* ===== Filter Bar ===== */
.filter-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 12px 16px; background: #f8fafc; border-radius: 12px; margin-bottom: 16px;
  border: 1px solid #f1f5f9;
}
.filter-label { font-size: 12px; color: #64748b; font-weight: 600; display: flex; align-items: center; gap: 4px; }
.filter-count { font-size: 12px; color: #94a3b8; margin-left: auto; }

/* ===== Table ===== */
.table-card { border-radius: 16px !important; border-color: #f1f5f9 !important; }
.ai-col-badge {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0 4px; font-size: 9px; font-weight: 700; color: #fff;
  background: #0891b2;
  border-radius: 3px; line-height: 14px; letter-spacing: 0.5px;
}
.risk-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.health-score-bar { width: 100%; height: 4px; border-radius: 2px; background: #e5e7eb; overflow: hidden; margin-top: 3px; }
.health-score-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease; }
:deep(.hidden-expand-icon .el-table__expand-icon) { display: none; }
:deep(.el-table__row) { cursor: pointer; }
.mr-1 { margin-right: 4px; }
</style>

<template>
  <div v-loading="loading" class="monitor-page">
    <!-- 科技感 Hero Banner -->
    <div class="ai-hero-banner">
      <canvas ref="canvasRef" class="particle-canvas"></canvas>
      <div class="hero-content">
        <div class="hero-left">
          <div class="ai-brain-icon">
            <svg viewBox="0 0 36 36" width="32" height="32">
              <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(6,182,212,0.3)" stroke-width="1.2">
                <animate attributeName="r" values="12;15;12" dur="3s" repeatCount="indefinite"/>
              </circle>
              <circle cx="18" cy="18" r="8" fill="none" stroke="rgba(6,182,212,0.5)" stroke-width="0.8">
                <animate attributeName="r" values="7;10;7" dur="2.5s" repeatCount="indefinite"/>
              </circle>
              <circle cx="18" cy="18" r="3" fill="#06b6d4">
                <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite"/>
              </circle>
              <line x1="18" y1="4" x2="18" y2="12" stroke="#06b6d4" stroke-width="0.6" opacity="0.5"/>
              <line x1="18" y1="24" x2="18" y2="32" stroke="#06b6d4" stroke-width="0.6" opacity="0.5"/>
              <line x1="4" y1="18" x2="12" y2="18" stroke="#06b6d4" stroke-width="0.6" opacity="0.5"/>
              <line x1="24" y1="18" x2="32" y2="18" stroke="#06b6d4" stroke-width="0.6" opacity="0.5"/>
              <circle cx="18" cy="4" r="1.2" fill="#06b6d4" opacity="0.6"/>
              <circle cx="18" cy="32" r="1.2" fill="#06b6d4" opacity="0.6"/>
              <circle cx="4" cy="18" r="1.2" fill="#06b6d4" opacity="0.6"/>
              <circle cx="32" cy="18" r="1.2" fill="#06b6d4" opacity="0.6"/>
            </svg>
          </div>
          <div>
            <h2 class="hero-title">AI 全局监控 <span class="ai-badge-glow">MONITOR</span></h2>
            <p class="hero-desc">AI 实时分析 · 风险智能识别 · 异常自动预警 · 数据驱动决策</p>
          </div>
        </div>
        <div class="hero-controls">
          <div class="hero-status">
            <span class="status-dot" :class="{ scanning: monitorStatus === 'scanning' }"></span>
            <span>{{ monitorStatus === 'scanning' ? 'AI 扫描中...' : lastScanTime ? `上次: ${lastScanTime}` : '就绪' }}</span>
          </div>
          <el-select v-model="selectedSemesterId" placeholder="选择批次" @change="handleSemesterChange" size="default"
            style="width: 160px;" popper-class="dark-select">
            <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-select v-model="selectedInstructorId" placeholder="筛选老师" clearable @change="fetchMonitorData" size="default"
            style="width: 160px;">
            <el-option v-for="i in instructors" :key="i.id" :label="`${i.name} (${i.student_count}人)`" :value="i.id" />
          </el-select>
          <el-button :icon="Refresh" @click="fetchMonitorData" :loading="loading" circle type="primary" />
        </div>
      </div>
      <div v-if="monitorStatus === 'scanning'" class="scan-line"></div>
    </div>

    <!-- AI 仪表盘: 统计 + 风险分布 -->
    <div class="ai-dashboard-grid" v-if="aiStats.total > 0">
      <!-- 左: AI 统计面板 -->
      <div class="ai-stats-panel">
        <div class="panel-title">
          <div class="panel-title-icon"><el-icon :size="14"><TrendCharts /></el-icon></div>
          <span>AI 异常检测</span>
          <span class="ai-tag-sm">AI</span>
        </div>
        <div class="stats-grid">
          <div class="stat-item info" @click="filterRisk = ''">
            <div class="stat-value">{{ aiStats.total }}</div>
            <div class="stat-label">监控学生</div>
          </div>
          <div class="stat-item danger" :class="{ active: filterRisk === 'high' }" @click="filterRisk = filterRisk === 'high' ? '' : 'high'">
            <div class="stat-value">{{ aiStats.highRisk }}</div>
            <div class="stat-label">高风险</div>
            <div v-if="aiStats.highRisk > 0" class="stat-pulse"></div>
          </div>
          <div class="stat-item warning" :class="{ active: filterRisk === 'medium' }" @click="filterRisk = filterRisk === 'medium' ? '' : 'medium'">
            <div class="stat-value">{{ aiStats.mediumRisk }}</div>
            <div class="stat-label">需关注</div>
          </div>
          <div class="stat-item success" :class="{ active: filterRisk === 'low' }" @click="filterRisk = filterRisk === 'low' ? '' : 'low'">
            <div class="stat-value">{{ aiStats.healthy }}</div>
            <div class="stat-label">健康</div>
          </div>
          <div class="stat-item info">
            <div class="stat-value">{{ aiStats.zeroSubmit }}</div>
            <div class="stat-label">零提交</div>
          </div>
          <div class="stat-item info">
            <div class="stat-value">{{ aiStats.avgCompletion }}%</div>
            <div class="stat-label">完成率</div>
          </div>
        </div>
      </div>

      <!-- 右: AI 风险分布 -->
      <div class="risk-distrib-panel">
        <div class="panel-title">
          <div class="panel-title-icon"><el-icon :size="14"><DataLine /></el-icon></div>
          <span>AI 风险分布</span>
          <span class="ai-tag-sm">AI</span>
        </div>
        <!-- 分布条 -->
        <div class="risk-bar-wrap">
          <div class="risk-seg high" :style="{ width: riskDistribution.highPct + '%' }" v-if="riskDistribution.highPct > 0">
            {{ riskDistribution.highPct }}%
          </div>
          <div class="risk-seg med" :style="{ width: riskDistribution.medPct + '%' }" v-if="riskDistribution.medPct > 0">
            {{ riskDistribution.medPct }}%
          </div>
          <div class="risk-seg low" :style="{ width: riskDistribution.lowPct + '%' }" v-if="riskDistribution.lowPct > 0">
            {{ riskDistribution.lowPct }}%
          </div>
        </div>
        <!-- 图例 -->
        <div class="risk-legend">
          <div class="legend-item"><span class="legend-dot high"></span>高风险 <span class="legend-num">{{ aiStats.highRisk }}</span></div>
          <div class="legend-item"><span class="legend-dot med"></span>需关注 <span class="legend-num">{{ aiStats.mediumRisk }}</span></div>
          <div class="legend-item"><span class="legend-dot low"></span>健康 <span class="legend-num">{{ aiStats.healthy }}</span></div>
        </div>
        <!-- 快捷统计 -->
        <div class="quick-stats-row">
          <div class="quick-stat">
            <div class="quick-stat-val">{{ pagination.total }}</div>
            <div class="quick-stat-label">总记录</div>
          </div>
          <div class="quick-stat">
            <div class="quick-stat-val">{{ instructors.length }}</div>
            <div class="quick-stat-label">指导老师</div>
          </div>
          <div class="quick-stat">
            <div class="quick-stat-val">{{ aiStats.avgCompletion }}%</div>
            <div class="quick-stat-label">平均完成率</div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI 监控简报 -->
    <div v-if="aiNarrative || aiNarrativeLoading" class="ai-narrative-card">
      <div class="ai-narrative-inner">
        <div class="ai-narrative-icon"><el-icon :size="16" class="icon-spin"><Cpu /></el-icon></div>
        <div class="ai-narrative-body">
          <div class="ai-narrative-label">
            <span class="font-semibold text-sm text-gray-700">AI 监控简报</span>
            <span class="ai-live-dot"></span>
            <span class="text-xs text-cyan-600 font-medium">Neural Engine</span>
            <div class="ai-status-bar">
              <div class="status-wave">
                <span v-for="i in 5" :key="'w'+i" class="wave-bar" :style="{ animationDelay: i * 0.15 + 's' }"></span>
              </div>
              <span class="text-xs" :class="aiNarrativeLoading ? 'text-cyan-600' : 'text-green-600'">
                {{ aiNarrativeLoading ? '分析中' : '就绪' }}
              </span>
            </div>
          </div>
          <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="narrative-loading">
            <div class="thinking-dots"><span></span><span></span><span></span></div>
            AI 正在分析全局监控数据...
          </div>
          <div v-else class="narrative-text">
            {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="typing-cursor">|</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 筛选条件 -->
    <div class="filter-bar">
      <span class="filter-label"><el-icon :size="13"><Search /></el-icon> 筛选</span>
      <el-select v-model="filterCollege" placeholder="学院" clearable size="default" style="width: 140px;">
        <el-option v-for="c in collegeOptions" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filterMajor" placeholder="专业" clearable size="default" style="width: 140px;">
        <el-option v-for="m in majorOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-select v-model="filterClass" placeholder="班级" clearable size="default" style="width: 120px;">
        <el-option v-for="cls in classOptions" :key="cls" :label="cls" :value="cls" />
      </el-select>
      <el-select v-model="filterRisk" placeholder="AI 风险等级" clearable size="default" style="width: 130px;">
        <el-option label="高风险" value="high" />
        <el-option label="需关注" value="medium" />
        <el-option label="健康" value="low" />
      </el-select>
      <span class="filter-count">共 {{ filteredData.length }} 条记录</span>
    </div>

    <!-- 数据表格 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="filteredData" stripe @row-click="handleRowClick" :expand-row-keys="expandedRows" row-key="student.id">
        <el-table-column type="expand" width="1" class-name="hidden-expand-icon">
          <template #default="{ row }">
            <div class="p-2">
              <div class="font-semibold mb-2">提交明细</div>
              <el-table :data="row.submissions || []" size="small">
                <el-table-column prop="task_title" label="作业" min-width="160" />
                <el-table-column label="状态" width="90">
                  <template #default="{ row: sub }">
                    <el-tag v-if="sub.status === 'pending'" type="warning" size="small">待批改</el-tag>
                    <el-tag v-else-if="sub.status === 'approved'" type="success" size="small">已通过</el-tag>
                    <el-tag v-else-if="sub.status === 'rejected'" type="danger" size="small">已驳回</el-tag>
                    <el-tag v-else size="small">{{ sub.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="提交时间" width="160">
                  <template #default="{ row: sub }">
                    {{ sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="教案" width="110">
                  <template #default="{ row: sub }">
                    <el-button v-if="sub.lesson_plan_path" size="small" @click="openFile(sub.lesson_plan_path)">查看PDF</el-button>
                    <span v-else class="text-gray-400 text-xs">无</span>
                  </template>
                </el-table-column>
                <el-table-column label="AI 视频分析" width="120">
                  <template #default="{ row: sub }">
                    <el-button v-if="sub.video_path" size="small" type="primary" link @click="viewVideoAnalysis(sub, $event)">
                      <el-icon class="mr-1"><VideoCamera /></el-icon>AI 分析
                    </el-button>
                    <span v-else class="text-gray-400 text-xs">-</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="姓名" width="100" fixed>
          <template #default="{ row }">
            <div class="font-medium">{{ row.student.name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="学号" width="120" fixed>
          <template #default="{ row }">{{ row.student.user_code }}</template>
        </el-table-column>
        <!-- AI 风险评估列 -->
        <el-table-column label="AI 风险" width="110" align="center" sortable :sort-method="(a: any, b: any) => getAIRisk(a).score - getAIRisk(b).score">
          <template #header>
            <div class="flex items-center justify-center gap-1">
              <span>AI 风险</span><span class="ai-col-badge">AI</span>
            </div>
          </template>
          <template #default="{ row }">
            <div class="flex items-center justify-center gap-1.5">
              <span class="risk-dot" :style="{ backgroundColor: getAIRisk(row).color, boxShadow: `0 0 4px ${getAIRisk(row).color}` }"></span>
              <span class="text-xs font-semibold" :style="{ color: getAIRisk(row).color }">{{ getAIRisk(row).label }}</span>
            </div>
          </template>
        </el-table-column>
        <!-- AI 健康分列 -->
        <el-table-column label="AI 健康分" width="110" align="center" sortable :sort-method="(a: any, b: any) => getAIRisk(a).score - getAIRisk(b).score">
          <template #header>
            <div class="flex items-center justify-center gap-1">
              <span>健康分</span><span class="ai-col-badge">AI</span>
            </div>
          </template>
          <template #default="{ row }">
            <div>
              <span class="font-bold text-sm" :style="{ color: getAIRisk(row).color }">{{ getAIRisk(row).score }}</span>
              <div class="health-score-bar">
                <div class="health-score-fill" :style="{ width: getAIRisk(row).score + '%', background: getAIRisk(row).color }"></div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="学院" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.student.college || '-' }}</template>
        </el-table-column>
        <el-table-column label="指导老师" width="100">
          <template #default="{ row }">{{ row.instructor.name }}</template>
        </el-table-column>
        <el-table-column label="作业数" width="70" align="center">
          <template #default="{ row }">{{ row.stats.total_tasks }}</template>
        </el-table-column>
        <el-table-column label="已提交" width="70" align="center">
          <template #default="{ row }">{{ row.stats.submitted }}</template>
        </el-table-column>
        <el-table-column label="待批改" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.stats.pending > 0" type="warning" size="small">{{ row.stats.pending }}</el-tag>
            <span v-else class="text-gray-400">0</span>
          </template>
        </el-table-column>
        <el-table-column label="已通过" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.stats.approved > 0" type="success" size="small">{{ row.stats.approved }}</el-tag>
            <span v-else class="text-gray-400">0</span>
          </template>
        </el-table-column>
        <el-table-column label="完成进度" min-width="140">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.stats.total_tasks ? Math.round(row.stats.approved / row.stats.total_tasks * 100) : 0"
              :status="row.stats.approved === row.stats.total_tasks && row.stats.total_tasks > 0 ? 'success' : ''"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.page_size"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 视频 AI 分析对话框 -->
    <el-dialog v-model="videoAnalysisDialogVisible" title="视频 AI 分析报告" width="900px" top="5vh">
      <div v-if="currentAnalysisSubmission" class="mb-4">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="作业">{{ currentAnalysisSubmission.task_title }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag 
              :type="currentAnalysisSubmission.status === 'approved' ? 'success' : currentAnalysisSubmission.status === 'rejected' ? 'danger' : 'warning'" 
              size="small"
            >
              {{ currentAnalysisSubmission.status === 'approved' ? '已通过' : currentAnalysisSubmission.status === 'rejected' ? '已驳回' : '待批改' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      
      <VideoAnalysisCard
        v-if="currentAnalysisSubmissionId"
        :submission-id="currentAnalysisSubmissionId"
        :can-trigger="true"
        :can-reanalyze="true"
      />
      
      <template #footer>
        <el-button @click="videoAnalysisDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>
