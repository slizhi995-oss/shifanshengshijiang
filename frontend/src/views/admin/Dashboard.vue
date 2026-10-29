<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { User, Reading, Calendar, Document, TrendCharts, DataLine, ArrowRight, Notification, Setting, Files, Monitor, Cpu } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/utils/request'
import { aiApi } from '@/api/ai'

const router = useRouter()

const authStore = useAuthStore()

// AI 数据叙事
const aiNarrative = ref('')
const aiNarrativeLoading = ref(false)
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent, LegendComponent])

const stats = ref<any>({
  users: { total: 0, admin: 0, instructor: 0, student: 0 },
  semesters: { total: 0, draft: 0, active: 0, completed: 0 },
  submissions: { total: 0, pending: 0, approved: 0, rejected: 0 }
})

const loading = ref(true)
const activeSemester = ref<any>(null)

const displayStats = ref({
  instructorCount: 0,
  studentCount: 0,
  pendingCount: 0
})

const animateCount = (key: 'instructorCount' | 'studentCount' | 'pendingCount', target: number, duration = 1200) => {
  const start = displayStats.value[key]
  const diff = target - start
  if (diff === 0) { displayStats.value[key] = target; return }
  const startTime = performance.now()
  const step = (t: number) => {
    const elapsed = t - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // easeOutCubic
    displayStats.value[key] = Math.round(start + diff * eased)
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

const fetchDashboard = async () => {
  const res: any = await api.get('/admin/dashboard')
  stats.value = res
  animateCount('instructorCount', res.users?.instructor || 0)
  animateCount('studentCount', res.users?.student || 0)
  animateCount('pendingCount', res.submissions?.pending || 0)
  fetchAINarrative(res)
}

const fetchActiveSemester = async () => {
  try {
    const list: any = await api.get('/semesters')
    activeSemester.value = list.find((s: any) => s.status === 'active') || list[0] || null
  } catch {
    activeSemester.value = null
  }
}

// AI 数据叙事
const typewriterEffect = (text: string) => {
  aiNarrativeDisplayed.value = ''
  let i = 0
  if (narrativeTimer) clearInterval(narrativeTimer)
  narrativeTimer = setInterval(() => {
    if (i < text.length) {
      aiNarrativeDisplayed.value += text[i]
      i++
    } else {
      if (narrativeTimer) clearInterval(narrativeTimer)
    }
  }, 30)
}

const fetchAINarrative = async (dashData: any) => {
  aiNarrativeLoading.value = true
  try {
    const narrativeStats = {
      user_total: dashData.users?.total || 0,
      instructor_count: dashData.users?.instructor || 0,
      student_count: dashData.users?.student || 0,
      semester_total: dashData.semesters?.total || 0,
      active_semesters: dashData.semesters?.active || 0,
      submissions_total: dashData.submissions?.total || 0,
      submissions_pending: dashData.submissions?.pending || 0,
      submissions_approved: dashData.submissions?.approved || 0,
      pass_rate: dashData.submissions?.total > 0 ? Math.round((dashData.submissions.approved / dashData.submissions.total) * 100) : 0,
    }
    const res = await aiApi.dataNarrative({ role: 'admin', stats: narrativeStats })
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
  try {
    await Promise.all([fetchDashboard(), fetchActiveSemester()])
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (narrativeTimer) clearInterval(narrativeTimer)
})

const collegeName = computed(() => authStore.user?.college || '高校师范')

const semesterStatusMap: Record<string, { label: string; type: string }> = {
  active: { label: '进行中', type: 'success' },
  draft: { label: '草稿', type: 'info' },
  completed: { label: '已结束', type: 'warning' },
}

const quickNavs = [
  { title: '通知公告', desc: '发布管理通知', icon: Notification, path: '/admin/notices', color: '#3b82f6' },
  { title: '试讲设置', desc: '周期/老师/学生', icon: Setting, path: '/admin/semesters', color: '#8b5cf6' },
  { title: '试讲分配', desc: 'AI 智能匹配', icon: Cpu, path: '/admin/assignments', color: '#0891b2' },
  { title: '试讲进展', desc: '实时监控跟踪', icon: Monitor, path: '/admin/monitor', color: '#10b981' },
  { title: '试讲成绩', desc: '查看汇总成绩', icon: TrendCharts, path: '/admin/grades', color: '#f59e0b' },
  { title: '试讲材料', desc: '收集上传下载', icon: Files, path: '/admin/materials', color: '#ef4444' },
]

// 动态问候语
const greetings = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了，注意休息'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const submissionPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: '2%', left: 'center', icon: 'circle', textStyle: { fontSize: 12 } },
  color: ['#f59e0b', '#10b981', '#ef4444'],
  series: [{
    name: '提交状态',
    type: 'pie',
    radius: ['38%', '62%'],
    center: ['50%', '44%'],
    avoidLabelOverlap: false,
    label: { show: false },
    emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
    labelLine: { show: false },
    data: [
      { value: stats.value.submissions?.pending || 0, name: '待审核' },
      { value: stats.value.submissions?.approved || 0, name: '已通过' },
      { value: stats.value.submissions?.rejected || 0, name: '已退回' },
    ]
  }]
}))
</script>

<template>
  <div v-loading="loading" class="admin-dashboard">
    <!-- 欢迎头部 -->
    <div class="welcome-header mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">{{ greetings }}，{{ authStore.user?.name || '管理员' }}</h1>
          <p class="text-gray-500 mt-1 flex items-center gap-1">
            <el-icon><Reading /></el-icon>
            {{ collegeName }} · 多模态试讲赋能平台
          </p>
        </div>
        <div class="text-right text-sm text-gray-400">
          {{ new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) }}
        </div>
      </div>
    </div>

    <!-- 概要信息卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="summary-card cursor-pointer" @click="router.push('/admin/semesters')">
        <div class="card-icon bg-blue-50">
          <el-icon :size="24" color="#3b82f6"><Calendar /></el-icon>
        </div>
        <div class="card-info">
          <div class="card-label">当前试讲时段</div>
          <div class="card-value text-blue-600 text-sm leading-tight">
            {{ activeSemester ? activeSemester.name : '暂无' }}
          </div>
          <el-tag v-if="activeSemester" :type="(semesterStatusMap[activeSemester.status]?.type || 'info') as any" size="small" class="mt-1">
            {{ semesterStatusMap[activeSemester.status]?.label || activeSemester.status }}
          </el-tag>
        </div>
      </div>
      <div class="summary-card cursor-pointer" @click="router.push('/admin/instructors')">
        <div class="card-icon bg-purple-50">
          <el-icon :size="24" color="#8b5cf6"><User /></el-icon>
        </div>
        <div class="card-info">
          <div class="card-label">指导老师</div>
          <div class="card-value text-purple-600">{{ displayStats.instructorCount }}</div>
          <div class="card-sub">人</div>
        </div>
      </div>
      <div class="summary-card cursor-pointer" @click="router.push('/admin/students')">
        <div class="card-icon bg-teal-50">
          <el-icon :size="24" color="#0891b2"><Reading /></el-icon>
        </div>
        <div class="card-info">
          <div class="card-label">试讲学生</div>
          <div class="card-value text-teal-600">{{ displayStats.studentCount }}</div>
          <div class="card-sub">人</div>
        </div>
      </div>
      <div class="summary-card cursor-pointer" @click="router.push('/admin/monitor')">
        <div class="card-icon bg-amber-50">
          <el-icon :size="24" color="#f59e0b"><Document /></el-icon>
        </div>
        <div class="card-info">
          <div class="card-label">待审核提交</div>
          <div class="card-value text-amber-600">{{ displayStats.pendingCount }}</div>
          <div class="card-sub">份</div>
        </div>
      </div>
    </div>

    <!-- 详细信息区 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <!-- 当前试讲时段详情 -->
      <div class="bg-white rounded-xl shadow-sm border p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-gray-700 flex items-center gap-2">
            <el-icon color="#3b82f6"><Calendar /></el-icon>
            当前试讲时段
          </h3>
          <el-button text size="small" @click="router.push('/admin/semesters')">
            管理 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
        <div v-if="activeSemester" class="space-y-3">
          <div>
            <div class="text-xs text-gray-400 mb-1">时段名称</div>
            <div class="font-medium text-gray-800">{{ activeSemester.name }}</div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <div class="text-xs text-gray-400 mb-1">开始日期</div>
              <div class="text-sm text-gray-700">
                {{ activeSemester.start_date ? new Date(activeSemester.start_date).toLocaleDateString('zh-CN') : '—' }}
              </div>
            </div>
            <div>
              <div class="text-xs text-gray-400 mb-1">结束日期</div>
              <div class="text-sm text-gray-700">
                {{ activeSemester.end_date ? new Date(activeSemester.end_date).toLocaleDateString('zh-CN') : '—' }}
              </div>
            </div>
          </div>
          <div v-if="activeSemester.description">
            <div class="text-xs text-gray-400 mb-1">说明</div>
            <div class="text-sm text-gray-600 line-clamp-3">{{ activeSemester.description }}</div>
          </div>
          <div class="flex gap-2 pt-1">
            <el-button size="small" type="primary" @click="router.push('/admin/assignments')">试讲分配</el-button>
            <el-button size="small" @click="router.push('/admin/monitor')">查看进展</el-button>
          </div>
        </div>
        <div v-else class="text-center py-8 text-gray-400">
          <el-icon :size="32" class="mb-2"><Calendar /></el-icon>
          <div class="text-sm">暂无进行中的试讲时段</div>
          <el-button size="small" type="primary" class="mt-3" @click="router.push('/admin/semesters')">新建试讲周期</el-button>
        </div>
      </div>

      <!-- 功能导航 -->
      <div class="lg:col-span-2 bg-white rounded-xl shadow-sm border p-5">
        <h3 class="font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <el-icon color="#6366f1"><DataLine /></el-icon>
          功能导航
        </h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div
            v-for="nav in quickNavs"
            :key="nav.path"
            class="quick-nav-item cursor-pointer"
            @click="router.push(nav.path)"
          >
            <div class="quick-nav-icon" :style="{ backgroundColor: nav.color + '18' }">
              <el-icon :size="20" :style="{ color: nav.color }"><component :is="nav.icon" /></el-icon>
            </div>
            <div>
              <div class="font-medium text-gray-800 text-sm">{{ nav.title }}</div>
              <div class="text-xs text-gray-400">{{ nav.desc }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计信息区 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 提交情况统计 -->
      <div class="bg-white rounded-xl shadow-sm border p-5">
        <h3 class="font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <el-icon color="#f59e0b"><TrendCharts /></el-icon>
          提交情况统计
        </h3>
        <div class="flex items-center">
          <v-chart :option="submissionPieOption" style="height:180px;width:180px;flex-shrink:0;" autoresize />
          <div class="ml-6 space-y-3 flex-1">
            <div class="flex items-center justify-between">
              <span class="flex items-center text-sm text-gray-600 gap-2">
                <span class="w-3 h-3 rounded-full bg-amber-400 inline-block"></span>待审核
              </span>
              <span class="font-bold text-amber-600">{{ stats.submissions?.pending || 0 }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="flex items-center text-sm text-gray-600 gap-2">
                <span class="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>已通过
              </span>
              <span class="font-bold text-emerald-600">{{ stats.submissions?.approved || 0 }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="flex items-center text-sm text-gray-600 gap-2">
                <span class="w-3 h-3 rounded-full bg-red-400 inline-block"></span>已退回
              </span>
              <span class="font-bold text-red-500">{{ stats.submissions?.rejected || 0 }}</span>
            </div>
            <div class="border-t pt-2">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500">共提交</span>
                <span class="font-bold text-gray-700">{{ stats.submissions?.total || 0 }} 份</span>
              </div>
              <div class="flex items-center justify-between text-sm mt-1">
                <span class="text-gray-500">通过率</span>
                <span class="font-bold text-gray-700">
                  {{ stats.submissions?.total > 0 ? Math.round((stats.submissions.approved / stats.submissions.total) * 100) : 0 }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- AI 数据解读 -->
      <div class="bg-white rounded-xl shadow-sm p-5 border border-cyan-100" style="background: linear-gradient(135deg, #ecfeff 0%, #ffffff 55%);">
        <h3 class="font-semibold mb-3 flex items-center gap-2 text-slate-800">
          <el-icon color="#0891b2"><Cpu /></el-icon>
          AI 数据解读
          <el-tag size="small" style="background:#0891b2;border-color:#0891b2;color:white;">AI</el-tag>
        </h3>
        <div v-if="aiNarrativeLoading" class="text-slate-400 text-sm py-6 text-center">
          AI 正在分析试讲数据...
        </div>
        <div v-else-if="aiNarrativeDisplayed" class="text-slate-700 text-sm leading-relaxed">
          {{ aiNarrativeDisplayed }}
        </div>
        <div v-else class="text-slate-400 text-sm py-6 text-center">
          暂无 AI 分析数据
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-dashboard { max-width: 1440px; margin: 0 auto; }

.summary-card {
  background: white;
  border-radius: 16px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  border: 1px solid rgba(226, 232, 240, 0.85);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.summary-card:hover {
  box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.1);
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.25);
}
.card-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.card-info { min-width: 0; flex: 1; }
.card-label { font-size: 12.5px; color: #64748b; font-weight: 500; margin-bottom: 3px; }
.card-value { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.2; }
.card-sub { font-size: 12px; color: #94a3b8; display: inline-block; margin-left: 3px; }

.quick-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  background: #f8fafc;
  transition: all 0.22s ease;
}
.quick-nav-item:hover {
  border-color: #c7d2fe;
  background: #ffffff;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.08);
}
.quick-nav-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
</style>
