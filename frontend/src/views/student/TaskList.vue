<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Clock, Cpu, Collection, ArrowRight, Aim } from '@element-plus/icons-vue'
import api from '@/utils/request'

const tasks = ref<any[]>([])
const submissions = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const loading = ref(false)

// 搜索和筛选
const keyword = ref('')
const statusFilter = ref('')

const router = useRouter()

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
      await fetchTasks(selectedSemesterId.value)
    }
  } catch (error) {}
}

const getSubmissionStatus = (taskId: number) => {
  const sub: any = submissions.value.find((s: any) => s.task_id === taskId)
  return sub ? sub.status : 'not_submitted'
}

const fetchTasks = async (semesterId: number) => {
  loading.value = true
  try {
    const [tasksRes, subsRes]: any = await Promise.all([
      api.get('/tasks', { params: { semester_id: semesterId } }),
      api.get('/submissions/my', { params: { semester_id: semesterId } })
    ])
    tasks.value = tasksRes
    submissions.value = subsRes
  } finally {
    loading.value = false
  }
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'pending': return 'warning'
    case 'approved': return 'success'
    case 'rejected': return 'danger'
    default: return 'info'
  }
}

// 判断作业是否已截止
const isTaskExpired = (deadline: string) => {
  if (!deadline) return false
  return new Date(deadline).getTime() < new Date().getTime()
}

// 获取作业状态标签
const getTaskStatusTag = (task: any) => {
  if (isTaskExpired(task.deadline)) {
    return { text: '已截止', type: 'info' as const, class: 'opacity-60' }
  }
  const status = getSubmissionStatus(task.id)
  if (status === 'approved') return { text: '已完成', type: 'success' as const, class: '' }
  if (status === 'pending') return { text: '待批改', type: 'warning' as const, class: '' }
  if (status === 'rejected') return { text: '已驳回', type: 'danger' as const, class: '' }
  
  // 未提交但未截止
  const daysLeft = Math.ceil((new Date(task.deadline).getTime() - new Date().getTime()) / (1000 * 3600 * 24))
  if (daysLeft <= 3) return { text: '即将截止', type: 'danger' as const, class: '' }
  return { text: '进行中', type: 'info' as const, class: '' }
}

const handleUpload = (task: any) => {
  // 检查是否已截止
  if (isTaskExpired(task.deadline)) {
    ElMessage.warning('该作业已截止，无法提交')
    return
  }
  
  router.push({
    name: 'StudentSubmissions',
    query: { taskId: task.id }
  })
}

// 筛选后的作业
const filteredTasks = computed(() => {
  return tasks.value.filter((t) => {
    // 关键词搜索
    if (keyword.value.trim()) {
      const k = keyword.value.trim().toLowerCase()
      const match = t.title?.toLowerCase().includes(k) ||
                   t.content?.toLowerCase().includes(k)
      if (!match) return false
    }
    
    // 状态筛选
    if (statusFilter.value) {
      const status = getSubmissionStatus(t.id)
      if (status !== statusFilter.value) return false
    }
    
    return true
  })
})

const handleSemesterChange = () => {
  if (selectedSemesterId.value) {
    fetchTasks(selectedSemesterId.value)
  }
}

const clearFilters = () => {
  keyword.value = ''
  statusFilter.value = ''
}

// AI 智能优先级推荐
const aiPriorityTask = computed(() => {
  // 找到最需要关注的任务
  const unsubmitted = tasks.value.filter((t: any) => {
    const status = getSubmissionStatus(t.id)
    return (status === 'not_submitted' || status === 'rejected') && !isTaskExpired(t.deadline)
  })
  if (unsubmitted.length === 0) return null

  // 按截止时间排序，最紧迫的优先
  const sorted = [...unsubmitted].sort((a: any, b: any) => 
    new Date(a.deadline).getTime() - new Date(b.deadline).getTime()
  )
  const top = sorted[0]
  const daysLeft = Math.ceil((new Date(top.deadline).getTime() - Date.now()) / (1000 * 3600 * 24))
  const isRejected = getSubmissionStatus(top.id) === 'rejected'
  
  let reason = ''
  if (isRejected) {
    reason = '该作业已被驳回，建议优先修改后重新提交'
  } else if (daysLeft <= 1) {
    reason = '截止日期迫在眉睫，建议立即处理'
  } else if (daysLeft <= 3) {
    reason = `仅剩 ${daysLeft} 天截止，建议优先完成`
  } else {
    reason = `还有 ${daysLeft} 天截止，可以开始准备`
  }

  return {
    task: top,
    daysLeft,
    reason,
    urgency: daysLeft <= 1 || isRejected ? 'high' : daysLeft <= 3 ? 'medium' : 'low'
  }
})

onMounted(fetchSemesters)
</script>

<template>
  <div class="task-list-page">
    <div class="tl-page-header">
      <div>
        <h2 class="tl-page-title">
          <el-icon class="tl-title-icon"><Collection /></el-icon>
          作业列表
        </h2>
        <p class="tl-page-desc">查看和提交试讲作业，AI 智能推荐优先任务</p>
      </div>
      <el-select
        v-model="selectedSemesterId"
        placeholder="选择批次"
        @change="handleSemesterChange"
        style="width: 200px"
      >
        <el-option
          v-for="s in semesters"
          :key="s.id"
          :label="s.name"
          :value="s.id"
        >
          <span>{{ s.name }}</span>
          <el-tag v-if="s.status === 'active'" size="small" type="success" class="ml-2">进行中</el-tag>
        </el-option>
      </el-select>
    </div>

    <!-- AI 智能优先级推荐 -->
    <div v-if="aiPriorityTask" class="ai-priority-card" :class="'urgency-' + aiPriorityTask.urgency">
      <div class="ai-priority-inner">
        <div class="ai-priority-icon">
          <el-icon :size="20"><Aim /></el-icon>
        </div>
        <div class="ai-priority-body">
          <div class="ai-priority-label">
            <span class="ai-priority-label-text">AI 推荐优先完成</span>
            <div class="ai-priority-tag"><span class="ai-priority-dot"></span><span>AI</span></div>
          </div>
          <div class="ai-priority-task-name">{{ aiPriorityTask.task.title }}</div>
          <div class="ai-priority-reason">{{ aiPriorityTask.reason }}</div>
        </div>
        <el-button type="primary" size="small" round @click="handleUpload(aiPriorityTask.task)">
          去提交 <el-icon class="ml-1"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>
    
    <div v-if="semesters.length === 0" class="text-center py-10 text-gray-500">
      当前没有试讲批次
    </div>

    <div v-else v-loading="loading">
      <!-- 筛选器 -->
      <div class="mb-4 flex items-center gap-3">
        <el-input
          v-model="keyword"
          placeholder="搜索作业名称/内容"
          clearable
          style="width: 250px"
        />
        <el-select
          v-model="statusFilter"
          placeholder="状态筛选"
          clearable
          style="width: 150px"
        >
          <el-option label="未提交" value="not_submitted" />
          <el-option label="待批改" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-button @click="clearFilters">清空筛选</el-button>
        <div class="flex-1"></div>
        <el-tag>共 {{ filteredTasks.length }} 个作业</el-tag>
      </div>
      
      <el-empty v-if="filteredTasks.length === 0 && !loading" description="暂无作业" />
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" style="max-height: 600px; overflow-y: auto; padding-right: 8px;">
        <el-card 
          v-for="task in filteredTasks" 
          :key="task.id" 
          shadow="hover" 
          class="flex flex-col transition-all"
          :class="isTaskExpired(task.deadline) ? 'opacity-75 bg-gray-50' : ''"
        >
        <template #header>
          <div class="flex justify-between items-start gap-2">
            <span class="font-bold text-lg truncate flex-1" :title="task.title">{{ task.title }}</span>
            <div class="flex gap-1 flex-shrink-0">
              <el-tag size="small" v-if="task.require_lesson_plan" type="info">教案</el-tag>
              <el-tag size="small" v-if="task.require_video" type="warning">视频</el-tag>
            </div>
          </div>
        </template>
        
        <div class="text-sm text-gray-600 mb-4 h-20 overflow-hidden" v-html="task.content"></div>
        
        <div class="space-y-3 mt-auto">
          <!-- 状态标签 -->
          <div class="flex items-center gap-2">
            <el-tag 
              :type="getTaskStatusTag(task).type" 
              size="small"
              :class="getTaskStatusTag(task).class"
            >
              {{ getTaskStatusTag(task).text }}
            </el-tag>
            <span class="text-xs text-gray-400 flex-1">截止: {{ new Date(task.deadline).toLocaleDateString() }}</span>
          </div>
          
          <!-- 操作按钮 -->
          <div class="flex justify-end">
            <el-button
              v-if="isTaskExpired(task.deadline)"
              size="small"
              disabled
              plain
            >
              <el-icon class="mr-1"><Clock /></el-icon>
              已截止
            </el-button>
            <el-button
              v-else-if="getSubmissionStatus(task.id) === 'not_submitted' || getSubmissionStatus(task.id) === 'rejected'"
              type="primary"
              size="small"
              @click="handleUpload(task)"
            >
              {{ getSubmissionStatus(task.id) === 'rejected' ? '重新提交' : '去提交' }}
            </el-button>
            <el-button v-else size="small" disabled>
              已提交
            </el-button>
          </div>
        </div>
      </el-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-list-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tl-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.tl-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.tl-title-icon { color: #0891b2; }

.tl-page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

/* AI Priority Card */
.ai-priority-card {
  background: white;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.ai-priority-card.urgency-high { border-left: 3px solid #ef4444; background: #fef2f2; }
.ai-priority-card.urgency-medium { border-left: 3px solid #f59e0b; background: #fffbeb; }
.ai-priority-card.urgency-low { border-left: 3px solid #10b981; background: #ecfdf5; }

.ai-priority-inner {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-priority-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #0891b2;
  box-shadow: 0 2px 4px rgba(0,0,0,0.06);
}

.ai-priority-body {
  flex: 1;
  min-width: 0;
}

.ai-priority-label {
  display: flex;
  align-items: center;
  margin-bottom: 2px;
}

.ai-priority-label-text {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.ai-priority-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  background: #ccfbf1;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  color: #0891b2;
  margin-left: 6px;
}

.ai-priority-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #0891b2;
  animation: ai-p-pulse 2s infinite;
}

@keyframes ai-p-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.ai-priority-task-name {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-priority-reason {
  font-size: 12px;
  color: #64748b;
  margin-top: 1px;
}
</style>
