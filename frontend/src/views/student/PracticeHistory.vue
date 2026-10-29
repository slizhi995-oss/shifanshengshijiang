<script setup lang="ts">
/**
 * 练习会话历史页面
 * 学生查看历史对话记录和报告
 */
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'
import { aiApi } from '@/api'
import { 
  ChatDotRound, Clock, Document, Delete, View, 
  Star, Warning, Refresh, Plus, Search, Cpu, TrendCharts, Aim, ArrowRight, MagicStick
} from '@element-plus/icons-vue'

const loading = ref(false)
const sessions = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(12)
const total = ref(0)
const statusFilter = ref('')
const searchKeyword = ref('')

// 会话详情对话框
const showDetailDialog = ref(false)
const selectedSession = ref<any>(null)
const detailLoading = ref(false)

// 获取会话列表
const fetchSessions = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/practice-sessions', {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        status: statusFilter.value || undefined
      }
    })
    if (res.success) {
      sessions.value = res.data?.items || []
      total.value = res.data?.total || 0
    } else {
      sessions.value = res.items || []
      total.value = res.total || 0
    }
  } catch (error) {
    ElMessage.error('获取会话列表失败')
  } finally {
    loading.value = false
  }
}

// 查看会话详情
const viewSession = async (session: any) => {
  selectedSession.value = session
  showDetailDialog.value = true
  detailLoading.value = true
  
  try {
    const res: any = await api.get(`/practice-sessions/${session.id}`)
    if (res.success) {
      selectedSession.value = res.data
    } else {
      selectedSession.value = res
    }
  } catch (error) {
    ElMessage.error('获取会话详情失败')
  } finally {
    detailLoading.value = false
  }
}

// 删除会话
const deleteSession = async (session: any) => {
  await ElMessageBox.confirm('确定删除这个会话吗？删除后无法恢复。', '确认删除', {
    type: 'warning'
  })
  
  try {
    await api.delete(`/practice-sessions/${session.id}`)
    ElMessage.success('会话已删除')
    fetchSessions()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 过滤后的会话列表
const filteredSessions = computed(() => {
  if (!searchKeyword.value) return sessions.value
  const keyword = searchKeyword.value.toLowerCase()
  return sessions.value.filter((s: any) => 
    s.topic?.toLowerCase().includes(keyword) ||
    s.session_type?.toLowerCase().includes(keyword)
  )
})

// 获取会话图标
const getSessionIcon = (type: string) => {
  const icons: Record<string, any> = {
    'practice': ChatDotRound,
    'prepare': Document,
    'review': Star
  }
  return icons[type] || ChatDotRound
}

// 获取状态样式
const getStatusStyle = (status: string) => {
  const styles: Record<string, { type: string; text: string }> = {
    'active': { type: 'primary', text: '进行中' },
    'completed': { type: 'success', text: '已完成' },
    'archived': { type: 'info', text: '已归档' }
  }
  return styles[status] || { type: 'info', text: status }
}

// 获取类型标签
const getTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    'practice': '试讲练习',
    'prepare': '备课咨询',
    'review': '教案评审'
  }
  return labels[type] || type
}

// 格式化时间
const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  
  return date.toLocaleDateString()
}

// AI 数据叙事
const aiNarrativeLoading = ref(false)
const aiNarrative = ref('')
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

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

const fetchAINarrative = async () => {
  if (sessions.value.length === 0) return
  aiNarrativeLoading.value = true
  try {
    const summary = aiSummary.value
    if (!summary) return
    const res = await aiApi.dataNarrative({
      role: 'student',
      stats: {
        total_practice_sessions: summary.totalSessions,
        completed_sessions: summary.completedCount,
        total_messages: summary.totalMessages,
        average_score: summary.avgScore,
        this_week_count: summary.thisWeekCount,
        context: '试讲练习历史分析'
      }
    })
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

// AI 练习分析摘要
const aiSummary = computed(() => {
  const all = sessions.value
  if (all.length === 0) return null

  const completedSessions = all.filter((s: any) => s.status === 'completed')
  const totalMessages = all.reduce((sum: number, s: any) => sum + (s.messages?.length || 0), 0)
  const sessionsWithReport = completedSessions.filter((s: any) => s.report?.score)
  const avgScore = sessionsWithReport.length > 0
    ? Math.round(sessionsWithReport.reduce((sum: number, s: any) => sum + s.report.score, 0) / sessionsWithReport.length)
    : 0

  // 计算本周练习次数
  const now = new Date()
  const weekStart = new Date(now)
  weekStart.setDate(now.getDate() - now.getDay())
  weekStart.setHours(0, 0, 0, 0)
  const thisWeekCount = all.filter((s: any) => new Date(s.created_at) >= weekStart).length

  // 成绩趋势
  let trend = 'stable'
  if (sessionsWithReport.length >= 2) {
    const sorted = [...sessionsWithReport].sort((a: any, b: any) =>
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    )
    const last = sorted[sorted.length - 1].report.score
    const prev = sorted[sorted.length - 2].report.score
    trend = last > prev ? 'up' : last < prev ? 'down' : 'stable'
  }

  return {
    totalSessions: all.length,
    completedCount: completedSessions.length,
    totalMessages,
    avgScore,
    thisWeekCount,
    trend
  }
})

// AI 下次练习建议
const nextPracticeAdvice = computed(() => {
  const summary = aiSummary.value
  if (!summary) return null
  
  if (summary.thisWeekCount === 0) {
    return { text: '本周尚未练习，建议尽快开始以保持手感', urgency: 'high' as const }
  }
  if (summary.thisWeekCount < 3) {
    return { text: `本周已练习 ${summary.thisWeekCount} 次，再练 ${3 - summary.thisWeekCount} 次达到推荐频率`, urgency: 'medium' as const }
  }
  if (summary.avgScore > 0 && summary.avgScore < 75) {
    return { text: '平均分偏低，建议针对薄弱环节重点练习', urgency: 'medium' as const }
  }
  return { text: `本周已练习 ${summary.thisWeekCount} 次，保持良好节奏！`, urgency: 'low' as const }
})

// 获取 AI 评价等级标签
const getAIEvalTag = (session: any) => {
  if (!session.report?.score) return null
  const score = session.report.score
  if (score >= 90) return { text: '优秀', type: 'success' as const, color: '#10b981' }
  if (score >= 75) return { text: '良好', type: 'primary' as const, color: '#0891b2' }
  if (score >= 60) return { text: '合格', type: 'warning' as const, color: '#f59e0b' }
  return { text: '需改进', type: 'danger' as const, color: '#ef4444' }
}

// 刷新
const handleRefresh = () => {
  currentPage.value = 1
  fetchSessions()
}

// 分页
const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchSessions()
}

onMounted(async () => {
  await fetchSessions()
  fetchAINarrative()
})
</script>

<template>
  <div v-loading="loading" class="practice-history-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <el-icon class="title-icon"><ChatDotRound /></el-icon>
          练习记录
        </h2>
        <p class="page-desc">查看历史对话、AI 练习分析和成长趋势</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索主题..."
          :prefix-icon="Search"
          clearable
          class="w-48"
        />
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable class="w-32" @change="handleRefresh">
          <el-option label="进行中" value="active" />
          <el-option label="已完成" value="completed" />
          <el-option label="已归档" value="archived" />
        </el-select>
        <el-button :icon="Refresh" @click="handleRefresh" circle />
      </div>
    </div>

    <!-- 统计卡片行 -->
    <div v-if="aiSummary" class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon bg-blue"><el-icon :size="22"><ChatDotRound /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value text-blue">{{ aiSummary.totalSessions }}</div>
          <div class="stat-label">总练习</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon bg-green"><el-icon :size="22"><Star /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value text-green">{{ aiSummary.completedCount }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon bg-amber"><el-icon :size="22"><TrendCharts /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value" :class="aiSummary.avgScore >= 75 ? 'text-green' : 'text-amber'">{{ aiSummary.avgScore > 0 ? aiSummary.avgScore : '--' }}</div>
          <div class="stat-label">平均分</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" :class="aiSummary.trend === 'up' ? 'bg-green' : aiSummary.trend === 'down' ? 'bg-red' : 'bg-gray'">
          <span class="trend-arrow">{{ aiSummary.trend === 'up' ? '↑' : aiSummary.trend === 'down' ? '↓' : '→' }}</span>
        </div>
        <div class="stat-body">
          <div class="stat-value" :class="aiSummary.trend === 'up' ? 'text-green' : aiSummary.trend === 'down' ? 'text-red' : 'text-gray'">{{ aiSummary.trend === 'up' ? '上升' : aiSummary.trend === 'down' ? '下降' : '持平' }}</div>
          <div class="stat-label">趋势</div>
        </div>
      </div>
    </div>

    <!-- AI 叙事 + 下次练习建议 -->
    <div v-if="aiSummary" class="ai-row">
      <!-- AI 数据叙事 -->
      <div v-if="aiNarrative || aiNarrativeLoading" class="ai-narrative-card">
        <div class="ai-narrative-inner">
          <div class="ai-narrative-icon">
            <el-icon :size="22" color="#0891b2"><Cpu /></el-icon>
          </div>
          <div class="ai-narrative-body">
            <div class="ai-narrative-label">
              <span class="label-text">AI 练习分析</span>
              <div class="ai-tag"><span class="ai-tag-dot"></span><span>AI 生成</span></div>
            </div>
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="ai-narrative-text loading-text">
              AI 正在分析你的练习数据...
            </div>
            <div v-else class="ai-narrative-text">
              {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="typing-dot">|</span>
            </div>
          </div>
        </div>
      </div>

      <!-- AI 下次练习建议 -->
      <div v-if="nextPracticeAdvice" class="ai-advice-card" :class="'urgency-' + nextPracticeAdvice.urgency">
        <div class="advice-header">
          <div class="advice-icon">
            <el-icon :size="18"><Aim /></el-icon>
          </div>
          <span class="advice-title">AI 下次练习建议</span>
        </div>
        <p class="advice-text">{{ nextPracticeAdvice.text }}</p>
        <el-button type="primary" size="small" round @click="$router.push('/student/ai-assistant')">
          开始练习 <el-icon class="ml-1"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 空状态 -->
    <el-empty 
      v-if="filteredSessions.length === 0 && !loading" 
      description="暂无练习记录，去 AI 备课助手开始练习吧！"
    >
      <el-button type="primary" @click="$router.push('/student/ai-assistant')">
        <el-icon class="mr-1"><Plus /></el-icon>
        开始练习
      </el-button>
    </el-empty>

    <!-- 会话卡片列表 -->
    <div v-else class="sessions-grid">
      <el-card 
        v-for="session in filteredSessions" 
        :key="session.id"
        class="session-card"
        shadow="hover"
        @click="viewSession(session)"
      >
        <div class="session-header">
          <div class="session-icon" :class="`bg-${session.status === 'completed' ? 'emerald' : 'indigo'}-100`">
            <el-icon :class="`text-${session.status === 'completed' ? 'emerald' : 'indigo'}-600 text-xl`">
              <component :is="getSessionIcon(session.session_type)" />
            </el-icon>
          </div>
          <el-tag 
            :type="getStatusStyle(session.status).type as any" 
            size="small" 
            effect="plain"
            round
          >
            {{ getStatusStyle(session.status).text }}
          </el-tag>
        </div>
        
        <h3 class="session-title">{{ session.topic || '未命名对话' }}</h3>
        <p class="session-type">{{ getTypeLabel(session.session_type) }}</p>
        
        <div class="session-meta">
          <div class="meta-item">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ session.messages?.length || 0 }} 条消息</span>
          </div>
          <div class="meta-item">
            <el-icon><Clock /></el-icon>
            <span>{{ formatTime(session.updated_at || session.created_at) }}</span>
          </div>
        </div>
        
        <!-- 报告预览 -->
        <div v-if="session.report" class="session-report-preview">
          <div class="report-score-row">
            <div class="report-score" v-if="session.report.score">
              <el-icon class="text-amber-500"><Star /></el-icon>
              <span>{{ session.report.score }} 分</span>
            </div>
            <el-tag
              v-if="getAIEvalTag(session)"
              :type="getAIEvalTag(session)!.type"
              size="small"
              effect="dark"
              round
              class="ai-eval-tag"
            >
              <el-icon class="mr-0.5" :size="10"><Cpu /></el-icon>
              AI: {{ getAIEvalTag(session)!.text }}
            </el-tag>
          </div>
        </div>
        
        <div class="session-actions">
          <el-button text type="primary" :icon="View" @click.stop="viewSession(session)">
            查看
          </el-button>
          <el-button text type="danger" :icon="Delete" @click.stop="deleteSession(session)">
            删除
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-6">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="selectedSession?.topic || '会话详情'"
      width="700px"
      class="session-detail-dialog"
    >
      <div v-loading="detailLoading" class="session-detail">
        <!-- 会话信息 -->
        <div class="detail-header">
          <div class="flex items-center gap-3">
            <el-tag :type="getStatusStyle(selectedSession?.status).type as any" effect="dark">
              {{ getStatusStyle(selectedSession?.status).text }}
            </el-tag>
            <span class="text-gray-500">{{ getTypeLabel(selectedSession?.session_type) }}</span>
          </div>
          <span class="text-sm text-gray-400">
            {{ new Date(selectedSession?.created_at).toLocaleString() }}
          </span>
        </div>
        
        <!-- 对话内容 -->
        <div class="messages-container">
          <div 
            v-for="(msg, index) in selectedSession?.messages" 
            :key="index"
            class="message-item"
            :class="msg.role === 'user' ? 'user-message' : 'assistant-message'"
          >
            <div class="message-avatar">
              <span v-if="msg.role === 'user'">我</span>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
              <div class="message-time" v-if="msg.timestamp">
                {{ new Date(msg.timestamp).toLocaleTimeString() }}
              </div>
            </div>
          </div>
        </div>
        
        <!-- 报告 -->
        <div v-if="selectedSession?.report" class="report-section">
          <h4 class="report-title">
            <el-icon class="text-amber-500"><Star /></el-icon>
            练习报告
            <el-tag v-if="selectedSession.report.score" type="warning" size="small" effect="dark">
              {{ selectedSession.report.score }} 分
            </el-tag>
          </h4>
          
          <div class="report-content">
            <div v-if="selectedSession.report.strengths?.length" class="report-block">
              <h5 class="block-title text-emerald-600">
                <el-icon><Star /></el-icon> 优点
              </h5>
              <ul class="block-list">
                <li v-for="(item, i) in selectedSession.report.strengths" :key="i">{{ item }}</li>
              </ul>
            </div>
            
            <div v-if="selectedSession.report.weaknesses?.length" class="report-block">
              <h5 class="block-title text-amber-600">
                <el-icon><Warning /></el-icon> 待改进
              </h5>
              <ul class="block-list">
                <li v-for="(item, i) in selectedSession.report.weaknesses" :key="i">{{ item }}</li>
              </ul>
            </div>
            
            <div v-if="selectedSession.report.suggestions?.length" class="report-block">
              <h5 class="block-title text-blue-600">
                <el-icon><Document /></el-icon> 建议
              </h5>
              <ul class="block-list">
                <li v-for="(item, i) in selectedSession.report.suggestions" :key="i">{{ item }}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.practice-history-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.title-icon { color: #0891b2; }

.page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: white;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: all 0.2s;
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
  transform: translateY(-2px);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.bg-blue { background: #eff6ff; color: #3b82f6; }
.stat-icon.bg-green { background: #ecfdf5; color: #10b981; }
.stat-icon.bg-amber { background: #fffbeb; color: #f59e0b; }
.stat-icon.bg-red { background: #fef2f2; color: #ef4444; }
.stat-icon.bg-gray { background: #f3f4f6; color: #6b7280; }

.trend-arrow { font-size: 22px; font-weight: 700; }

.stat-body { display: flex; flex-direction: column; }

.stat-value { font-size: 22px; font-weight: 800; line-height: 1; }
.stat-value.text-blue { color: #3b82f6; }
.stat-value.text-green { color: #10b981; }
.stat-value.text-amber { color: #f59e0b; }
.stat-value.text-red { color: #ef4444; }
.stat-value.text-gray { color: #6b7280; }

.stat-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }

/* AI Row */
.ai-row {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 14px;
}

@media (max-width: 900px) {
  .ai-row { grid-template-columns: 1fr; }
}

/* AI Narrative */
.ai-narrative-card {
  background: #ecfeff;
  border: 1px solid #cffafe;
  border-radius: 14px;
  padding: 18px 20px;
}

.ai-narrative-inner {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.ai-narrative-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(8, 145, 178, 0.1);
}

.ai-narrative-body { flex: 1; min-width: 0; }

.ai-narrative-label {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.label-text {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.ai-narrative-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}

.ai-narrative-text.loading-text { color: #94a3b8; }

.typing-dot {
  animation: blink-cursor 1s infinite;
  color: #0891b2;
  font-weight: bold;
}

@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.ai-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  background: #ccfbf1;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  color: #0891b2;
  margin-left: 8px;
}

.ai-tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0891b2;
  animation: ai-pulse 2s infinite;
}

@keyframes ai-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* AI Advice Card */
.ai-advice-card {
  background: white;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.ai-advice-card.urgency-high { border-left: 3px solid #ef4444; }
.ai-advice-card.urgency-medium { border-left: 3px solid #f59e0b; }
.ai-advice-card.urgency-low { border-left: 3px solid #10b981; }

.advice-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.advice-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #ecfeff;
  color: #0891b2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.advice-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.advice-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  margin: 0;
}

.sessions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.session-card {
  cursor: pointer;
  border-radius: 1rem;
  transition: transform 0.2s, box-shadow 0.2s;
}

.session-card:hover {
  transform: translateY(-4px);
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.session-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.session-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-type {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.75rem;
}

.session-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: #9ca3af;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.session-report-preview {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px dashed #e5e7eb;
}

.report-score {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #f59e0b;
}

.session-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #f3f4f6;
}

/* 详情对话框 */
.session-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}

.messages-container {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem;
  background: #f9fafb;
  border-radius: 0.75rem;
}

.message-item {
  display: flex;
  gap: 0.75rem;
}

.user-message {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.user-message .message-avatar {
  background: #0891b2;
  color: white;
}

.assistant-message .message-avatar {
  background: #e5e7eb;
  color: #4b5563;
}

.message-content {
  max-width: 70%;
}

.message-text {
  padding: 0.75rem 1rem;
  border-radius: 1rem;
  font-size: 0.875rem;
  line-height: 1.5;
}

.user-message .message-text {
  background: #0891b2;
  color: white;
  border-bottom-right-radius: 4px;
}

.assistant-message .message-text {
  background: white;
  color: #374151;
  border-bottom-left-radius: 4px;
}

.message-time {
  font-size: 0.625rem;
  color: #9ca3af;
  margin-top: 0.25rem;
  text-align: right;
}

.user-message .message-time {
  text-align: left;
}

/* 报告区域 */
.report-section {
  padding: 1rem;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 0.75rem;
}

.report-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 0.75rem;
}

.report-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.report-block {
  background: white;
  padding: 0.75rem;
  border-radius: 0.5rem;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.block-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 0.875rem;
  color: #4b5563;
}

.block-list li {
  padding: 0.25rem 0;
  padding-left: 1rem;
  position: relative;
}

.block-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #9ca3af;
}

/* AI 评价标签 */
.report-score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ai-eval-tag {
  font-size: 0.625rem !important;
}
</style>
