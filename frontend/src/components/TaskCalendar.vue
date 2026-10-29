<script setup lang="ts">
/**
 * 任务日历视图组件
 * 可视化展示作业截止日期，支持状态筛选和AI智能提醒
 */
import { ref, computed, watch } from 'vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { 
  Calendar, ArrowLeft, ArrowRight, Document, 
  Clock, Warning, Check, CircleClose, Cpu, Filter
} from '@element-plus/icons-vue'

const props = defineProps<{
  semesterId?: number | null
}>()

const authStore = useAuthStore()
const loading = ref(false)
const tasks = ref<any[]>([])
const submissions = ref<any[]>([])

// 筛选状态: all | pending | submitted | overdue
const statusFilter = ref<string>('all')

// 当前年月
const currentDate = ref(new Date())
const currentYear = computed(() => currentDate.value.getFullYear())
const currentMonth = computed(() => currentDate.value.getMonth())

// 月份名称
const monthNames = ['一月', '二月', '三月', '四月', '五月', '六月', 
                    '七月', '八月', '九月', '十月', '十一月', '十二月']

// 星期名称
const weekDays = ['日', '一', '二', '三', '四', '五', '六']

// 获取任务
const fetchTasks = async () => {
  if (!props.semesterId) return
  loading.value = true
  try {
    const res: any = await api.get('/tasks', {
      params: { semester_id: props.semesterId }
    })
    tasks.value = Array.isArray(res) ? res : (res.items || [])
  } catch (error) {
    // 静默处理
  } finally {
    loading.value = false
  }
}

// 获取提交（学生端）
const fetchSubmissions = async () => {
  if (authStore.userRole !== 'student' || !props.semesterId) return
  try {
    const res: any = await api.get('/submissions/my', {
      params: { semester_id: props.semesterId }
    })
    submissions.value = Array.isArray(res) ? res : (res.items || [])
  } catch (error) {
    // 忽略
  }
}

type TaskStatusTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

// 获取任务状态
const getTaskStatus = (task: any): { type: TaskStatusTagType; text: string; icon: any; category: string } => {
  const submission = submissions.value.find(s => s.task_id === task.id)
  if (!submission) {
    const deadline = new Date(task.deadline)
    if (deadline < new Date()) {
      return { type: 'danger', text: '已过期', icon: CircleClose, category: 'overdue' }
    }
    return { type: 'warning', text: '未提交', icon: Warning, category: 'pending' }
  }
  
  if (submission.status === 'approved') {
    return { type: 'success', text: '已通过', icon: Check, category: 'submitted' }
  }
  if (submission.status === 'rejected') {
    return { type: 'danger', text: '被驳回', icon: CircleClose, category: 'overdue' }
  }
  return { type: 'primary', text: '已提交', icon: Document, category: 'submitted' }
}

// 根据筛选条件过滤任务
const filteredTasks = computed(() => {
  if (statusFilter.value === 'all') return tasks.value
  return tasks.value.filter(task => {
    const status = getTaskStatus(task)
    return status.category === statusFilter.value
  })
})

// 获取某日期的任务（已过滤）
const getTasksOnDate = (date: Date) => {
  return filteredTasks.value.filter(task => {
    const deadline = new Date(task.deadline)
    return isSameDay(deadline, date)
  })
}

// 获取某日期的全部任务（不过滤，用于AI分析）
const getAllTasksOnDate = (date: Date) => {
  return tasks.value.filter(task => {
    const deadline = new Date(task.deadline)
    return isSameDay(deadline, date)
  })
}

// 判断是否同一天
const isSameDay = (d1: Date, d2: Date) => {
  return d1.getFullYear() === d2.getFullYear() &&
         d1.getMonth() === d2.getMonth() &&
         d1.getDate() === d2.getDate()
}

// 生成日历数据
const calendarDays = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const daysInPrevMonth = new Date(year, month, 0).getDate()
  
  const days: any[] = []
  
  for (let i = firstDay - 1; i >= 0; i--) {
    days.push({
      date: daysInPrevMonth - i,
      currentMonth: false,
      fullDate: new Date(year, month - 1, daysInPrevMonth - i)
    })
  }
  
  for (let i = 1; i <= daysInMonth; i++) {
    const fullDate = new Date(year, month, i)
    const tasksOnDay = getTasksOnDate(fullDate)
    const isToday = isSameDay(fullDate, new Date())
    
    days.push({
      date: i,
      currentMonth: true,
      fullDate,
      tasks: tasksOnDay,
      isToday
    })
  }
  
  const remaining = 42 - days.length
  for (let i = 1; i <= remaining; i++) {
    days.push({
      date: i,
      currentMonth: false,
      fullDate: new Date(year, month + 1, i)
    })
  }
  
  return days
})

// 切换月份
const prevMonth = () => {
  currentDate.value = new Date(currentYear.value, currentMonth.value - 1, 1)
}

const nextMonth = () => {
  currentDate.value = new Date(currentYear.value, currentMonth.value + 1, 1)
}

const goToday = () => {
  currentDate.value = new Date()
}

// 本月任务统计
const monthStats = computed(() => {
  const monthTasks = tasks.value.filter(task => {
    const deadline = new Date(task.deadline)
    return deadline.getFullYear() === currentYear.value &&
           deadline.getMonth() === currentMonth.value
  })
  
  let submitted = 0
  let pending = 0
  let overdue = 0
  
  monthTasks.forEach(task => {
    const status = getTaskStatus(task)
    if (status.category === 'submitted') {
      submitted++
    } else if (status.category === 'overdue') {
      overdue++
    } else {
      pending++
    }
  })
  
  return { total: monthTasks.length, submitted, pending, overdue }
})

// ==================== AI 智能分析 ====================
const aiInsights = computed(() => {
  const now = new Date()
  const insights: { type: 'urgent' | 'tip' | 'praise'; text: string }[] = []
  
  // 1. 紧急：3天内截止且未提交的任务
  const urgentTasks = tasks.value.filter(task => {
    const status = getTaskStatus(task)
    if (status.category !== 'pending') return false
    const deadline = new Date(task.deadline)
    const daysLeft = Math.ceil((deadline.getTime() - now.getTime()) / (24 * 3600 * 1000))
    return daysLeft >= 0 && daysLeft <= 3
  })
  if (urgentTasks.length > 0) {
    const names = urgentTasks.map(t => t.title).slice(0, 2).join('、')
    insights.push({
      type: 'urgent',
      text: `${urgentTasks.length} 项任务将在3天内截止（${names}${urgentTasks.length > 2 ? '等' : ''}），建议优先完成`
    })
  }
  
  // 2. 过期未交提醒
  const overdueTasks = tasks.value.filter(task => getTaskStatus(task).category === 'overdue')
  if (overdueTasks.length > 0) {
    insights.push({
      type: 'urgent',
      text: `${overdueTasks.length} 项任务已逾期，请尽快联系教师确认是否可以补交`
    })
  }
  
  // 3. 本周任务密度分析
  const weekStart = new Date(now)
  weekStart.setDate(now.getDate() - now.getDay())
  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekStart.getDate() + 6)
  const weekTasks = tasks.value.filter(task => {
    const d = new Date(task.deadline)
    return d >= weekStart && d <= weekEnd
  })
  if (weekTasks.length >= 3) {
    insights.push({
      type: 'tip',
      text: `本周有 ${weekTasks.length} 项任务截止，建议合理分配时间，每天完成 ${Math.ceil(weekTasks.length / 7)} 项`
    })
  }
  
  // 4. 表扬：完成率高
  const totalTasks = tasks.value.length
  const completedTasks = tasks.value.filter(t => getTaskStatus(t).category === 'submitted').length
  if (totalTasks > 0 && completedTasks / totalTasks >= 0.8) {
    insights.push({
      type: 'praise',
      text: `已完成 ${Math.round(completedTasks / totalTasks * 100)}% 的任务，表现优秀，继续保持！`
    })
  } else if (totalTasks > 0 && completedTasks === 0) {
    insights.push({
      type: 'tip',
      text: '尚未提交任何作业，建议从最早截止的任务开始完成'
    })
  }
  
  // 5. 下周预告
  const nextWeekStart = new Date(weekEnd)
  nextWeekStart.setDate(weekEnd.getDate() + 1)
  const nextWeekEnd = new Date(nextWeekStart)
  nextWeekEnd.setDate(nextWeekStart.getDate() + 6)
  const nextWeekTasks = tasks.value.filter(task => {
    const d = new Date(task.deadline)
    return d >= nextWeekStart && d <= nextWeekEnd
  })
  if (nextWeekTasks.length > 0) {
    insights.push({
      type: 'tip',
      text: `下周有 ${nextWeekTasks.length} 项任务截止，建议提前准备`
    })
  }
  
  return insights.slice(0, 3)
})

watch(() => props.semesterId, (val) => {
  if (val) {
    fetchTasks()
    fetchSubmissions()
  }
}, { immediate: true })
</script>

<template>
  <div v-loading="loading" class="task-calendar">
    <!-- 日历头部 -->
    <div class="calendar-header">
      <div class="header-left">
        <el-icon class="text-cyan-600 text-xl"><Calendar /></el-icon>
        <h3 class="text-lg font-bold text-gray-800">任务日历</h3>
      </div>
      <div class="header-center">
        <el-button text :icon="ArrowLeft" @click="prevMonth" />
        <span class="month-title">{{ currentYear }}年 {{ monthNames[currentMonth] }}</span>
        <el-button text :icon="ArrowRight" @click="nextMonth" />
        <el-button size="small" @click="goToday" class="ml-3">今天</el-button>
      </div>
      <div class="header-right">
        <div class="stat-item">
          <span class="stat-label">本月任务</span>
          <span class="stat-value text-cyan-700">{{ monthStats.total }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">已提交</span>
          <span class="stat-value text-emerald-600">{{ monthStats.submitted }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">待提交</span>
          <span class="stat-value text-amber-600">{{ monthStats.pending }}</span>
        </div>
      </div>
    </div>

    <!-- 状态筛选栏 -->
    <div class="filter-bar">
      <el-icon class="filter-icon"><Filter /></el-icon>
      <div class="filter-tabs">
        <button 
          class="filter-tab" 
          :class="{ active: statusFilter === 'all' }" 
          @click="statusFilter = 'all'"
        >
          全部 <span class="tab-count">{{ tasks.length }}</span>
        </button>
        <button 
          class="filter-tab pending" 
          :class="{ active: statusFilter === 'pending' }" 
          @click="statusFilter = 'pending'"
        >
          待提交 <span class="tab-count">{{ monthStats.pending }}</span>
        </button>
        <button 
          class="filter-tab submitted" 
          :class="{ active: statusFilter === 'submitted' }" 
          @click="statusFilter = 'submitted'"
        >
          已完成 <span class="tab-count">{{ monthStats.submitted }}</span>
        </button>
        <button 
          class="filter-tab overdue" 
          :class="{ active: statusFilter === 'overdue' }" 
          @click="statusFilter = 'overdue'"
        >
          已逾期 <span class="tab-count">{{ monthStats.overdue }}</span>
        </button>
      </div>
    </div>

    <!-- 星期标题 -->
    <div class="weekday-row">
      <div v-for="day in weekDays" :key="day" class="weekday-cell">
        {{ day }}
      </div>
    </div>

    <!-- 日历网格 -->
    <div class="calendar-grid">
      <div 
        v-for="(day, index) in calendarDays" 
        :key="index"
        class="calendar-cell"
        :class="{
          'other-month': !day.currentMonth,
          'today': day.isToday,
          'has-tasks': day.tasks?.length > 0
        }"
      >
        <div class="cell-date">{{ day.date }}</div>
        <div v-if="day.tasks?.length" class="cell-tasks">
          <el-tooltip 
            v-for="task in day.tasks.slice(0, 2)" 
            :key="task.id"
            :content="`${task.title} - ${getTaskStatus(task).text}`"
            placement="top"
          >
            <div 
              class="task-dot"
              :class="`task-${getTaskStatus(task).type}`"
            >
              <el-icon class="text-xs"><component :is="getTaskStatus(task).icon" /></el-icon>
            </div>
          </el-tooltip>
          <div v-if="day.tasks.length > 2" class="more-tasks">
            +{{ day.tasks.length - 2 }}
          </div>
        </div>
      </div>
    </div>

    <!-- 今日任务列表 -->
    <div class="today-tasks" v-if="getAllTasksOnDate(new Date()).length > 0">
      <h4 class="text-sm font-medium text-gray-700 mb-2">
        <el-icon class="text-amber-500 mr-1"><Clock /></el-icon>
        今日截止
      </h4>
      <div class="task-list">
        <div 
          v-for="task in getAllTasksOnDate(new Date())" 
          :key="task.id"
          class="task-item"
        >
          <el-icon class="text-red-500"><Document /></el-icon>
          <span class="task-title">{{ task.title }}</span>
          <el-tag :type="getTaskStatus(task).type" size="small" effect="plain">
            {{ getTaskStatus(task).text }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- AI 智能提醒 -->
    <div v-if="aiInsights.length > 0" class="ai-insights">
      <div class="ai-insights-header">
        <el-icon class="text-cyan-600"><Cpu /></el-icon>
        <span class="ai-insights-title">AI 智能提醒</span>
        <span class="ai-badge">AI</span>
      </div>
      <div class="ai-insights-list">
        <div 
          v-for="(insight, idx) in aiInsights" 
          :key="idx"
          class="ai-insight-item"
          :class="insight.type"
        >
          <span class="insight-icon">
            <template v-if="insight.type === 'urgent'"><el-icon><Warning /></el-icon></template>
            <template v-else-if="insight.type === 'praise'"><el-icon><Check /></el-icon></template>
            <template v-else><el-icon><Cpu /></el-icon></template>
          </span>
          <span class="insight-text">{{ insight.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-calendar {
  background: white;
  border-radius: 1rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.month-title {
  font-size: 1rem;
  font-weight: 600;
  color: #374151;
  min-width: 120px;
  text-align: center;
}

.header-right {
  display: flex;
  gap: 1.5rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
}

.stat-label {
  font-size: 0.75rem;
  color: #9ca3af;
}

.stat-value {
  font-size: 1.125rem;
  font-weight: 700;
}

.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: #f9fafb;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
}

.weekday-cell {
  text-align: center;
  padding: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.calendar-cell {
  aspect-ratio: 1;
  padding: 0.375rem;
  background: #fafafa;
  border-radius: 0.375rem;
  display: flex;
  flex-direction: column;
  min-height: 60px;
  transition: background 0.2s;
}

.calendar-cell:hover {
  background: #f0f9ff;
}

.calendar-cell.other-month {
  background: transparent;
}

.calendar-cell.other-month .cell-date {
  color: #d1d5db;
}

.calendar-cell.today {
  background: #cffafe;
  border: 2px solid #0891b2;
}

.calendar-cell.today .cell-date {
  color: #0891b2;
  font-weight: 700;
}

.calendar-cell.has-tasks {
  background: #fef3c7;
}

.cell-date {
  font-size: 0.75rem;
  font-weight: 500;
  color: #374151;
  margin-bottom: 0.25rem;
}

.cell-tasks {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.task-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.task-success {
  background: #10b981;
  color: white;
}

.task-primary {
  background: #0891b2;
  color: white;
}

.task-warning {
  background: #f59e0b;
  color: white;
}

.task-danger {
  background: #ef4444;
  color: white;
}

.more-tasks {
  font-size: 0.625rem;
  color: #6b7280;
  background: #e5e7eb;
  padding: 0 4px;
  border-radius: 4px;
  height: 18px;
  line-height: 18px;
}

.today-tasks {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #fef2f2;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}

.task-title {
  flex: 1;
  color: #374151;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem 0;
}

.filter-icon {
  color: #9ca3af;
  font-size: 14px;
  flex-shrink: 0;
}

.filter-tabs {
  display: flex;
  gap: 0.375rem;
  flex-wrap: wrap;
}

.filter-tab {
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.filter-tab:hover {
  border-color: #d1d5db;
  background: #f3f4f6;
}

.filter-tab.active {
  background: #ecfeff;
  border-color: #0891b2;
  color: #0891b2;
  font-weight: 600;
}

.filter-tab.pending.active {
  background: #fffbeb;
  border-color: #f59e0b;
  color: #d97706;
}

.filter-tab.submitted.active {
  background: #ecfdf5;
  border-color: #10b981;
  color: #059669;
}

.filter-tab.overdue.active {
  background: #fef2f2;
  border-color: #ef4444;
  color: #dc2626;
}

.tab-count {
  font-size: 11px;
  font-weight: 700;
  background: rgba(0, 0, 0, 0.06);
  padding: 0 5px;
  border-radius: 8px;
  min-width: 18px;
  text-align: center;
}

.filter-tab.active .tab-count {
  background: rgba(0, 0, 0, 0.08);
}

/* AI Insights */
.ai-insights {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
}

.ai-insights-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.625rem;
}

.ai-insights-title {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #374151;
}

.ai-badge {
  font-size: 10px;
  font-weight: 700;
  color: #0891b2;
  background: #ecfeff;
  padding: 1px 8px;
  border-radius: 8px;
  border: 1px solid #cffafe;
}

.ai-insights-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.ai-insight-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 0.5rem;
  font-size: 0.8125rem;
  line-height: 1.5;
}

.ai-insight-item.urgent {
  background: #fef2f2;
  color: #991b1b;
}

.ai-insight-item.urgent .insight-icon {
  color: #ef4444;
}

.ai-insight-item.tip {
  background: #ecfeff;
  color: #155e75;
}

.ai-insight-item.tip .insight-icon {
  color: #0891b2;
}

.ai-insight-item.praise {
  background: #ecfdf5;
  color: #065f46;
}

.ai-insight-item.praise .insight-icon {
  color: #10b981;
}

.insight-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.insight-text {
  flex: 1;
}

@media (max-width: 640px) {
  .header-right {
    display: none;
  }
  
  .calendar-cell {
    min-height: 40px;
    padding: 0.25rem;
  }
  
  .cell-date {
    font-size: 0.625rem;
  }
  
  .task-dot {
    width: 14px;
    height: 14px;
  }
  
  .filter-bar {
    overflow-x: auto;
  }
}
</style>
