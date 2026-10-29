<script setup lang="ts">
/**
 * 提交状态时间线组件
 * 展示作业从提交到批改的完整流程
 */
import { computed } from 'vue'
import { 
  Upload, Loading, Check, Close, Clock, 
  Document, VideoCamera, DataAnalysis, Edit
} from '@element-plus/icons-vue'

type SubmissionStatus = 'pending' | 'graded' | 'approved' | 'rejected'

interface TimelineEvent {
  type: 'submit' | 'ai_analysis' | 'grading' | 'result'
  status: 'completed' | 'processing' | 'pending' | 'failed'
  title: string
  time?: string
  description?: string
  data?: any
}

const props = defineProps<{
  status: SubmissionStatus
  submittedAt?: string
  gradedAt?: string
  approvedAt?: string
  rejectedAt?: string
  rejectReason?: string
  hasAIAnalysis?: boolean
  aiAnalyzedAt?: string
  lessonPlanScore?: number
  videoScore?: number
  totalScore?: number
  feedback?: string
}>()

const formatTime = (time?: string) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 生成时间线事件
const events = computed<TimelineEvent[]>(() => {
  const list: TimelineEvent[] = []
  
  // 1. 提交事件
  list.push({
    type: 'submit',
    status: 'completed',
    title: '作业已提交',
    time: formatTime(props.submittedAt),
    description: '教案和视频文件上传成功'
  })
  
  // 2. AI 分析事件
  if (props.hasAIAnalysis !== false) {
    const aiStatus = props.aiAnalyzedAt ? 'completed' : 
                     props.status === 'pending' ? 'processing' : 'pending'
    list.push({
      type: 'ai_analysis',
      status: aiStatus,
      title: aiStatus === 'completed' ? 'AI 分析完成' : 
             aiStatus === 'processing' ? 'AI 正在分析...' : '等待 AI 分析',
      time: formatTime(props.aiAnalyzedAt),
      description: aiStatus === 'completed' ? '教案和视频已完成智能分析' : undefined
    })
  }
  
  // 3. 批改事件
  if (props.status !== 'pending') {
    list.push({
      type: 'grading',
      status: 'completed',
      title: '老师已批改',
      time: formatTime(props.gradedAt || props.approvedAt || props.rejectedAt),
      data: {
        lessonPlanScore: props.lessonPlanScore,
        videoScore: props.videoScore,
        totalScore: props.totalScore
      }
    })
  } else {
    list.push({
      type: 'grading',
      status: 'pending',
      title: '等待老师批改',
      description: '老师将尽快审阅您的作业'
    })
  }
  
  // 4. 结果事件
  if (props.status === 'approved') {
    list.push({
      type: 'result',
      status: 'completed',
      title: '🎉 作业已通过',
      time: formatTime(props.approvedAt),
      description: props.feedback
    })
  } else if (props.status === 'rejected') {
    list.push({
      type: 'result',
      status: 'failed',
      title: '作业被驳回',
      time: formatTime(props.rejectedAt),
      description: props.rejectReason || '请根据老师反馈修改后重新提交'
    })
  }
  
  return list
})

// 获取事件图标
const getEventIcon = (event: TimelineEvent) => {
  if (event.type === 'submit') return Upload
  if (event.type === 'ai_analysis') return DataAnalysis
  if (event.type === 'grading') return Edit
  if (event.status === 'completed') return Check
  if (event.status === 'failed') return Close
  return Clock
}

// 获取事件颜色
const getEventColor = (event: TimelineEvent) => {
  if (event.status === 'completed') return '#10b981'
  if (event.status === 'processing') return '#0891b2'
  if (event.status === 'failed') return '#ef4444'
  return '#94a3b8'
}
</script>

<template>
  <div class="submission-timeline">
    <div 
      v-for="(event, index) in events" 
      :key="index"
      class="timeline-item"
      :class="{
        completed: event.status === 'completed',
        processing: event.status === 'processing',
        pending: event.status === 'pending',
        failed: event.status === 'failed',
        last: index === events.length - 1
      }"
    >
      <!-- 连接线 -->
      <div v-if="index < events.length - 1" class="timeline-line"></div>
      
      <!-- 节点 -->
      <div 
        class="timeline-node"
        :style="{ background: getEventColor(event) }"
      >
        <el-icon v-if="event.status === 'processing'" class="spin">
          <Loading />
        </el-icon>
        <el-icon v-else>
          <component :is="getEventIcon(event)" />
        </el-icon>
      </div>
      
      <!-- 内容 -->
      <div class="timeline-content">
        <div class="content-header">
          <h4 class="event-title">{{ event.title }}</h4>
          <span v-if="event.time" class="event-time">{{ event.time }}</span>
        </div>
        
        <p v-if="event.description" class="event-desc">{{ event.description }}</p>
        
        <!-- 成绩详情 -->
        <div v-if="event.data?.totalScore" class="score-detail">
          <div class="score-item">
            <el-icon><Document /></el-icon>
            <span>教案分</span>
            <strong>{{ event.data.lessonPlanScore || '-' }}</strong>
          </div>
          <div class="score-item">
            <el-icon><VideoCamera /></el-icon>
            <span>视频分</span>
            <strong>{{ event.data.videoScore || '-' }}</strong>
          </div>
          <div class="score-item total">
            <span>总分</span>
            <strong>{{ event.data.totalScore }}</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.submission-timeline {
  padding: 16px 0;
}

.timeline-item {
  display: flex;
  gap: 16px;
  position: relative;
  padding-bottom: 24px;
}

.timeline-item.last {
  padding-bottom: 0;
}

/* 连接线 */
.timeline-line {
  position: absolute;
  left: 17px;
  top: 40px;
  bottom: 0;
  width: 2px;
  background: #e2e8f0;
}

.timeline-item.completed .timeline-line {
  background: #10b981;
}

/* 节点 */
.timeline-node {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  z-index: 1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.timeline-item.pending .timeline-node {
  background: #94a3b8 !important;
}

.timeline-node .el-icon {
  font-size: 16px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 内容 */
.timeline-content {
  flex: 1;
  padding-top: 4px;
}

.content-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.event-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin: 0;
}

.timeline-item.pending .event-title {
  color: #94a3b8;
}

.timeline-item.failed .event-title {
  color: #ef4444;
}

.event-time {
  font-size: 12px;
  color: #94a3b8;
}

.event-desc {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0 0;
  line-height: 1.5;
}

/* 成绩详情 */
.score-detail {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
}

.score-item .el-icon {
  color: #94a3b8;
}

.score-item strong {
  color: #334155;
  font-size: 15px;
}

.score-item.total {
  margin-left: auto;
  padding-left: 16px;
  border-left: 1px solid #e2e8f0;
}

.score-item.total strong {
  color: #0891b2;
  font-size: 18px;
}

@media (max-width: 640px) {
  .score-detail {
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .score-item.total {
    width: 100%;
    margin-left: 0;
    padding-left: 0;
    border-left: none;
    padding-top: 8px;
    border-top: 1px solid #e2e8f0;
    justify-content: center;
  }
}
</style>
</script>
