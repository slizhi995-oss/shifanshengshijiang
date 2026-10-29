<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, VideoCamera, ChatLineSquare, View, Printer, Cpu, TrendCharts, Aim, MagicStick, ArrowRight } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { aiApi } from '@/api'
import VideoAnalysisCard from '@/components/VideoAnalysisCard.vue'
import TranscriptPrint from '@/components/TranscriptPrint.vue'

const router = useRouter()
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const submissions = ref<any[]>([])
const loading = ref(false)
const detailDialogVisible = ref(false)
const selectedSubmission = ref<any>(null)

// 视频分析对话框
const videoAnalysisDialogVisible = ref(false)
const currentAnalysisSubmissionId = ref<number | null>(null)

// 打印成绩单
const printDialogVisible = ref(false)

// AI 成绩分析
const aiNarrativeLoading = ref(false)
const aiNarrative = ref('')
const aiNarrativeDisplayed = ref('')
let narrativeTimer: ReturnType<typeof setInterval> | null = null

// AI 画像数据
const profileData = ref<any>(null)
const profileLoading = ref(false)

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
      await fetchGrades()
    }
  } catch (error) {}
}

// 获取成绩列表
const fetchGrades = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const res: any = await api.get('/submissions/my', { params: { semester_id: selectedSemesterId.value } })
    // 只显示已经批改的（有分数的）
    submissions.value = res.filter((s: any) => s.total_score !== null && s.total_score !== undefined)
    
    // 有成绩数据时获取 AI 分析
    if (submissions.value.length > 0) {
      fetchAINarrative()
      fetchProfile()
    }
  } catch (error) {
    ElMessage.error('获取成绩失败')
  } finally {
    loading.value = false
  }
}

const handleSemesterChange = () => {
  aiNarrative.value = ''
  aiNarrativeDisplayed.value = ''
  profileData.value = null
  fetchGrades()
}

// 查看详情
const viewDetail = (submission: any) => {
  selectedSubmission.value = submission
  detailDialogVisible.value = true
}

// 打开文件
const openFile = (path: string) => {
  if (path) {
    window.open(`/uploads/${path}`, '_blank')
  }
}

// 查看视频分析
const viewVideoAnalysis = (submission: any) => {
  currentAnalysisSubmissionId.value = submission.id
  videoAnalysisDialogVisible.value = true
}

// 计算平均分
const averageScore = computed(() => {
  if (submissions.value.length === 0) return 0
  const sum = submissions.value.reduce((acc, s) => acc + (s.total_score || 0), 0)
  return (sum / submissions.value.length).toFixed(1)
})

// 最高分
const highestScore = computed(() => {
  if (submissions.value.length === 0) return 0
  return Math.max(...submissions.value.map(s => s.total_score || 0))
})

// 成绩趋势（对比前后两次）
const scoreTrend = computed(() => {
  if (submissions.value.length < 2) return { direction: 'stable' as const, diff: 0 }
  const sorted = [...submissions.value].sort((a, b) => 
    new Date(a.reviewed_at || a.created_at).getTime() - new Date(b.reviewed_at || b.created_at).getTime()
  )
  const last = sorted[sorted.length - 1].total_score || 0
  const prev = sorted[sorted.length - 2].total_score || 0
  const diff = last - prev
  return {
    direction: diff > 0 ? 'up' as const : diff < 0 ? 'down' as const : 'stable' as const,
    diff: Math.abs(diff)
  }
})

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

const fetchAINarrative = async () => {
  aiNarrativeLoading.value = true
  try {
    const approved = submissions.value.filter(s => s.status === 'approved').length
    const rejected = submissions.value.filter(s => s.status === 'rejected').length
    const avgLessonPlan = submissions.value
      .filter(s => s.lesson_plan_score != null)
      .reduce((acc, s, _, arr) => acc + (s.lesson_plan_score || 0) / arr.length, 0)
    const avgVideo = submissions.value
      .filter(s => s.video_score != null)
      .reduce((acc, s, _, arr) => acc + (s.video_score || 0) / arr.length, 0)
    
    const res = await aiApi.dataNarrative({
      role: 'student',
      stats: {
        submission_count: submissions.value.length,
        average_score: Number(averageScore.value),
        highest_score: highestScore.value,
        approved_count: approved,
        rejected_count: rejected,
        avg_lesson_plan_score: Math.round(avgLessonPlan),
        avg_video_score: Math.round(avgVideo),
        trend: scoreTrend.value.direction,
        trend_diff: scoreTrend.value.diff,
        context: '成绩分析报告'
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

// 获取 AI 画像（薄弱维度）
const fetchProfile = async () => {
  if (!selectedSemesterId.value) return
  profileLoading.value = true
  try {
    const res: any = await api.get('/profile/me', {
      params: { semester_id: selectedSemesterId.value }
    })
    profileData.value = res.success ? res.data : res
  } catch {
    profileData.value = null
  } finally {
    profileLoading.value = false
  }
}

// 薄弱维度（取最低的3个）
const weakDimensions = computed(() => {
  if (!profileData.value?.radar?.length) return []
  const sorted = [...profileData.value.radar].sort((a: any, b: any) => 
    (a.value ?? a.score ?? 0) - (b.value ?? b.score ?? 0)
  )
  return sorted.slice(0, 3).map((d: any) => ({
    label: d.label || d.name || '未知',
    score: Math.round(d.value ?? d.score ?? 0)
  }))
})

// 优势维度（取最高的2个）
const strongDimensions = computed(() => {
  if (!profileData.value?.radar?.length) return []
  const sorted = [...profileData.value.radar].sort((a: any, b: any) => 
    (b.value ?? b.score ?? 0) - (a.value ?? a.score ?? 0)
  )
  return sorted.slice(0, 2).map((d: any) => ({
    label: d.label || d.name || '未知',
    score: Math.round(d.value ?? d.score ?? 0)
  }))
})

onMounted(fetchSemesters)
</script>

<template>
  <div class="grades-page" v-loading="loading">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">
          <el-icon class="title-icon"><TrendCharts /></el-icon>
          我的成绩
        </h2>
        <p class="page-desc">查看作业成绩、AI 分析和能力诊断</p>
      </div>
      <div class="header-actions">
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
        <el-button v-if="submissions.length > 0" :icon="Printer" @click="printDialogVisible = true">打印成绩单</el-button>
      </div>
    </div>

    <el-alert v-if="semesters.length === 0" type="info" :closable="false" class="mb-6">
      当前没有试讲批次
    </el-alert>

    <div v-else>
      <!-- 统计卡片 -->
      <div v-if="submissions.length > 0" class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon bg-blue"><el-icon :size="22"><Document /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-blue">{{ submissions.length }}</div>
            <div class="stat-label">已批改作业</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon bg-green"><el-icon :size="22"><TrendCharts /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-green">{{ averageScore }}</div>
            <div class="stat-label">平均分</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon bg-amber"><el-icon :size="22"><Aim /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-amber">{{ highestScore }}</div>
            <div class="stat-label">最高分</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" :class="scoreTrend.direction === 'up' ? 'bg-green' : scoreTrend.direction === 'down' ? 'bg-red' : 'bg-gray'">
            <span class="trend-arrow">{{ scoreTrend.direction === 'up' ? '↑' : scoreTrend.direction === 'down' ? '↓' : '→' }}</span>
          </div>
          <div class="stat-body">
            <div class="stat-value" :class="scoreTrend.direction === 'up' ? 'text-green' : scoreTrend.direction === 'down' ? 'text-red' : 'text-gray'">{{ scoreTrend.direction === 'stable' ? '持平' : (scoreTrend.direction === 'up' ? '+' : '-') + scoreTrend.diff }}</div>
            <div class="stat-label">成绩趋势</div>
          </div>
        </div>
      </div>

      <!-- AI 成绩分析叙事 -->
      <div v-if="(aiNarrative || aiNarrativeLoading) && submissions.length > 0" class="ai-narrative-card">
        <div class="ai-narrative-inner">
          <div class="ai-narrative-icon">
            <el-icon :size="22" color="#0891b2"><Cpu /></el-icon>
          </div>
          <div class="ai-narrative-body">
            <div class="ai-narrative-label">
              <span class="font-bold text-gray-800 text-sm">AI 成绩分析</span>
              <div class="ai-tag">
                <span class="ai-tag-dot"></span>
                <span>AI 生成</span>
              </div>
            </div>
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="ai-narrative-text text-gray-400 text-sm mt-1">
              AI 正在分析你的成绩数据...
            </div>
            <div v-else class="ai-narrative-text text-gray-600 text-sm mt-1">
              {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="typing-dot">|</span>
            </div>
          </div>
        </div>
      </div>

      <!-- AI 能力诊断区域 -->
      <div v-if="(weakDimensions.length > 0 || strongDimensions.length > 0) && submissions.length > 0" class="ai-diagnosis-row">
        <!-- 薄弱维度 -->
        <div v-if="weakDimensions.length > 0" class="diagnosis-card weak">
          <div class="diagnosis-header">
            <div class="diagnosis-icon weak"><el-icon :size="16"><Aim /></el-icon></div>
            <span class="diagnosis-title">AI 薄弱维度诊断</span>
            <div class="ai-tag small">
              <span class="ai-tag-dot"></span>
              <span>AI</span>
            </div>
          </div>
          <div class="dimension-list">
            <div v-for="dim in weakDimensions" :key="dim.label" class="dimension-item">
              <span class="dim-label">{{ dim.label }}</span>
              <div class="dim-bar-wrap">
                <div class="dim-bar weak" :style="{ width: dim.score + '%' }"></div>
              </div>
              <span class="dim-score weak">{{ dim.score }}</span>
            </div>
          </div>
          <el-button text type="primary" size="small" class="mt-2" @click="router.push('/student/learning-path')">
            查看提升路径 <el-icon class="ml-1"><ArrowRight /></el-icon>
          </el-button>
        </div>
        <!-- 优势维度 -->
        <div v-if="strongDimensions.length > 0" class="diagnosis-card strong">
          <div class="diagnosis-header">
            <div class="diagnosis-icon strong"><el-icon :size="16"><MagicStick /></el-icon></div>
            <span class="diagnosis-title">优势能力</span>
          </div>
          <div class="dimension-list">
            <div v-for="dim in strongDimensions" :key="dim.label" class="dimension-item">
              <span class="dim-label">{{ dim.label }}</span>
              <div class="dim-bar-wrap">
                <div class="dim-bar strong" :style="{ width: dim.score + '%' }"></div>
              </div>
              <span class="dim-score strong">{{ dim.score }}</span>
            </div>
          </div>
          <el-button text type="primary" size="small" class="mt-2" @click="router.push('/student/my-profile')">
            查看完整画像 <el-icon class="ml-1"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 成绩列表 -->
      <div class="table-card">
        <div class="table-card-header">
          <div class="table-card-title">
            <span class="title-bar"></span>
            <span>成绩明细</span>
          </div>
        </div>
        <el-empty v-if="submissions.length === 0 && !loading" description="暂无成绩记录" />
        <div v-else class="grades-table-container">
        <el-table :data="submissions" v-loading="loading" stripe>
          <el-table-column prop="task_title" label="作业名称" min-width="180" />
          <el-table-column label="教案分数" width="100" align="center">
            <template #default="scope">
              <span v-if="scope.row.lesson_plan_score !== null" class="font-bold text-blue-600">
                {{ scope.row.lesson_plan_score }}
              </span>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="视频分数" width="100" align="center">
            <template #default="scope">
              <span v-if="scope.row.video_score !== null" class="font-bold text-green-600">
                {{ scope.row.video_score }}
              </span>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="总分" width="100" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.total_score >= 60 ? 'success' : 'danger'" size="large" class="font-bold">
                {{ scope.row.total_score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="scope">
              <el-tag v-if="scope.row.status === 'approved'" type="success">已通过</el-tag>
              <el-tag v-else-if="scope.row.status === 'rejected'" type="danger">已驳回</el-tag>
              <el-tag v-else type="warning">待批改</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="批改时间" width="160">
            <template #default="scope">
              <span v-if="scope.row.reviewed_at" class="text-xs text-gray-500">
                {{ new Date(scope.row.reviewed_at).toLocaleString('zh-CN') }}
              </span>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="视频分析" width="100">
            <template #default="scope">
              <el-button 
                v-if="scope.row.video_path" 
                size="small"
                type="primary"
                link
                @click="viewVideoAnalysis(scope.row)"
              >
                <el-icon class="mr-1"><View /></el-icon>
                查看
              </el-button>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button size="small" type="primary" @click="viewDetail(scope.row)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        </div>
      </div>
    </div>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="成绩详情" width="700px">
      <div v-if="selectedSubmission">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="作业名称" :span="2">
            <span class="font-bold">{{ selectedSubmission.task_title }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="教案文件">
            <div v-if="selectedSubmission.lesson_plan_name" class="flex items-center gap-2">
              <el-icon class="text-red-500"><Document /></el-icon>
              <span 
                class="text-sm cursor-pointer hover:text-blue-600 hover:underline" 
                @click="openFile(selectedSubmission.lesson_plan_path)"
              >
                {{ selectedSubmission.lesson_plan_name }}
              </span>
            </div>
            <span v-else class="text-gray-400">未上传</span>
          </el-descriptions-item>
          <el-descriptions-item label="教案分数">
            <span v-if="selectedSubmission.lesson_plan_score !== null" class="text-lg font-bold text-blue-600">
              {{ selectedSubmission.lesson_plan_score }}
            </span>
            <span v-else class="text-gray-400">未批改</span>
          </el-descriptions-item>
          <el-descriptions-item label="视频文件">
            <div v-if="selectedSubmission.video_name" class="flex items-center gap-2">
              <el-icon class="text-blue-500"><VideoCamera /></el-icon>
              <span 
                class="text-sm cursor-pointer hover:text-blue-600 hover:underline" 
                @click="openFile(selectedSubmission.video_path)"
              >
                {{ selectedSubmission.video_name }}
              </span>
            </div>
            <span v-else class="text-gray-400">未上传</span>
          </el-descriptions-item>
          <el-descriptions-item label="视频分数">
            <span v-if="selectedSubmission.video_score !== null" class="text-lg font-bold text-green-600">
              {{ selectedSubmission.video_score }}
            </span>
            <span v-else class="text-gray-400">未批改</span>
          </el-descriptions-item>
          <el-descriptions-item label="总分" :span="2">
            <el-tag :type="selectedSubmission.total_score >= 60 ? 'success' : 'danger'" size="large" class="font-bold text-xl">
              {{ selectedSubmission.total_score }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag v-if="selectedSubmission.status === 'approved'" type="success">已通过</el-tag>
            <el-tag v-else-if="selectedSubmission.status === 'rejected'" type="danger">已驳回</el-tag>
            <el-tag v-else type="warning">待批改</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="批改时间">
            <span v-if="selectedSubmission.reviewed_at">
              {{ new Date(selectedSubmission.reviewed_at).toLocaleString('zh-CN') }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="mt-4">
          <div class="flex items-center gap-2 mb-2">
            <el-icon class="text-blue-600"><ChatLineSquare /></el-icon>
            <span class="font-bold text-gray-700">导师评价</span>
          </div>
          <el-card shadow="never" class="bg-gray-50">
            <div v-if="selectedSubmission.feedback" class="text-sm text-gray-700 whitespace-pre-wrap">
              {{ selectedSubmission.feedback }}
            </div>
            <div v-else class="text-sm text-gray-400 text-center py-4">
              暂无评价
            </div>
          </el-card>
        </div>

        <div v-if="selectedSubmission.student_remark" class="mt-4">
          <div class="font-bold text-gray-700 mb-2">提交备注</div>
          <el-card shadow="never" class="bg-blue-50">
            <div class="text-sm text-gray-700 whitespace-pre-wrap">
              {{ selectedSubmission.student_remark }}
            </div>
          </el-card>
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 视频分析对话框 -->
    <el-dialog
      v-model="videoAnalysisDialogVisible"
      title="视频AI分析报告"
      width="900px"
      top="5vh"
    >
      <VideoAnalysisCard
        v-if="currentAnalysisSubmissionId"
        :submission-id="currentAnalysisSubmissionId"
        :can-trigger="true"
        :can-reanalyze="false"
      />
      
      <template #footer>
        <el-button @click="videoAnalysisDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 打印成绩单 -->
    <TranscriptPrint 
      v-model:visible="printDialogVisible"
      :semester-id="selectedSemesterId ?? undefined"
    />
  </div>
</template>

<style scoped>
.grades-page {
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

.title-icon {
  color: #0891b2;
}

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

.trend-arrow {
  font-size: 22px;
  font-weight: 700;
}

.stat-body {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
}

.stat-value.text-blue { color: #3b82f6; }
.stat-value.text-green { color: #10b981; }
.stat-value.text-amber { color: #f59e0b; }
.stat-value.text-red { color: #ef4444; }
.stat-value.text-gray { color: #6b7280; }

.stat-label {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

/* AI Narrative Card */
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

.ai-narrative-body {
  flex: 1;
  min-width: 0;
}

.ai-narrative-label {
  display: flex;
  align-items: center;
}

.ai-narrative-text {
  line-height: 1.7;
}

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

.ai-tag.small {
  padding: 1px 8px;
  font-size: 10px;
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

/* AI Diagnosis Row */
.ai-diagnosis-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

@media (max-width: 768px) {
  .ai-diagnosis-row { grid-template-columns: 1fr; }
}

.diagnosis-card {
  background: white;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.diagnosis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.diagnosis-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.diagnosis-icon.weak { background: #fef2f2; color: #ef4444; }
.diagnosis-icon.strong { background: #ecfdf5; color: #10b981; }

.diagnosis-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dim-label {
  font-size: 13px;
  color: #64748b;
  width: 80px;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dim-bar-wrap {
  flex: 1;
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.dim-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}

.dim-bar.weak { background: #ef4444; }
.dim-bar.strong { background: #10b981; }

.dim-score {
  font-size: 13px;
  font-weight: 700;
  width: 32px;
  text-align: right;
}

.dim-score.weak { color: #ef4444; }
.dim-score.strong { color: #10b981; }

/* Table Card */
.table-card {
  background: white;
  border-radius: 14px;
  border: 1px solid #f1f5f9;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.table-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.table-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.title-bar {
  width: 3px;
  height: 16px;
  background: #0891b2;
  border-radius: 2px;
}

.grades-table-container {
  max-height: 500px;
  overflow-y: auto;
}

.mr-1 {
  margin-right: 4px;
}
</style>
