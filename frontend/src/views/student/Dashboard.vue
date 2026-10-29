<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import {
  User, School, Reading, Collection, ChatDotRound, ArrowRight,
  Calendar, Clock, MagicStick, TrendCharts, Cpu, DataAnalysis,
  VideoCamera, Star, Trophy, Aim
} from '@element-plus/icons-vue'
import { aiApi } from '@/api/ai'

const router = useRouter()

const instructor = ref<any>(null)
const tasks = ref<any[]>([])
const submissions = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const loading = ref(false)
const aiSuggestions = ref<any[]>([])
const aiOverallScore = ref(0)
const aiNarrative = ref('')
const aiNarrativeLoading = ref(false)
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

const authStore = useAuthStore()
const currentUser = computed(() => authStore.user)

// 生成默认头像URL
const getAvatarUrl = (userCode: string | undefined) => {
  const seed = userCode || 'default'
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9`
}

// 获取批次列表
const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    
    // 默认选择活跃批次
    const active = res.find((s: any) => s.status === 'active')
    if (active) {
      selectedSemesterId.value = active.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
    
    if (selectedSemesterId.value) {
      await fetchData()
    }
  } catch (error) {
    console.error('获取批次列表失败:', error)
    ElMessage.error('获取批次信息失败，请刷新重试')
  }
}

const fetchData = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    // 分别获取导师和作业，避免一个失败导致全部失败
    try {
      instructor.value = await api.get(`/assignments/student/my-instructor/${selectedSemesterId.value}`)
    } catch (e) {
      // 未分配导师是正常情况，不报错
      instructor.value = null
    }
    
    try {
      tasks.value = await api.get('/tasks', { params: { semester_id: selectedSemesterId.value } })
    } catch (e) {
      tasks.value = []
    }
    
    // 获取提交记录
    try {
      submissions.value = await api.get('/submissions/my', { params: { semester_id: selectedSemesterId.value } })
    } catch (e) {
      submissions.value = []
    }

    // 获取 AI 智能建议（来自成长画像）
    try {
      const profileRes: any = await api.get('/profile/me', {
        params: { semester_id: selectedSemesterId.value }
      })
      const data = profileRes.success ? profileRes.data : profileRes
      aiSuggestions.value = data?.action_items?.slice(0, 3) || []
      aiOverallScore.value = data?.overall_score || 0

      // 获取 AI 数据叙事
      fetchAINarrative({
        submission_count: submissions.value.length,
        average_score: aiOverallScore.value,
        weak_dimensions: aiSuggestions.value.map((s: any) => s.dimension).join('、'),
        task_count: tasks.value.length,
      })
    } catch (e) {
      aiSuggestions.value = []
    }
  } finally {
    loading.value = false
  }
}

const handleSemesterChange = () => {
  fetchData()
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

const getDaysLeft = (deadline: string) => {
  const diff = new Date(deadline).getTime() - new Date().getTime()
  const days = Math.ceil(diff / (1000 * 3600 * 24))
  if (days < 0) return '已截止'
  if (days === 0) return '今天截止'
  return `剩 ${days} 天`
}

// 判断作业是否已截止
const isTaskExpired = (deadline: string) => {
  if (!deadline) return false
  return new Date(deadline).getTime() < new Date().getTime()
}

// 获取作业提交状态
const getTaskSubmissionStatus = (taskId: number) => {
  const sub: any = submissions.value.find((s: any) => s.task_id === taskId)
  return sub ? sub.status : 'not_submitted'
}

// 判断作业是否可以提交（未提交或已驳回）
const canSubmitTask = (task: any) => {
  if (isTaskExpired(task.deadline)) return false
  const status = getTaskSubmissionStatus(task.id)
  return status === 'not_submitted' || status === 'rejected'
}

// 点击作业卡片
const handleTaskClick = (task: any) => {
  if (isTaskExpired(task.deadline)) {
    ElMessage.warning('该作业已截止，无法提交')
    return
  }
  const status = getTaskSubmissionStatus(task.id)
  if (status === 'pending') {
    ElMessage.info('该作业已提交，正在等待批改')
    return
  }
  if (status === 'approved') {
    ElMessage.success('该作业已通过')
    return
  }
  router.push('/student/my-submissions?taskId=' + task.id)
}

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
      if (narrativeTimer) clearInterval(narrativeTimer)
    }
  }, 30)
}

const fetchAINarrative = async (stats: Record<string, any>) => {
  aiNarrativeLoading.value = true
  try {
    const res = await aiApi.dataNarrative({ role: 'student', stats })
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

// 时段问候
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// 统计数据
const stats = computed(() => {
  const totalTasks = tasks.value.length
  const completed = submissions.value.filter((s: any) => s.status === 'approved').length
  const pending = submissions.value.filter((s: any) => s.status === 'pending').length
  const score = aiOverallScore.value || 0
  return { totalTasks, completed, pending, score }
})

// 最近任务（取前5条）
const recentTasks = computed(() => {
  return tasks.value.slice(0, 5).map(task => {
    const sub = submissions.value.find((s: any) => s.task_id === task.id)
    return {
      ...task,
      submissionStatus: sub?.status || 'not_submitted',
      isExpired: new Date(task.deadline) < new Date()
    }
  })
})

onMounted(fetchSemesters)
onUnmounted(() => { if (narrativeTimer) clearInterval(narrativeTimer) })
</script>

<template>
  <div class="ai-hub" v-loading="loading">
    <!-- ===== Hero Banner ===== -->
    <div class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <div class="hero-top">
          <div class="hero-left">
            <el-avatar :size="52" :src="getAvatarUrl(currentUser?.user_code)" class="hero-avatar" />
            <div>
              <h1 class="hero-greeting">{{ greeting }}，{{ currentUser?.name }}</h1>
              <p class="hero-sub">今天也要加油练习试讲哦</p>
            </div>
          </div>
          <el-select v-model="selectedSemesterId" @change="handleSemesterChange" size="default" class="hero-select" placeholder="选择批次">
            <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id">
              <span class="flex items-center justify-between w-full">
                {{ s.name }}
                <el-tag v-if="s.status === 'active'" size="small" type="success" round class="ml-2">进行中</el-tag>
              </span>
            </el-option>
          </el-select>
        </div>
        <!-- Stats Pills -->
        <div class="stats-row">
          <div class="stat-pill">
            <span class="stat-icon si-purple"><el-icon><Collection /></el-icon></span>
            <span class="stat-val">{{ stats.totalTasks }}</span>
            <span class="stat-lbl">全部任务</span>
          </div>
          <div class="stat-pill">
            <span class="stat-icon si-green"><el-icon><Trophy /></el-icon></span>
            <span class="stat-val">{{ stats.completed }}</span>
            <span class="stat-lbl">已通过</span>
          </div>
          <div class="stat-pill">
            <span class="stat-icon si-amber"><el-icon><Clock /></el-icon></span>
            <span class="stat-val">{{ stats.pending }}</span>
            <span class="stat-lbl">待批改</span>
          </div>
          <div class="stat-pill">
            <span class="stat-icon si-cyan"><el-icon><Star /></el-icon></span>
            <span class="stat-val">{{ stats.score || '—' }}</span>
            <span class="stat-lbl">AI 评分</span>
          </div>
        </div>
      </div>
    </div>

    <el-alert v-if="semesters.length === 0 && !loading" type="info" :closable="false" class="mx-6 mt-4" show-icon>
      当前没有试讲批次，请联系管理员
    </el-alert>

    <!-- ===== AI Features Bento Grid ===== -->
    <div class="section">
      <div class="sec-head">
        <h2 class="sec-title"><span class="sec-dot"></span>AI 智能功能</h2>
        <p class="sec-desc">人工智能驱动的试讲能力提升工具</p>
      </div>

      <div class="bento">
        <!-- 主卡: AI 实时试讲 -->
        <div class="b-card b-hero" @click="router.push('/student/realtime-eval')">
          <div class="b-deco">
            <div class="b-circle c1"></div>
            <div class="b-circle c2"></div>
          </div>
          <div class="b-body">
            <span class="b-badge">核心功能</span>
            <div class="b-icon-wrap"><el-icon :size="40"><VideoCamera /></el-icon></div>
            <h3 class="b-title">AI 实时试讲评估</h3>
            <p class="b-desc">开启摄像头，AI 实时分析姿态、表情、语速和教态，获得即时反馈与评分</p>
            <div class="b-tags">
              <span>姿态检测</span><span>表情分析</span><span>语音转写</span><span>实时评分</span>
            </div>
            <div class="b-action">开始练习 <el-icon><ArrowRight /></el-icon></div>
          </div>
        </div>

        <!-- AI 备课助手 -->
        <div class="b-card b-md b-purple" @click="router.push('/student/ai-assistant')">
          <div class="b-body">
            <div class="b-icon-wrap"><el-icon :size="32"><MagicStick /></el-icon></div>
            <h3 class="b-title">AI 智能备课</h3>
            <p class="b-desc">AI 生成教案、模拟学生提问、教案质量检测与改进建议</p>
            <div class="b-action">开始备课 <el-icon><ArrowRight /></el-icon></div>
          </div>
        </div>

        <!-- AI 学习路径 -->
        <div class="b-card b-md b-teal" @click="router.push('/student/learning-path')">
          <div class="b-body">
            <div class="b-icon-wrap"><el-icon :size="32"><Aim /></el-icon></div>
            <h3 class="b-title">AI 学习路径</h3>
            <p class="b-desc">基于成长画像数据，AI 量身定制个性化提升计划</p>
            <div class="b-action">查看路径 <el-icon><ArrowRight /></el-icon></div>
          </div>
        </div>

        <!-- 成长画像 -->
        <div class="b-card b-sm b-orange" @click="router.push('/student/my-profile')">
          <div class="b-body">
            <div class="b-icon-wrap"><el-icon :size="24"><TrendCharts /></el-icon></div>
            <h3 class="b-stitle">成长画像</h3>
            <p class="b-sdesc">多维能力雷达图</p>
          </div>
        </div>

        <!-- 练习记录 -->
        <div class="b-card b-sm b-blue" @click="router.push('/student/practice-history')">
          <div class="b-body">
            <div class="b-icon-wrap"><el-icon :size="24"><DataAnalysis /></el-icon></div>
            <h3 class="b-stitle">练习记录</h3>
            <p class="b-sdesc">历史会话与报告</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== AI Insights + Tasks + Instructor ===== -->
    <div class="main-grid">
      <!-- Left Column: AI Insights + Tasks -->
      <div class="mg-left">
        <!-- AI 学情分析 -->
        <div class="card insight-card" v-if="aiNarrative || aiNarrativeLoading">
          <div class="card-head">
            <div class="ch-icon"><el-icon :size="18"><Cpu /></el-icon></div>
            <span class="ch-title">AI 学情分析</span>
            <span class="ai-badge"><span class="ai-dot"></span>AI 生成</span>
          </div>
          <div class="card-body">
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="text-gray-400 text-sm">AI 正在分析你的学习数据...</div>
            <div v-else class="text-gray-600 text-sm leading-relaxed">{{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="cursor-blink">|</span></div>
          </div>
        </div>

        <!-- AI 改进建议 -->
        <div class="card" v-if="aiSuggestions.length > 0">
          <div class="card-head">
            <span class="ch-dot teal"></span>
            <span class="ch-title">AI 改进建议</span>
            <span class="ai-badge"><span class="ai-dot"></span>AI</span>
          </div>
          <div class="card-body">
            <div class="sg-list">
              <div v-for="(item, idx) in aiSuggestions" :key="idx" class="sg-item">
                <div class="sg-pri" :class="'p' + item.priority">P{{ item.priority }}</div>
                <div class="sg-body">
                  <div class="sg-dim">
                    <span class="font-medium text-gray-800">{{ item.dimension }}</span>
                    <span class="sg-score" :class="item.current_score < 70 ? 'low' : 'mid'">{{ item.current_score }}分</span>
                  </div>
                  <div class="sg-text">{{ item.suggestion }}</div>
                </div>
              </div>
            </div>
            <div class="text-right mt-3">
              <el-button text type="primary" size="small" @click="router.push('/student/my-profile')">
                查看完整画像 <el-icon class="ml-1"><TrendCharts /></el-icon>
              </el-button>
            </div>
          </div>
        </div>

        <!-- 作业进度 -->
        <div class="card">
          <div class="card-head">
            <span class="ch-dot orange"></span>
            <span class="ch-title">作业进度</span>
            <el-tag size="small" round type="info" class="ml-2">{{ tasks.length }}</el-tag>
            <el-button text type="primary" size="small" class="ml-auto" @click="router.push('/student/task-board')">
              全部 <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
          <div class="card-body">
            <div v-if="recentTasks.length === 0" class="empty-state">
              <el-icon :size="28" class="text-gray-300"><Collection /></el-icon>
              <span class="text-gray-400 text-sm">暂无作业</span>
            </div>
            <div v-else class="tk-list">
              <div v-for="task in recentTasks" :key="task.id" class="tk-item" @click="handleTaskClick(task)">
                <div class="tk-info">
                  <h4 class="tk-name">{{ task.title }}</h4>
                  <div class="tk-meta">
                    <span><el-icon><Calendar /></el-icon> {{ formatDate(task.deadline) }}</span>
                    <span :class="getDaysLeft(task.deadline) === '已截止' ? 'text-gray-400' : 'text-amber-500'">{{ getDaysLeft(task.deadline) }}</span>
                  </div>
                </div>
                <el-tag v-if="task.submissionStatus === 'approved'" type="success" size="small" round>已通过</el-tag>
                <el-tag v-else-if="task.submissionStatus === 'pending'" type="warning" size="small" round>待批改</el-tag>
                <el-tag v-else-if="task.submissionStatus === 'rejected'" type="danger" size="small" round>已驳回</el-tag>
                <el-tag v-else-if="task.isExpired" type="info" size="small" round>已截止</el-tag>
                <el-tag v-else size="small" round effect="plain">待提交</el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Instructor + Profile -->
      <div class="mg-right">
        <!-- 指导老师 -->
        <div class="card mentor-card">
          <div class="card-head">
            <span class="ch-dot blue"></span>
            <span class="ch-title">指导老师</span>
          </div>
          <div class="card-body" v-if="instructor">
            <div class="mt-body">
              <el-avatar :size="56" :src="getAvatarUrl(instructor.user_code)" class="mt-avatar" />
              <h3 class="mt-name">{{ instructor.name }}</h3>
              <div class="mt-info">
                <span v-if="instructor.college">{{ instructor.college }}</span>
                <span>工号: {{ instructor.user_code }}</span>
              </div>
              <el-button type="primary" round size="default" class="mt-btn" @click="router.push('/chat')">
                <el-icon class="mr-1"><ChatDotRound /></el-icon> 联系导师
              </el-button>
            </div>
          </div>
          <div class="card-body" v-else>
            <div class="empty-state" style="padding: 24px 0;">
              <el-icon :size="28" class="text-gray-300"><User /></el-icon>
              <span class="text-gray-400 text-sm">暂未分配导师</span>
            </div>
          </div>
        </div>

        <!-- 个人信息 -->
        <div class="card">
          <div class="card-head">
            <span class="ch-dot green"></span>
            <span class="ch-title">个人信息</span>
          </div>
          <div class="card-body pf-body" v-if="currentUser">
            <div class="pf-row" v-if="currentUser.college">
              <el-icon class="text-blue-500"><School /></el-icon>
              <div><div class="pf-label">学院</div><div class="pf-val">{{ currentUser.college }}</div></div>
            </div>
            <div class="pf-row" v-if="currentUser.major">
              <el-icon class="text-green-500"><Reading /></el-icon>
              <div><div class="pf-label">专业</div><div class="pf-val">{{ currentUser.major }}</div></div>
            </div>
            <div class="pf-row" v-if="currentUser.class_name">
              <el-icon class="text-orange-500"><Collection /></el-icon>
              <div><div class="pf-label">班级</div><div class="pf-val">{{ currentUser.class_name }}</div></div>
            </div>
            <div class="pf-row" v-if="currentUser.head_teacher">
              <el-icon class="text-teal-500"><User /></el-icon>
              <div><div class="pf-label">班主任</div><div class="pf-val">{{ currentUser.head_teacher }}</div></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ==================== AI Hub Container ==================== */
.ai-hub { display: flex; flex-direction: column; gap: 0; }

/* ==================== Hero Banner ==================== */
.hero {
  position: relative; border-radius: 20px; overflow: hidden;
  margin: 0 0 20px 0; padding: 0;
  box-shadow: 0 20px 40px -15px rgba(15, 23, 42, 0.25);
}
.hero-bg {
  position: absolute; inset: 0; z-index: 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
}
.hero-bg::after {
  content: '';
  position: absolute;
  top: -40%;
  right: -10%;
  width: 450px;
  height: 450px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.3) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}
.hero-content {
  position: relative; z-index: 1; padding: 28px 32px 26px;
}
.hero-top {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 16px; margin-bottom: 24px;
}
.hero-left { display: flex; align-items: center; gap: 16px; }
.hero-avatar { border: 3px solid rgba(255,255,255,0.4); box-shadow: 0 4px 14px rgba(0,0,0,0.25); flex-shrink: 0; }
.hero-greeting {
  font-size: 24px; font-weight: 800; color: #fff; margin: 0; line-height: 1.3;
  letter-spacing: -0.5px;
}
.hero-sub { font-size: 13.5px; color: rgba(224, 231, 255, 0.8); margin: 4px 0 0; }
.hero-select { width: 200px; }
.hero-select :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.12) !important;
  border: 1px solid rgba(255,255,255,0.2) !important;
  box-shadow: none !important; border-radius: 12px !important;
  backdrop-filter: blur(8px) !important;
}
.hero-select :deep(.el-input__inner) { color: #fff !important; font-weight: 600; }
.hero-select :deep(.el-select__caret) { color: rgba(255,255,255,0.8) !important; }

/* Stats Row */
.stats-row { display: flex; gap: 14px; flex-wrap: wrap; }
.stat-pill {
  display: flex; align-items: center; gap: 12px;
  background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 16px;
  padding: 12px 18px; flex: 1; min-width: 140px; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.stat-pill:hover {
  background: rgba(255, 255, 255, 0.16);
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.25);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}
.stat-icon {
  width: 38px; height: 38px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
}
.si-purple { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }
.si-green  { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
.si-amber  { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
.si-cyan   { background: linear-gradient(135deg, #06b6d4 0%, #0284c7 100%); }
.stat-val { font-size: 22px; font-weight: 800; color: #fff; line-height: 1; letter-spacing: -0.5px; }
.stat-lbl { font-size: 11.5px; color: rgba(224, 231, 255, 0.7); font-weight: 500; }

/* ==================== Section ==================== */
.section { padding: 12px 0 0; }
.sec-head { margin-bottom: 18px; }
.sec-title {
  font-size: 18px; font-weight: 800; color: #0f172a;
  display: flex; align-items: center; gap: 10px; margin: 0;
}
.sec-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #6366f1;
  display: inline-block; animation: ai-pulse 2s infinite;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.6);
}
.sec-desc { font-size: 13px; color: #64748b; margin: 4px 0 0 18px; }

/* ==================== Bento Grid ==================== */
.bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: auto auto;
  gap: 16px;
}
.b-card {
  position: relative; border-radius: 20px; overflow: hidden;
  cursor: pointer; transition: all 0.3s cubic-bezier(.4,0,.2,1);
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.08);
}
.b-card:hover { transform: translateY(-5px); box-shadow: 0 20px 35px -5px rgba(15, 23, 42, 0.2); }

/* Hero card - spans 2 cols, 2 rows */
.b-hero {
  grid-column: span 2; grid-row: span 2;
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #1e293b 100%);
  color: #fff; min-height: 280px;
  border: 1px solid rgba(99, 102, 241, 0.3);
}
.b-hero .b-body { padding: 30px; display: flex; flex-direction: column; height: 100%; position: relative; z-index: 1; }
.b-badge {
  display: inline-flex; align-items: center; padding: 4px 12px;
  background: rgba(34, 211, 238, 0.18); border-radius: 9999px;
  font-size: 11px; font-weight: 800; color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.3);
  width: fit-content; margin-bottom: 14px; letter-spacing: 0.5px;
}
.b-icon-wrap { margin-bottom: 12px; opacity: 0.95; }
.b-title { font-size: 22px; font-weight: 800; margin: 0 0 8px; letter-spacing: -0.3px; }
.b-desc { font-size: 13.5px; opacity: 0.8; line-height: 1.6; margin: 0 0 auto; color: #e0e7ff; }
.b-tags { display: flex; flex-wrap: wrap; gap: 7px; margin: 16px 0; }
.b-tags span {
  padding: 3px 10px; border-radius: 8px; font-size: 11.5px; font-weight: 600;
  background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9);
  border: 1px solid rgba(255,255,255,0.08);
}
.b-action {
  display: flex; align-items: center; gap: 6px;
  font-size: 14px; font-weight: 700; color: #38bdf8;
  margin-top: 8px;
}
.b-deco { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.b-circle {
  position: absolute; border-radius: 50%;
  background: rgba(34,211,238,0.1); animation: float 8s ease-in-out infinite;
}
.b-circle.c1 { width: 220px; height: 220px; top: -60px; right: -40px; }
.b-circle.c2 { width: 160px; height: 160px; bottom: -40px; right: 60px; animation-delay: 3s; }

/* Medium cards */
.b-md {
  grid-column: span 2; color: #fff;
}
.b-md .b-body { padding: 24px; }
.b-md .b-title { font-size: 18px; font-weight: 800; margin: 8px 0 6px; }
.b-md .b-desc { font-size: 12.5px; opacity: 0.85; line-height: 1.5; margin: 0 0 12px; }
.b-purple { background: linear-gradient(135deg, #581c87 0%, #7c3aed 100%); border-color: rgba(168, 85, 247, 0.3); }
.b-teal   { background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%); border-color: rgba(45, 212, 191, 0.3); }

/* Small cards */
.b-sm { grid-column: span 1; color: #fff; }
.b-sm .b-body { padding: 22px 18px; text-align: center; }
.b-stitle { font-size: 15px; font-weight: 800; margin: 8px 0 2px; }
.b-sdesc { font-size: 11.5px; opacity: 0.8; margin: 0; }
.b-orange { background: linear-gradient(135deg, #c2410c 0%, #ea580c 100%); border-color: rgba(251, 146, 60, 0.3); }
.b-blue   { background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%); border-color: rgba(96, 165, 250, 0.3); }

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-10px, 15px) scale(1.05); }
}

/* ==================== Main Grid ==================== */
.main-grid {
  display: grid; grid-template-columns: 1fr;
  gap: 18px; padding-top: 24px;
}
@media (min-width: 1024px) {
  .main-grid { grid-template-columns: 7fr 3fr; }
}
.mg-left, .mg-right { display: flex; flex-direction: column; gap: 16px; }

/* ==================== Card Base ==================== */
.card {
  background: #fff; border-radius: 18px; border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05); overflow: hidden;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.card:hover {
  box-shadow: 0 10px 25px -4px rgba(15, 23, 42, 0.08);
  border-color: rgba(99, 102, 241, 0.2);
}
.card-head {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; border-bottom: 1px solid #f1f5f9;
}
.ch-icon {
  width: 32px; height: 32px; border-radius: 10px;
  background: #eef2ff;
  display: flex; align-items: center; justify-content: center;
  color: #4f46e5; flex-shrink: 0;
}
.ch-title { font-size: 14.5px; font-weight: 700; color: #1e293b; }
.ch-dot {
  width: 4px; height: 16px; border-radius: 2px; flex-shrink: 0;
}
.ch-dot.teal   { background: #0d9488; }
.ch-dot.orange { background: #f59e0b; }
.ch-dot.blue   { background: #4f46e5; }
.ch-dot.green  { background: #10b981; }
.card-body { padding: 18px 20px; }

/* AI Badge */
.ai-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 10px; background: #eef2ff; border-radius: 9999px;
  font-size: 11px; font-weight: 700; color: #4f46e5; margin-left: auto;
  border: 1px solid rgba(99, 102, 241, 0.2);
}
.ai-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #4f46e5; animation: ai-pulse 2s infinite;
}
@keyframes ai-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Insight Card */
.insight-card {
  background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%) !important;
  border-color: rgba(99, 102, 241, 0.25) !important;
}
.cursor-blink { animation: blink 1s infinite; color: #4f46e5; font-weight: bold; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

/* ==================== Suggestion List ==================== */
.sg-list { display: flex; flex-direction: column; gap: 10px; }
.sg-item {
  display: flex; gap: 12px; padding: 12px;
  background: #fafbfc; border: 1px solid #f1f5f9;
  border-radius: 10px; transition: all 0.2s;
}
.sg-item:hover { border-color: #cffafe; background: #faf5ff; }
.sg-pri {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
}
.sg-pri.p1 { background: #fee2e2; color: #dc2626; }
.sg-pri.p2 { background: #fef3c7; color: #d97706; }
.sg-pri.p3 { background: #dbeafe; color: #2563eb; }
.sg-body { flex: 1; }
.sg-dim { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.sg-score { font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 6px; }
.sg-score.low { background: #fee2e2; color: #dc2626; }
.sg-score.mid { background: #fef3c7; color: #d97706; }
.sg-text { font-size: 13px; color: #6b7280; line-height: 1.4; }

/* ==================== Task List ==================== */
.tk-list { display: flex; flex-direction: column; gap: 8px; }
.tk-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 14px; border-radius: 10px;
  background: #fafbfc; border: 1px solid #f1f5f9;
  cursor: pointer; transition: all 0.2s;
}
.tk-item:hover { border-color: #bfdbfe; background: #eff6ff; }
.tk-info { flex: 1; min-width: 0; }
.tk-name {
  font-size: 14px; font-weight: 600; color: #1e293b;
  margin: 0 0 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tk-meta {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: #94a3b8;
}
.tk-meta .el-icon { font-size: 12px; }

/* ==================== Mentor Card ==================== */
.mt-body {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; padding: 8px 0;
}
.mt-avatar { border: 3px solid #e0f2fe; margin-bottom: 12px; }
.mt-name { font-size: 18px; font-weight: 700; color: #1e293b; margin: 0 0 6px; }
.mt-info {
  display: flex; flex-wrap: wrap; gap: 8px; justify-content: center;
  font-size: 12px; color: #94a3b8; margin-bottom: 16px;
}
.mt-info span {
  padding: 2px 10px; background: #f1f5f9; border-radius: 6px;
}
.mt-btn { width: 100%; }

/* ==================== Profile Info ==================== */
.pf-body { display: flex; flex-direction: column; gap: 12px; }
.pf-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: #f8fafc; border-radius: 10px;
}
.pf-row .el-icon { font-size: 16px; flex-shrink: 0; }
.pf-label { font-size: 11px; color: #94a3b8; }
.pf-val { font-size: 13px; font-weight: 600; color: #334155; }

/* ==================== Empty State ==================== */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 32px 0;
}

/* ==================== Responsive ==================== */
@media (max-width: 768px) {
  .hero-content { padding: 20px 16px 18px; }
  .hero-greeting { font-size: 18px; }
  .stats-row { gap: 8px; }
  .stat-pill { min-width: 100px; padding: 8px 12px; }
  .stat-val { font-size: 16px; }
  .bento { grid-template-columns: 1fr 1fr; }
  .b-hero { grid-column: span 2; grid-row: span 1; min-height: 200px; }
  .b-md { grid-column: span 2; }
  .b-sm { grid-column: span 1; }
  .section { padding: 20px 0 0; }
}

@media (max-width: 480px) {
  .bento { grid-template-columns: 1fr; }
  .b-hero, .b-md, .b-sm { grid-column: span 1; }
  .hero-top { flex-direction: column; align-items: flex-start; }
  .hero-select { width: 100%; }
}
</style>
