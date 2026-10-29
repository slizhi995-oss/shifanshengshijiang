<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/utils/request'
import { aiApi } from '@/api/ai'
import { Cpu, DataLine, Warning, TrendCharts, Right, Aim, User as UserIcon, VideoCamera, Star, Trophy, Refresh } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()

const students = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const loading = ref(false)

// AI 统计数据
const dashStats = ref<any>(null)
const classInsights = ref<any>(null)
const statsLoading = ref(false)
const insightsLoading = ref(false)

// 搜索和筛选
const keyword = ref('')
const filterCollege = ref('')
const filterMajor = ref('')
const filterClass = ref('')

// AI 数据叙事
const aiNarrative = ref('')
const aiNarrativeLoading = ref(false)
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 动态问候
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了，注意休息'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// 筛选选项
const colleges = computed(() => {
  const set = new Set(students.value.map(s => s.college).filter(Boolean))
  return Array.from(set).sort()
})

const majors = computed(() => {
  const set = new Set(students.value.map(s => s.major).filter(Boolean))
  return Array.from(set).sort()
})

const classes = computed(() => {
  const set = new Set(students.value.map(s => s.class_name).filter(Boolean))
  return Array.from(set).sort()
})

const filteredStudents = computed(() => {
  return students.value.filter((s) => {
    if (keyword.value.trim()) {
      const k = keyword.value.trim().toLowerCase()
      const match = s.name?.toLowerCase().includes(k) ||
                   s.user_code?.toLowerCase().includes(k) ||
                   s.college?.toLowerCase().includes(k) ||
                   s.major?.toLowerCase().includes(k) ||
                   s.class_name?.toLowerCase().includes(k)
      if (!match) return false
    }
    if (filterCollege.value && s.college !== filterCollege.value) return false
    if (filterMajor.value && s.major !== filterMajor.value) return false
    if (filterClass.value && s.class_name !== filterClass.value) return false
    return true
  })
})

const pagedStudents = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredStudents.value.slice(start, start + pageSize.value)
})

// AI 速览卡片数据
const pendingCount = computed(() => dashStats.value?.grading?.pending ?? 0)
const avgScore = computed(() => dashStats.value?.scores?.average ?? 0)
const needsAttentionCount = computed(() => {
  const tiers = classInsights.value?.student_tiers
  return tiers?.needs_attention?.count ?? 0
})
const excellentCount = computed(() => {
  const tiers = classInsights.value?.student_tiers
  return tiers?.excellent?.count ?? 0
})
const aiInsightSummary = computed(() => {
  const insights = classInsights.value?.ai_insights
  return insights?.summary || '暂无 AI 洞察数据'
})

// 模拟 AI 评分（从 class_insights 中的 submission_stats 获取）
const studentAIScores = computed(() => {
  const stats = classInsights.value?.submission_stats || {}
  const map: Record<number, { avgScore: number; count: number }> = {}
  for (const [sid, val] of Object.entries(stats)) {
    const v = val as any
    map[Number(sid)] = { avgScore: v.avg_score || 0, count: v.count || 0 }
  }
  return map
})

// AI 风险等级
const getAIRisk = (studentId: number): { level: string; color: string; label: string } => {
  const tiers = classInsights.value?.student_tiers
  if (!tiers) return { level: 'unknown', color: '#9ca3af', label: '未知' }
  
  if (tiers.excellent?.students?.some((s: any) => s.id === studentId)) {
    return { level: 'low', color: '#10b981', label: '优秀' }
  }
  if (tiers.good?.students?.some((s: any) => s.id === studentId)) {
    return { level: 'medium', color: '#f59e0b', label: '良好' }
  }
  if (tiers.needs_attention?.students?.some((s: any) => s.id === studentId)) {
    return { level: 'high', color: '#ef4444', label: '需关注' }
  }
  return { level: 'none', color: '#d1d5db', label: '暂无' }
}

// 获取批次列表
const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    
    const active = res.find((s: any) => s.status === 'active')
    if (active) {
      selectedSemesterId.value = active.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
  } catch (error) {}
}

// 获取学生列表
const fetchStudents = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const res: any = await api.get(`/assignments/instructor/${selectedSemesterId.value}`)
    students.value = res || []
    currentPage.value = 1
  } catch (error) {
    students.value = []
  } finally {
    loading.value = false
  }
}

// 获取仪表盘统计
const fetchDashStats = async () => {
  if (!selectedSemesterId.value) return
  statsLoading.value = true
  try {
    const res: any = await api.get('/statistics/instructor/dashboard', {
      params: { semester_id: selectedSemesterId.value }
    })
    dashStats.value = res?.data || null
  } catch {
    dashStats.value = null
  } finally {
    statsLoading.value = false
  }
}

// 获取 AI 班级洞察
const fetchClassInsights = async () => {
  if (!selectedSemesterId.value) return
  insightsLoading.value = true
  try {
    const res: any = await api.get('/instructor/class-insights', {
      params: { semester_id: selectedSemesterId.value }
    })
    classInsights.value = res?.data || null
  } catch {
    classInsights.value = null
  } finally {
    insightsLoading.value = false
  }
}

// 加载所有数据
const loadAllData = async () => {
  await fetchStudents()
  fetchDashStats()
  fetchClassInsights().then(() => fetchAINarrative())
}

// 切换批次
const handleSemesterChange = () => {
  loadAllData()
}

// 清空筛选
const clearFilters = () => {
  keyword.value = ''
  filterCollege.value = ''
  filterMajor.value = ''
  filterClass.value = ''
  currentPage.value = 1
}

const handleExport = () => {
  const csvContent = [
    ['学号', '姓名', '学院', '专业', '班级', '班主任'],
    ...filteredStudents.value.map(s => [
      s.user_code,
      s.name,
      s.college,
      s.major,
      s.class_name,
      s.head_teacher
    ])
  ].map(row => row.join(',')).join('\n')

  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '学生列表.csv'
  link.click()
}

// 快捷操作
const goToReviews = () => router.push('/instructor/reviews')
const goToClassInsights = () => router.push('/instructor/class-insights')
const goToStudentProfiles = () => router.push('/instructor/student-profiles')

// AI 数据叙事 - 打字机效果
const typewriterEffect = (text: string) => {
  aiNarrativeDisplayed.value = ''
  let i = 0
  if (narrativeTimer) clearInterval(narrativeTimer)
  narrativeTimer = setInterval(() => {
    if (i < text.length) {
      aiNarrativeDisplayed.value += text[i]
      i++
    } else {
      clearInterval(narrativeTimer!)
    }
  }, 30)
}

const fetchAINarrative = async () => {
  aiNarrativeLoading.value = true
  try {
    const narrativeStats: Record<string, any> = {
      student_count: students.value.length,
      pending_count: pendingCount.value,
      average_score: avgScore.value,
      needs_attention_count: needsAttentionCount.value,
      insight_summary: aiInsightSummary.value,
    }
    const res = await aiApi.dataNarrative({ role: 'instructor', stats: narrativeStats })
    if (res.success && res.data?.narrative) {
      aiNarrative.value = res.data.narrative
      typewriterEffect(res.data.narrative)
    }
  } catch {
    aiNarrative.value = ''
  } finally {
    aiNarrativeLoading.value = false
  }
}

onMounted(async () => {
  await fetchSemesters()
  if (selectedSemesterId.value) {
    loadAllData()
  }
})

onUnmounted(() => {
  if (narrativeTimer) clearInterval(narrativeTimer)
})
</script>

<template>
  <div v-loading="loading" class="instructor-dashboard">
    <!-- Hero Banner -->
    <div class="hero-banner">
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="hero-title">{{ greeting }}，{{ authStore.user?.name || '老师' }}</h1>
          <p class="hero-desc">AI 教学助手为你智能分析班级数据，让教学更高效</p>
        </div>
        <div class="hero-actions">
          <el-select
            v-model="selectedSemesterId"
            placeholder="选择批次"
            @change="handleSemesterChange"
            class="hero-select"
          >
            <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id">
              <span>{{ s.name }}</span>
              <el-tag v-if="s.status === 'active'" size="small" type="success" class="ml-2">进行中</el-tag>
            </el-option>
          </el-select>
        </div>
      </div>
      <div class="hero-decoration"></div>
    </div>

    <el-alert v-if="semesters.length === 0" type="info" :closable="false" class="mb-6">
      当前没有试讲批次
    </el-alert>

    <template v-else-if="selectedSemesterId">
      <!-- AI 统计卡片 -->
      <div class="stats-grid">
        <div class="stat-card" @click="goToReviews">
          <div class="stat-icon blue"><el-icon :size="22"><Aim /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ pendingCount }}</div>
            <div class="stat-label">待 AI 批改</div>
          </div>
          <div class="stat-badge">AI</div>
        </div>
        <div class="stat-card" @click="goToStudentProfiles">
          <div class="stat-icon green"><el-icon :size="22"><Trophy /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ excellentCount }}</div>
            <div class="stat-label">AI 优秀学生</div>
          </div>
          <div class="stat-badge">AI</div>
        </div>
        <div class="stat-card" @click="goToStudentProfiles">
          <div class="stat-icon red"><el-icon :size="22"><Warning /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ needsAttentionCount }}</div>
            <div class="stat-label">AI 需关注</div>
          </div>
          <div class="stat-badge">AI</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon teal"><el-icon :size="22"><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ avgScore || '-' }}</div>
            <div class="stat-label">AI 平均评分</div>
          </div>
          <div class="stat-badge">AI</div>
        </div>
      </div>

      <!-- AI 功能 Bento Grid -->
      <div class="bento-grid">
        <!-- AI 智能批改 - 大卡片 -->
        <div class="bento-card bento-primary" @click="goToReviews">
          <div class="bento-glow"></div>
          <div class="bento-header">
            <div class="bento-icon-wrap primary"><el-icon :size="24"><Aim /></el-icon></div>
            <el-tag effect="dark" size="small" round class="bento-tag">核心功能</el-tag>
          </div>
          <h3 class="bento-title">AI 智能批改</h3>
          <p class="bento-desc">AI 自动分析教案+视频，多维度评分并生成个性化反馈建议</p>
          <div class="bento-footer">
            <span v-if="pendingCount > 0" class="bento-stat">{{ pendingCount }} 份待批改</span>
            <span v-else class="bento-stat">暂无待批改</span>
            <el-icon class="bento-arrow"><Right /></el-icon>
          </div>
        </div>

        <!-- AI 班级洞察 -->
        <div class="bento-card bento-purple" @click="goToClassInsights">
          <div class="bento-header">
            <div class="bento-icon-wrap purple"><el-icon :size="20"><Cpu /></el-icon></div>
            <el-tag effect="plain" size="small" round type="primary">AI</el-tag>
          </div>
          <h3 class="bento-title">AI 班级洞察</h3>
          <p class="bento-desc">智能分析班级整体表现，发现共性问题与教学改进方向</p>
          <div class="bento-footer">
            <span class="bento-stat">{{ students.length }} 名学生</span>
            <el-icon class="bento-arrow"><Right /></el-icon>
          </div>
        </div>

        <!-- AI 学生画像 -->
        <div class="bento-card bento-green" @click="goToStudentProfiles">
          <div class="bento-header">
            <div class="bento-icon-wrap green"><el-icon :size="20"><UserIcon /></el-icon></div>
            <el-tag effect="plain" size="small" round type="success">AI</el-tag>
          </div>
          <h3 class="bento-title">AI 学生画像</h3>
          <p class="bento-desc">AI 生成每位学生的能力雷达图、成长趋势与个性化建议</p>
          <div class="bento-footer">
            <span class="bento-stat">能力分析</span>
            <el-icon class="bento-arrow"><Right /></el-icon>
          </div>
        </div>

        <!-- AI 教学叙事 - 宽卡片 -->
        <div class="bento-card bento-narrative">
          <div class="bento-header">
            <div class="bento-icon-wrap cyan"><el-icon :size="20"><DataLine /></el-icon></div>
            <div class="flex items-center gap-2">
              <span class="font-semibold text-sm text-gray-700">AI 教学简报</span>
              <span class="ai-live-dot"></span>
              <span class="text-xs text-cyan-600 font-medium">AI 生成</span>
            </div>
          </div>
          <div class="narrative-content">
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="narrative-loading">
              AI 正在分析班级教学数据...
            </div>
            <div v-else-if="aiNarrativeDisplayed" class="narrative-text">
              {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="typing-cursor">|</span>
            </div>
            <div v-else class="narrative-loading">暂无数据，请等待 AI 分析</div>
          </div>
        </div>
      </div>

      <!-- 学生管理区域 -->
      <div class="section-header">
        <div>
          <h2 class="section-title">我的学生</h2>
          <p class="section-desc">AI 智能评估每位学生的学习状态</p>
        </div>
        <div class="flex items-center gap-3">
          <el-tag effect="plain">共 {{ filteredStudents.length }} 人</el-tag>
          <el-button type="primary" @click="handleExport" :disabled="filteredStudents.length === 0" size="small">导出CSV</el-button>
        </div>
      </div>

      <el-card shadow="never" class="student-table-card">
        <!-- 筛选器 -->
        <div class="mb-4 flex items-center gap-3 flex-wrap">
          <el-input v-model="keyword" placeholder="搜索姓名/学号" clearable style="width: 180px" />
          <el-select v-model="filterCollege" placeholder="学院" clearable style="width: 140px">
            <el-option v-for="college in colleges" :key="college" :label="college" :value="college" />
          </el-select>
          <el-select v-model="filterMajor" placeholder="专业" clearable style="width: 140px">
            <el-option v-for="major in majors" :key="major" :label="major" :value="major" />
          </el-select>
          <el-select v-model="filterClass" placeholder="班级" clearable style="width: 140px">
            <el-option v-for="cls in classes" :key="cls" :label="cls" :value="cls" />
          </el-select>
          <el-button @click="clearFilters" size="small">清空筛选</el-button>
        </div>

        <el-table :data="pagedStudents" stripe>
          <el-table-column prop="user_code" label="学号" width="130" />
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="college" label="学院" min-width="120" />
          <el-table-column prop="major" label="专业" min-width="120" />
          <el-table-column prop="class_name" label="班级" min-width="100" />
          <el-table-column label="AI 评分" width="110" align="center">
            <template #header>
              <div class="flex items-center justify-center gap-1">
                <span>AI 评分</span><span class="ai-col-badge">AI</span>
              </div>
            </template>
            <template #default="{ row }">
              <template v-if="studentAIScores[row.id]">
                <span class="font-semibold" :class="{
                  'text-green-600': studentAIScores[row.id].avgScore >= 80,
                  'text-yellow-600': studentAIScores[row.id].avgScore >= 60 && studentAIScores[row.id].avgScore < 80,
                  'text-red-600': studentAIScores[row.id].avgScore > 0 && studentAIScores[row.id].avgScore < 60,
                  'text-gray-400': !studentAIScores[row.id].avgScore
                }">{{ studentAIScores[row.id].avgScore || '-' }}</span>
              </template>
              <span v-else class="text-gray-300">-</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 风险" width="110" align="center">
            <template #header>
              <div class="flex items-center justify-center gap-1">
                <span>AI 风险</span><span class="ai-col-badge">AI</span>
              </div>
            </template>
            <template #default="{ row }">
              <div class="flex items-center justify-center gap-1.5">
                <span class="risk-dot" :style="{ backgroundColor: getAIRisk(row.id).color }"></span>
                <span class="text-xs" :style="{ color: getAIRisk(row.id).color }">{{ getAIRisk(row.id).label }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="$router.push(`/instructor/reviews?student_id=${row.id}`)">查看作业</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="flex justify-end mt-4">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            :total="filteredStudents.length"
          />
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.instructor-dashboard {
  padding: 0;
}

/* Hero Banner */
.hero-banner {
  position: relative;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0369a1 100%);
  border-radius: 20px;
  padding: 32px 36px;
  margin-bottom: 24px;
  overflow: hidden;
  color: white;
  box-shadow: 0 20px 40px -15px rgba(3, 105, 161, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.hero-content {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hero-title {
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.hero-desc {
  font-size: 14.5px;
  opacity: 0.88;
}

.hero-select {
  width: 200px;
}

.hero-select :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.25);
  box-shadow: none;
  color: white;
  border-radius: 12px;
  backdrop-filter: blur(8px);
}

.hero-select :deep(.el-input__inner) {
  color: white;
  font-weight: 600;
}

.hero-select :deep(.el-input__inner::placeholder) {
  color: rgba(255,255,255,0.7);
}

.hero-decoration {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.25) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

@media (max-width: 1024px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) { .stats-grid { grid-template-columns: 1fr; } }

.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  background: white;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.85);
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.1);
  border-color: rgba(99, 102, 241, 0.25);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.25s;
}

.stat-icon.blue { background: #eff6ff; color: #2563eb; }
.stat-icon.green { background: #ecfdf5; color: #059669; }
.stat-icon.red { background: #fef2f2; color: #ef4444; }
.stat-icon.teal { background: #eef2ff; color: #4f46e5; }

.stat-card:hover .stat-icon.blue { background: #2563eb; color: white; }
.stat-card:hover .stat-icon.green { background: #059669; color: white; }
.stat-card:hover .stat-icon.red { background: #ef4444; color: white; }
.stat-card:hover .stat-icon.teal { background: #4f46e5; color: white; }

.stat-value {
  font-size: 26px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.stat-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 1px 6px;
  font-size: 9px;
  font-weight: 700;
  color: white;
  background: #0891b2;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

/* Bento Grid */
.bento-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 16px;
  margin-bottom: 28px;
}

.bento-card {
  background: white;
  border-radius: 18px;
  padding: 22px 24px;
  border: 1px solid #f1f5f9;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 30px rgba(0,0,0,0.1);
  border-color: transparent;
}

.bento-primary {
  grid-row: span 1;
  background: #1e3a8a;
  color: white;
  border: none;
}

.bento-narrative {
  grid-column: span 3;
  cursor: default;
  background: #f0f9ff;
  border-color: #bae6fd;
}

.bento-narrative:hover {
  transform: none;
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.08);
}

.bento-glow {
  position: absolute;
  top: -50%;
  right: -30%;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.3) 0%, transparent 70%);
  pointer-events: none;
}

.bento-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.bento-icon-wrap {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bento-icon-wrap.primary { background: rgba(255,255,255,0.15); color: white; }
.bento-icon-wrap.purple { background: #ede9fe; color: #7c3aed; }
.bento-icon-wrap.green { background: #ecfdf5; color: #059669; }
.bento-icon-wrap.cyan { background: #cffafe; color: #0891b2; }

.bento-tag {
  background: rgba(255,255,255,0.2) !important;
  border: none !important;
}

.bento-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 8px;
}

.bento-primary .bento-title { color: white; }

.bento-desc {
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 16px;
}

.bento-primary .bento-desc { color: rgba(255,255,255,0.7); }
.bento-purple .bento-desc,
.bento-green .bento-desc { color: #64748b; }

.bento-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bento-stat {
  font-size: 12px;
  font-weight: 600;
}

.bento-primary .bento-stat { color: rgba(255,255,255,0.6); }
.bento-purple .bento-stat,
.bento-green .bento-stat { color: #94a3b8; }

.bento-arrow {
  transition: transform 0.2s;
}

.bento-card:hover .bento-arrow {
  transform: translateX(4px);
}

.bento-primary .bento-arrow { color: rgba(255,255,255,0.5); }

/* AI Narrative */
.narrative-content {
  margin-top: 10px;
}

.narrative-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.8;
}

.narrative-loading {
  font-size: 13px;
  color: #94a3b8;
  animation: pulse 1.5s infinite;
}

.ai-live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0891b2;
  animation: ai-blink 2s infinite;
}

@keyframes ai-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.typing-cursor {
  animation: cursor-blink 1s infinite;
  color: #0891b2;
  font-weight: bold;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Section Header */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
}

.section-desc {
  font-size: 13px;
  color: #94a3b8;
  margin-top: 4px;
}

/* Student Table Card */
.student-table-card {
  border-radius: 16px !important;
  border-color: #f1f5f9 !important;
}

/* AI Column Badge */
.ai-col-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  font-size: 9px;
  font-weight: 700;
  color: #fff;
  background: #0891b2;
  border-radius: 3px;
  line-height: 14px;
  letter-spacing: 0.5px;
}

/* Risk Dot */
.risk-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 4px currentColor;
}

/* Responsive */
@media (max-width: 1024px) {
  .bento-grid {
    grid-template-columns: 1fr 1fr;
  }
  .bento-narrative {
    grid-column: span 2;
  }
  .hero-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
}

@media (max-width: 640px) {
  .bento-grid {
    grid-template-columns: 1fr;
  }
  .bento-narrative {
    grid-column: span 1;
  }
  .hero-banner {
    padding: 24px;
  }
  .hero-title {
    font-size: 22px;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
