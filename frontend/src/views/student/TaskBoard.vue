<script setup lang="ts">
/**
 * 任务看板页面
 * 综合展示任务日历、进度统计、待办事项
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import TaskCalendar from '@/components/TaskCalendar.vue'
import { 
  Files, Clock, Check, Warning, TrendCharts,
  ArrowRight, Document, VideoCamera, Cpu, MagicStick
} from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const tasks = ref<any[]>([])
const submissions = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)

// AI 推荐相关
const profileData = ref<any>(null)
const aiLoading = ref(false)

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
    if (selectedSemesterId.value) {
      fetchData()
      fetchProfile()
    }
  } catch (error) {
    ElMessage.error('获取批次失败')
  }
}

// 获取任务和提交数据
const fetchData = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const [tasksRes, submissionsRes]: any = await Promise.all([
      api.get('/tasks', { params: { semester_id: selectedSemesterId.value } }),
      api.get('/submissions/my', { params: { semester_id: selectedSemesterId.value } })
    ])
    
    // tasks 接口返回数组，submissions 返回数组或分页对象
    tasks.value = Array.isArray(tasksRes) ? tasksRes : (tasksRes?.items || tasksRes || [])
    submissions.value = Array.isArray(submissionsRes) ? submissionsRes : (submissionsRes?.items || submissionsRes || [])
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// 统计数据
const stats = computed(() => {
  const now = new Date()
  let total = tasks.value.length
  let completed = 0
  let pending = 0
  let overdue = 0
  let upcoming = 0
  
  tasks.value.forEach(task => {
    const submission = submissions.value.find(s => s.task_id === task.id)
    const deadline = new Date(task.deadline)
    
    if (submission?.status === 'approved') {
      completed++
    } else if (!submission && deadline < now) {
      overdue++
    } else if (!submission) {
      pending++
      // 7天内截止的任务
      if (deadline.getTime() - now.getTime() < 7 * 24 * 3600 * 1000) {
        upcoming++
      }
    } else {
      pending++
    }
  })
  
  const progress = total > 0 ? Math.round((completed / total) * 100) : 100
  
  return { total, completed, pending, overdue, upcoming, progress }
})

// 待办任务（按截止日期排序）
const todoTasks = computed(() => {
  const now = new Date()
  return tasks.value
    .filter(task => {
      const submission = submissions.value.find(s => s.task_id === task.id)
      return !submission || submission.status === 'rejected'
    })
    .sort((a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime())
    .slice(0, 5)
})

type TaskStatusTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

// 获取任务状态
const getTaskStatus = (task: any): { type: TaskStatusTagType; text: string } => {
  const submission = submissions.value.find(s => s.task_id === task.id)
  const deadline = new Date(task.deadline)
  const now = new Date()
  
  if (submission?.status === 'approved') {
    return { type: 'success', text: '已通过' }
  }
  if (submission?.status === 'rejected') {
    return { type: 'danger', text: '被驳回' }
  }
  if (submission) {
    return { type: 'primary', text: '已提交' }
  }
  if (deadline < now) {
    return { type: 'danger', text: '已逾期' }
  }
  
  const daysLeft = Math.ceil((deadline.getTime() - now.getTime()) / (24 * 3600 * 1000))
  if (daysLeft <= 3) {
    return { type: 'warning', text: `${daysLeft}天后截止` }
  }
  return { type: 'info', text: `${daysLeft}天后截止` }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

// 跳转到任务详情
const goToTask = (task: any) => {
  router.push({ path: '/student/tasks', query: { task_id: task.id } })
}

// 获取 AI 画像数据用于推荐
const fetchProfile = async () => {
  if (!selectedSemesterId.value) return
  aiLoading.value = true
  try {
    const res: any = await api.get('/profile/me', {
      params: { semester_id: selectedSemesterId.value }
    })
    profileData.value = res.success ? res.data : res
  } catch {
    profileData.value = null
  } finally {
    aiLoading.value = false
  }
}

// AI 弱项分析
const weakDimension = computed(() => {
  if (!profileData.value?.radar?.length) return null
  const sorted = [...profileData.value.radar].sort((a: any, b: any) => (a.value ?? a.score ?? 0) - (b.value ?? b.score ?? 0))
  return sorted[0] || null
})

// AI 推荐信息
const aiRecommendation = computed(() => {
  if (!weakDimension.value) return null
  const dim = weakDimension.value
  const score = dim.value ?? dim.score ?? 0
  const label = dim.label || dim.name || '未知维度'
  
  // 根据弱项匹配待完成任务
  const pendingTasks = todoTasks.value
  const suggestedTask = pendingTasks.length > 0 ? pendingTasks[0] : null
  
  return {
    dimension: label,
    score: Math.round(score),
    taskTitle: suggestedTask?.title || null,
    taskId: suggestedTask?.id || null,
    overallScore: profileData.value?.overall_score ? Math.round(profileData.value.overall_score) : null,
    totalSubmissions: profileData.value?.stats?.total_submissions || 0
  }
})

// 判断任务是否匹配 AI 推荐（弱项相关任务优先）
const isAIRecommended = (task: any) => {
  if (!weakDimension.value) return false
  const submission = submissions.value.find(s => s.task_id === task.id)
  if (submission?.status === 'approved') return false
  // 对未完成的任务，第一个为最推荐
  const idx = todoTasks.value.findIndex(t => t.id === task.id)
  return idx === 0
}

// 获取任务 AI 难度标识
const getAITag = (task: any) => {
  if (!profileData.value) return null
  const submission = submissions.value.find(s => s.task_id === task.id)
  if (submission?.status === 'approved') return null
  
  const idx = todoTasks.value.findIndex(t => t.id === task.id)
  if (idx === 0) return { text: 'AI 建议优先', type: 'warning' as const }
  if (idx >= 0 && idx < 3) return { text: 'AI 推荐', type: 'primary' as const }
  return null
}

const handleSemesterChange = () => {
  fetchData()
  fetchProfile()
}

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading" class="task-board-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="tb-page-title">
            <span class="w-2.5 h-6 rounded-full bg-gradient-to-b from-indigo-500 to-cyan-500 inline-block mr-1"></span>
            任务看板
          </h2>
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-200/60 flex items-center gap-1">
            <el-icon :size="12"><Cpu /></el-icon>
            AI 智能排期
          </span>
        </div>
        <p class="tb-page-desc">实时查看实训作业全景进度、AI 推荐弱项补强与截止时间</p>
      </div>
      <el-select
        v-model="selectedSemesterId"
        placeholder="选择批次"
        @change="handleSemesterChange"
        class="w-52"
      >
        <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id">
          <span>{{ s.name }}</span>
          <el-tag v-if="s.status === 'active'" size="small" type="success" class="ml-2">进行中</el-tag>
        </el-option>
      </el-select>
    </div>

    <!-- AI 今日推荐卡片 -->
    <div v-if="aiRecommendation" class="ai-recommend-card" v-loading="aiLoading">
      <div class="ai-recommend-icon">
        <el-icon :size="26"><Cpu /></el-icon>
        <div class="ai-pulse-ring" />
      </div>
      <div class="ai-recommend-content">
        <div class="ai-recommend-title">
          <span class="ai-recommend-pill">AI 智能洞察</span>
          <span>今日攻坚建议</span>
        </div>
        <p class="ai-recommend-text">
          经诊断检测，你的 <strong>{{ aiRecommendation.dimension }}</strong> 维度当前得分为
          <span class="ai-score-tag">{{ aiRecommendation.score }}分</span>，
          <template v-if="aiRecommendation.taskTitle">
            推荐优先完成「<strong>{{ aiRecommendation.taskTitle }}</strong>」进行针对性专项突破。
          </template>
          <template v-else>
            建议多加进行该维度的语音教态微格练习。
          </template>
        </p>
        <div class="ai-recommend-meta">
          <span v-if="aiRecommendation.overallScore">
            当前画像综合评分 <strong class="text-indigo-600">{{ aiRecommendation.overallScore }}</strong> 分
          </span>
          <span v-if="aiRecommendation.totalSubmissions > 0">
            累计已试讲提交 <strong>{{ aiRecommendation.totalSubmissions }}</strong> 次
          </span>
        </div>
      </div>
      <el-button 
        v-if="aiRecommendation.taskId"
        type="primary" 
        round 
        class="!bg-gradient-to-r !from-indigo-600 !to-cyan-500 !border-none !shadow-md !shadow-indigo-500/25 hover:!opacity-95"
        @click="goToTask({ id: aiRecommendation.taskId })"
      >
        立即冲关 <el-icon class="ml-1"><ArrowRight /></el-icon>
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon stat-icon-indigo">
          <el-icon :size="24"><Files /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value text-slate-800">{{ stats.total }}</div>
          <div class="stat-label">总任务数</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon stat-icon-emerald">
          <el-icon :size="24"><Check /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value text-emerald-600">{{ stats.completed }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon stat-icon-amber">
          <el-icon :size="24"><Clock /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value text-amber-600">{{ stats.pending }}</div>
          <div class="stat-label">进行中</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon stat-icon-rose">
          <el-icon :size="24"><Warning /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value text-rose-600">{{ stats.overdue }}</div>
          <div class="stat-label">已逾期</div>
        </div>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-card">
      <div class="progress-header">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <el-icon :size="18"><TrendCharts /></el-icon>
          </div>
          <div>
            <span class="font-bold text-slate-800 text-sm">学期试讲完成率</span>
            <p class="text-xs text-slate-400 m-0">紧跟教学进度，按时交付作业</p>
          </div>
        </div>
        <div class="flex items-baseline gap-1">
          <span class="text-2xl font-black text-indigo-600 font-mono">{{ stats.progress }}</span>
          <span class="text-xs font-bold text-indigo-400">%</span>
        </div>
      </div>
      <div class="my-2">
        <el-progress 
          :percentage="stats.progress" 
          :stroke-width="10" 
          :show-text="false"
          color="#6366f1"
        />
      </div>
      <div class="progress-footer">
        <span v-if="stats.total === 0" class="text-xs text-slate-400">暂无任务，请等待教师发布</span>
        <template v-else>
          <span class="text-xs font-medium text-slate-500">{{ stats.completed }} / {{ stats.total }} 个任务已顺利通过</span>
          <span v-if="stats.upcoming > 0" class="text-xs font-semibold text-amber-600 flex items-center gap-1 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200/50">
            <el-icon><Warning /></el-icon>
            {{ stats.upcoming }} 个任务即将于 7 天内截止
          </span>
        </template>
      </div>
    </div>

    <!-- 主体内容 -->
    <div class="main-grid">
      <!-- 任务日历 -->
      <div class="calendar-section">
        <TaskCalendar :semester-id="selectedSemesterId" />
      </div>

      <!-- 待办任务列表 -->
      <div class="todo-section">
        <el-card class="todo-card" shadow="never">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-bold text-gray-800">待完成任务</span>
              <el-button text type="primary" @click="$router.push('/student/tasks')">
                查看全部 <el-icon class="ml-1"><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>

          <el-empty v-if="todoTasks.length === 0" description="太棒了！没有待完成的任务" :image-size="80" />

          <div v-else class="todo-list">
            <div 
              v-for="task in todoTasks" 
              :key="task.id"
              class="todo-item"
              @click="goToTask(task)"
            >
              <div class="todo-icon">
                <el-icon class="text-red-500" v-if="task.lesson_plan_required"><Document /></el-icon>
                <el-icon class="text-blue-500" v-if="task.video_required"><VideoCamera /></el-icon>
              </div>
              <div class="todo-content">
                <h4 class="todo-title">
                  {{ task.title }}
                  <el-tag 
                    v-if="getAITag(task)" 
                    :type="getAITag(task)!.type" 
                    size="small" 
                    effect="dark"
                    class="ml-2 ai-task-tag"
                    round
                  >
                    <el-icon class="mr-0.5" :size="10"><Cpu /></el-icon>
                    {{ getAITag(task)!.text }}
                  </el-tag>
                </h4>
                <p class="todo-date">截止: {{ formatDate(task.deadline) }}</p>
              </div>
              <el-tag :type="getTaskStatus(task).type" size="small" effect="plain">
                {{ getTaskStatus(task).text }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-board-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 1440px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.tb-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.5px;
  margin: 0;
  display: flex;
  align-items: center;
}

.tb-page-desc {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.25rem;
}

@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

.stat-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.09);
  border-color: rgba(99, 102, 241, 0.25);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
}

.stat-icon-indigo {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
}

.stat-icon-emerald {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
}

.stat-icon-amber {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
}

.stat-icon-rose {
  background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%);
  box-shadow: 0 4px 14px rgba(244, 63, 94, 0.35);
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.5px;
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
}

.stat-label {
  font-size: 12.5px;
  font-weight: 600;
  color: #64748b;
  margin-top: 4px;
}

.progress-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.main-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}

.todo-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  height: fit-content;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 0.875rem 1rem;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.todo-item:hover {
  background: #ffffff;
  border-color: #c7d2fe;
  transform: translateX(4px);
  box-shadow: 0 6px 16px -2px rgba(99, 102, 241, 0.12);
}

.todo-icon {
  display: flex;
  gap: 0.25rem;
  font-size: 18px;
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
}

.todo-date {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}

/* AI 推荐卡片 */
.ai-recommend-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.25rem 1.5rem;
  background: linear-gradient(135deg, rgba(238, 242, 255, 0.85) 0%, rgba(240, 249, 255, 0.85) 100%);
  border-radius: 16px;
  border: 1px solid rgba(99, 102, 241, 0.25);
  box-shadow: 0 8px 24px -4px rgba(99, 102, 241, 0.12);
  position: relative;
  overflow: hidden;
}

.ai-recommend-card::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -20%;
  width: 240px;
  height: 240px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.ai-recommend-icon {
  position: relative;
  width: 52px;
  height: 52px;
  min-width: 52px;
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
}

.ai-pulse-ring {
  position: absolute;
  inset: -4px;
  border-radius: 18px;
  border: 2px solid rgba(99, 102, 241, 0.4);
  animation: aiPulse 2s ease-in-out infinite;
}

@keyframes aiPulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 0; transform: scale(1.15); }
}

.ai-recommend-content {
  flex: 1;
  min-width: 0;
}

.ai-recommend-title {
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.ai-recommend-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.25);
}

.ai-recommend-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
  margin: 0;
}

.ai-score-tag {
  display: inline-block;
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  font-weight: 700;
  font-size: 12px;
  padding: 1px 7px;
  border-radius: 99px;
  margin: 0 3px;
}

.ai-recommend-meta {
  display: flex;
  gap: 1.25rem;
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.ai-recommend-meta strong {
  color: #4f46e5;
  font-weight: 700;
}

/* AI 任务标签 */
.ai-task-tag {
  vertical-align: middle;
  font-size: 11px !important;
  padding: 0 8px !important;
  height: 20px !important;
  line-height: 20px !important;
  font-weight: 700 !important;
}

@media (max-width: 640px) {
  .ai-recommend-card {
    flex-direction: column;
    text-align: center;
  }
}
</style>
