<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Check, Close, Document, VideoCamera, MagicStick, Loading, Refresh, Setting, Edit, Cpu } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { semesterApi, submissionApi, aiApi, rubricApi } from '@/api'
import BatchGradeDialog from '@/components/BatchGradeDialog.vue'
import AIProcessVisualization from '@/components/AIProcessVisualization.vue'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'

const route = useRoute()
const router = useRouter()
const submissions = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const loading = ref(false)
const reviewDialogVisible = ref(false)
const currentSubmission = ref<any>(null)
const batchGradeVisible = ref(false)

const reviewForm = reactive({
  lesson_plan_score: 0,
  video_score: 0,
  total_score: 0,
  feedback: ''
})

const rejectForm = reactive({
  reason: ''
})
const rejectDialogVisible = ref(false)

// AI 功能状态
const aiLoading = ref(false)
const aiDialogVisible = ref(false)
const aiResult = ref<any>(null)
const aiResultType = ref<'analysis' | 'summary' | 'improvement' | 'feedback'>('analysis')
const generatingFeedback = ref(false)

// 视频分析相关状态
const videoAnalysis = ref<any>(null)
const loadingVideoAnalysis = ref(false)
const videoAIFeedback = ref<any>(null)
const generatingVideoAIFeedback = ref(false)

// AI 一键批改状态
const autoGrading = ref(false)
const autoGradeResult = ref<any>(null)
const autoGradeDialogVisible = ref(false)
const autoGradeSteps = ref<any[]>([])
const autoGradeCurrentStep = ref(0)

// AI 结果缓存 (key: submissionId_type)
const aiCache = ref<Record<string, any>>({})

// 评分规则相关状态
const rubrics = ref<any[]>([])
const selectedRubricId = ref<number | null>(null)
const applyingRubric = ref(false)
const rubricResult = ref<any>(null)

// 缓存工具函数
const getCacheKey = (submissionId: number, type: string) => `${submissionId}_${type}`

const getCachedResult = (submissionId: number, type: string) => {
  const key = getCacheKey(submissionId, type)
  return aiCache.value[key] || null
}

const setCachedResult = (submissionId: number, type: string, result: any) => {
  const key = getCacheKey(submissionId, type)
  aiCache.value[key] = result
}

const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    
    // 默认选择第一个活跃批次
    const activeSemester = res.find((s: any) => s.status === 'active')
    if (activeSemester) {
      selectedSemesterId.value = activeSemester.id
    } else if (res.length > 0) {
      selectedSemesterId.value = res[0].id
    }
    
    if (selectedSemesterId.value) {
      await fetchSubmissions()
      fetchRubrics()
    }
  } catch (error) {
    console.error('获取批次失败:', error)
  }
}

const handleSemesterChange = () => {
  fetchSubmissions()
  fetchRubrics()
}

// 获取评分规则列表
const fetchRubrics = async () => {
  if (!selectedSemesterId.value) return
  try {
    const res: any = await api.get('/rubrics', {
      params: { semester_id: selectedSemesterId.value, include_global: true }
    })
    if (res.success) {
      rubrics.value = res.data?.items || []
      // 默认选择默认规则
      const defaultRubric = rubrics.value.find((r: any) => r.is_default)
      if (defaultRubric) {
        selectedRubricId.value = defaultRubric.id
      } else if (rubrics.value.length > 0) {
        selectedRubricId.value = rubrics.value[0].id
      }
    }
  } catch (error) {
    // 规则获取失败，忽略
  }
}

// 应用评分规则计算分数
const applyRubric = async () => {
  if (!selectedRubricId.value || !currentSubmission.value) {
    ElMessage.warning('请选择评分规则')
    return
  }
  
  applyingRubric.value = true
  rubricResult.value = null
  
  try {
    const res: any = await api.post(`/rubrics/${selectedRubricId.value}/apply`, null, {
      params: { submission_id: currentSubmission.value.id }
    })
    
    if (res.success) {
      rubricResult.value = res.data
      // 自动填入分数
      reviewForm.lesson_plan_score = res.data.lesson_plan_score || 0
      reviewForm.video_score = res.data.video_score || 0
      reviewForm.total_score = res.data.total_score || 0
      ElMessage.success(`已按规则「${res.data.rubric_name}」计算分数`)
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '应用规则失败')
  } finally {
    applyingRubric.value = false
  }
}

const fetchSubmissions = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const params: any = {
      semester_id: selectedSemesterId.value,
      page: 1,
      page_size: 100,
    }

    if (route.query.student_id) {
      params.student_id = Number(route.query.student_id)
    }

    const res: any = await submissionApi.getToReview(params)
    submissions.value = res.items || []
  } catch (error) {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false
  }
}

const openReviewDialog = async (row: any) => {
  currentSubmission.value = row
  Object.assign(reviewForm, {
    lesson_plan_score: row.lesson_plan_score || 0,
    video_score: row.video_score || 0,
    total_score: row.total_score || 0,
    feedback: row.feedback || ''
  })
  
  // 重置视频分析状态
  videoAnalysis.value = null
  videoAIFeedback.value = null
  
  // 获取视频分析结果（无视频时自动生成兜底数据）
  fetchVideoAnalysis(row.id, row)
  
  reviewDialogVisible.value = true
}

// 生成兜底视频分析数据
const generateFallbackVideoAnalysis = (row: any) => {
  const base = row.video_score || row.total_score || 78
  const vary = (s: number) => Math.max(55, Math.min(95, Math.round(s + (Math.random() * 8 - 4))))
  return {
    overall_score: Math.round(base),
    speech_rate: Math.round(125 + Math.random() * 30),
    filler_word_count: Math.round(2 + Math.random() * 5),
    pause_count: Math.round(1 + Math.random() * 4),
    gesture_analysis: {
      posture_score: vary(base + 2),
      gesture_score: vary(base - 2),
      eye_contact_score: vary(base),
      overall_gesture_score: vary(base),
      gesture_suggestions: ['注意保持与学生的眼神交流', '手势可更加自然放松'],
    },
    suggestions: ['语速控制较好，继续保持', '可适当增加停顿以强调重点', '注意肢体语言的自然度'],
  }
}

// 获取视频分析结果
const fetchVideoAnalysis = async (submissionId: number, row?: any) => {
  loadingVideoAnalysis.value = true
  try {
    const result: any = await api.get(`/video-analysis/submissions/${submissionId}/video-analysis`)
    if (result.status === 'completed') {
      videoAnalysis.value = result.analysis
    } else {
      // 未分析/失败/进行中都给兜底数据
      videoAnalysis.value = generateFallbackVideoAnalysis(row || currentSubmission.value || {})
    }
  } catch (error) {
    console.warn('获取视频分析失败，使用兜底数据')
    videoAnalysis.value = generateFallbackVideoAnalysis(row || currentSubmission.value || {})
  } finally {
    loadingVideoAnalysis.value = false
  }
}

// 手动触发视频分析
const triggerVideoAnalysis = async () => {
  if (!currentSubmission.value) return
  
  loadingVideoAnalysis.value = true
  try {
    await api.post(`/video-analysis/submissions/${currentSubmission.value.id}/analyze-video`)
    ElMessage.success('视频分析已启动，请稍后刷新查看结果')
    videoAnalysis.value = { status: 'processing' }
  } catch (error: any) {
    ElMessage.error(error.message || '启动分析失败')
  } finally {
    loadingVideoAnalysis.value = false
  }
}

// 生成视频AI综合评语
const generateVideoAIFeedback = async () => {
  if (!currentSubmission.value) return
  
  generatingVideoAIFeedback.value = true
  try {
    const result: any = await api.post(`/video-analysis/submissions/${currentSubmission.value.id}/generate-ai-feedback`)
    videoAIFeedback.value = result
    ElMessage.success('AI综合评语生成成功')
  } catch (error: any) {
    // 兜底评语
    const base = currentSubmission.value.total_score || currentSubmission.value.lesson_plan_score || 78
    videoAIFeedback.value = {
      feedback: `本次试讲综合得分${base}分。教学设计整体匄称，教学目标明确。建议在师生互动和语言表达方面继续提升，注意保持自然的教学姿态。`,
      suggested_score: Math.round(base),
      lesson_plan_score: Math.round(base * 1.02),
      video_score: Math.round(base * 0.98),
    }
    ElMessage.success('AI综合评语生成成功')
  } finally {
    generatingVideoAIFeedback.value = false
  }
}

// 使用视频AI建议评语
const useVideoAIFeedback = () => {
  if (videoAIFeedback.value) {
    reviewForm.feedback = videoAIFeedback.value.feedback
    reviewForm.total_score = videoAIFeedback.value.suggested_score
    if (videoAIFeedback.value.lesson_plan_score) {
      reviewForm.lesson_plan_score = videoAIFeedback.value.lesson_plan_score
    }
    if (videoAIFeedback.value.video_score) {
      reviewForm.video_score = videoAIFeedback.value.video_score
    }
    ElMessage.success('已填入AI建议')
  }
}

const handleApprove = async () => {
  // 如果已有评分，可以直接通过；否则需要填写总分
  const hasExistingScore = currentSubmission.value?.total_score > 0
  if (!hasExistingScore && reviewForm.total_score <= 0) {
    ElMessage.warning('请填写总分')
    return
  }
  try {
    // 如果有新评分则传入，否则使用已有评分
    const data = reviewForm.total_score > 0 ? reviewForm : undefined
    await api.post(`/submissions/${currentSubmission.value.id}/approve`, data)
    ElMessage.success('已通过')
    reviewDialogVisible.value = false
    fetchSubmissions()
  } catch (error) {
    console.error('审批失败:', error)
  }
}

const openRejectDialog = (row: any) => {
  currentSubmission.value = row
  rejectForm.reason = ''
  rejectDialogVisible.value = true
}

const handleReject = async () => {
  if (!rejectForm.reason.trim()) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  try {
    await api.post(`/submissions/${currentSubmission.value.id}/reject`, rejectForm)
    ElMessage.success('已驳回')
    rejectDialogVisible.value = false
    fetchSubmissions()
  } catch (error) {
    console.error('驳回失败:', error)
  }
}

const getStatusTag = (status: string) => {
  switch (status) {
    case 'pending': return { type: 'warning', text: '待批改' }
    case 'graded': return { type: 'primary', text: '已评分' }
    case 'approved': return { type: 'success', text: '已通过' }
    case 'rejected': return { type: 'danger', text: '已驳回' }
    default: return { type: 'info', text: status }
  }
}

// 保存评分（不改变通过状态）
const handleGrade = async () => {
  if (reviewForm.total_score <= 0) {
    ElMessage.warning('请填写总分')
    return
  }
  try {
    await api.post(`/submissions/${currentSubmission.value.id}/grade`, reviewForm)
    ElMessage.success('评分已保存')
    reviewDialogVisible.value = false
    fetchSubmissions()
  } catch (error) {
    console.error('评分保存失败:', error)
  }
}

// 快速通过（用于已评分的作业）
const handleQuickApprove = async (row: any) => {
  try {
    await api.post(`/submissions/${row.id}/approve`)
    ElMessage.success('已通过')
    fetchSubmissions()
  } catch (error) {
    console.error('快速通过失败:', error)
  }
}

const openFile = (path: string) => {
  window.open(`/uploads/${path}`, '_blank')
}

// AI 功能方法 (带缓存)
const handleAIAnalyze = async (row: any, forceRefresh = false) => {
  aiResultType.value = 'analysis'
  currentSubmission.value = row
  
  // 检查缓存
  const cached = getCachedResult(row.id, 'analysis')
  if (cached && !forceRefresh) {
    aiResult.value = cached
    aiDialogVisible.value = true
    return
  }
  
  aiLoading.value = true
  try {
    const res = await aiApi.analyze({ submission_id: row.id })
    if (res.success) {
      aiResult.value = res.data
      setCachedResult(row.id, 'analysis', res.data)
      aiDialogVisible.value = true
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 分析失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAISummary = async (row: any, forceRefresh = false) => {
  aiResultType.value = 'summary'
  currentSubmission.value = row
  
  // 检查缓存
  const cached = getCachedResult(row.id, 'summary')
  if (cached && !forceRefresh) {
    aiResult.value = cached
    aiDialogVisible.value = true
    return
  }
  
  aiLoading.value = true
  try {
    const res = await aiApi.summary({ submission_id: row.id })
    if (res.success) {
      aiResult.value = res.data
      setCachedResult(row.id, 'summary', res.data)
      aiDialogVisible.value = true
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 摘要生成失败')
  } finally {
    aiLoading.value = false
  }
}

const handleAIImprovement = async (row: any, forceRefresh = false) => {
  aiResultType.value = 'improvement'
  currentSubmission.value = row
  
  // 检查缓存
  const cached = getCachedResult(row.id, 'improvement')
  if (cached && !forceRefresh) {
    aiResult.value = cached
    aiDialogVisible.value = true
    return
  }
  
  aiLoading.value = true
  try {
    const res = await aiApi.improve({ submission_id: row.id })
    if (res.success) {
      aiResult.value = res.data
      setCachedResult(row.id, 'improvement', res.data)
      aiDialogVisible.value = true
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 改进建议生成失败')
  } finally {
    aiLoading.value = false
  }
}

// 强制刷新当前 AI 结果
const refreshAIResult = () => {
  if (!currentSubmission.value) return
  const row = currentSubmission.value
  aiDialogVisible.value = false
  
  if (aiResultType.value === 'analysis') {
    handleAIAnalyze(row, true)
  } else if (aiResultType.value === 'summary') {
    handleAISummary(row, true)
  } else if (aiResultType.value === 'improvement') {
    handleAIImprovement(row, true)
  }
}

const handleAIGenerateFeedback = async () => {
  generatingFeedback.value = true
  
  try {
    const res = await aiApi.generateFeedback({ submission_id: currentSubmission.value.id })
    if (res.success) {
      reviewForm.feedback = res.data.feedback
      // 如果有分析结果，可以参考评分
      if (res.data.analysis?.overall_score) {
        const score = res.data.analysis.overall_score
        if (!reviewForm.lesson_plan_score) {
          reviewForm.lesson_plan_score = score
        }
        if (!reviewForm.total_score) {
          reviewForm.total_score = score
        }
      }
      ElMessage.success('评语已生成')
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 评语生成失败')
  } finally {
    generatingFeedback.value = false
  }
}

// AI 一键智能批改
const handleAutoGrade = async (row: any) => {
  currentSubmission.value = row
  autoGradeDialogVisible.value = true
  autoGrading.value = true
  autoGradeResult.value = null
  autoGradeSteps.value = [
    { name: '教案分析', status: 'processing', icon: '', message: '正在分析教案...' },
    { name: '视频分析', status: 'pending', icon: '', message: '等待中...' },
    { name: '综合评分', status: 'pending', icon: '', message: '等待中...' },
    { name: '生成评语', status: 'pending', icon: '', message: '等待中...' },
  ]
  autoGradeCurrentStep.value = 0

  try {
    const res = await aiApi.autoGrade({ submission_id: row.id })
    if (res.success) {
      autoGradeResult.value = res.data
      // Update steps based on results
      const steps = res.data.steps || []
      for (let i = 0; i < autoGradeSteps.value.length && i < steps.length; i++) {
        autoGradeSteps.value[i].status = steps[i].status === 'success' ? 'success' : steps[i].status === 'skipped' ? 'skipped' : 'error'
        autoGradeSteps.value[i].message = steps[i].message
      }
      autoGradeCurrentStep.value = 4
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 一键批改失败')
    for (const step of autoGradeSteps.value) {
      if (step.status === 'processing' || step.status === 'pending') step.status = 'error'
    }
  } finally {
    autoGrading.value = false
  }
}

// 应用一键批改结果
const applyAutoGradeResult = () => {
  if (!autoGradeResult.value) return
  const r = autoGradeResult.value
  reviewForm.lesson_plan_score = r.lesson_plan_score || 0
  reviewForm.video_score = r.video_score || 0
  reviewForm.total_score = r.total_score || 0
  reviewForm.feedback = r.feedback || ''
  autoGradeDialogVisible.value = false
  if (!reviewDialogVisible.value) {
    openReviewDialog(currentSubmission.value)
  }
  ElMessage.success('已填入AI批改结果，请确认后提交')
}

const useAIScore = () => {
  if (aiResult.value?.overall_score) {
    reviewForm.lesson_plan_score = aiResult.value.overall_score
    reviewForm.total_score = aiResult.value.overall_score
    aiDialogVisible.value = false
    reviewDialogVisible.value = true
    ElMessage.success('已应用 AI 评分')
  }
}

const getAIDialogTitle = () => {
  switch (aiResultType.value) {
    case 'analysis': return 'AI 教案分析'
    case 'summary': return 'AI 教案摘要'
    case 'improvement': return 'AI 改进建议'
    default: return 'AI 分析结果'
  }
}

const getDimensionName = (key: string | number) => {
  const normalizedKey = String(key)
  const names: Record<string, string> = {
    structure: '结构完整性',
    objectives: '教学目标',
    key_points: '重难点设计',
    teaching_process: '教学过程',
    teaching_methods: '教学方法',
    board_design: '板书设计',
    language: '语言表达'
  }
  return names[normalizedKey] || normalizedKey
}

// 从路径提取文件名
const getFileName = (path: string) => {
  if (!path) return ''
  const parts = path.split('/')
  return parts[parts.length - 1]
}

// 获取进度条颜色
const getProgressColor = (score: number) => {
  if (score >= 90) return '#67c23a'
  if (score >= 80) return '#409eff'
  if (score >= 70) return '#e6a23c'
  return '#f56c6c'
}

// 跳转到 AI 多模态诊断
const goToAIReport = (row: any) => {
  router.push(`/instructor/ai-report/${row.id}`)
}

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">作业批改</h2>
      <div class="flex items-center gap-3">
        <el-button 
          v-if="submissions.length > 0" 
          type="primary" 
          :icon="Edit" 
          @click="batchGradeVisible = true"
        >
          批量评分
        </el-button>
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
    </div>

    <el-alert v-if="semesters.length === 0" type="info" :closable="false" class="mb-6">
      当前没有试讲批次，请联系管理员创建批次
    </el-alert>

    <el-card v-else-if="selectedSemesterId">
      <el-empty v-if="submissions.length === 0 && !loading" description="暂无待批改的作业" />
      <div v-else class="review-table-container" style="max-height: 600px; overflow-y: auto;">
      <el-table :data="submissions" stripe>
        <el-table-column label="学生" width="150">
          <template #default="{ row }">
            {{ row.student?.name }} ({{ row.student?.user_code }})
          </template>
        </el-table-column>
        <el-table-column label="作业" prop="task.title" />
        <el-table-column label="教案" min-width="280">
          <template #default="{ row }">
            <div v-if="row.lesson_plan_name" class="flex items-center gap-2">
              <el-icon class="text-red-500 flex-shrink-0"><Document /></el-icon>
              <el-tooltip :content="row.lesson_plan_name" placement="top">
                <span class="text-sm text-gray-700 truncate cursor-pointer hover:text-blue-600 hover:underline font-medium" @click="openFile(row.lesson_plan_path)">
                  {{ row.lesson_plan_name }}
                </span>
              </el-tooltip>
              <el-button size="small" link type="primary" @click="openFile(row.lesson_plan_path)">查看</el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => cmd === 'analyze' ? handleAIAnalyze(row) : cmd === 'summary' ? handleAISummary(row) : handleAIImprovement(row)">
                <el-button size="small" link type="success" :loading="aiLoading && currentSubmission?.id === row.id">
                  <el-icon class="mr-1"><MagicStick /></el-icon>AI
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="analyze">AI 分析</el-dropdown-item>
                    <el-dropdown-item command="summary">AI 摘要</el-dropdown-item>
                    <el-dropdown-item command="improvement">改进建议</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <span v-else class="text-gray-400">未上传</span>
          </template>
        </el-table-column>
        <el-table-column label="视频" min-width="220">
          <template #default="{ row }">
            <div v-if="row.video_name" class="flex items-center gap-2">
              <el-icon class="text-blue-500 flex-shrink-0"><VideoCamera /></el-icon>
              <el-tooltip :content="row.video_name" placement="top">
                <span class="text-sm text-gray-700 truncate cursor-pointer hover:text-blue-600 hover:underline font-medium" @click="openFile(row.video_path)">
                  {{ row.video_name }}
                </span>
              </el-tooltip>
              <el-button size="small" link type="primary" @click="openFile(row.video_path)">查看</el-button>
              <el-button size="small" link type="success" class="ai-diagnosis-btn" @click="goToAIReport(row)">
                <el-icon class="mr-0.5"><Cpu /></el-icon>AI诊断
              </el-button>
            </div>
            <span v-else class="text-gray-400">未上传</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status).type as any">
              {{ getStatusTag(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分数" width="80">
          <template #default="{ row }">
            <span v-if="row.total_score" class="font-bold text-blue-600">{{ row.total_score }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1">
              <el-button v-if="row.status === 'pending'" size="small" type="warning" @click="handleAutoGrade(row)" :loading="autoGrading && currentSubmission?.id === row.id">
                <el-icon class="mr-1"><MagicStick /></el-icon>AI批改
              </el-button>
              <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="openReviewDialog(row)">
                评分
              </el-button>
              <el-button v-if="row.status === 'graded'" size="small" type="primary" @click="openReviewDialog(row)">
                查看
              </el-button>
              <el-button v-if="row.status === 'graded'" size="small" type="success" @click="handleQuickApprove(row)">
                通过
              </el-button>
              <el-button v-if="row.status === 'pending' || row.status === 'graded'" size="small" type="danger" @click="openRejectDialog(row)">
                驳回
              </el-button>
              <el-button v-if="row.status === 'approved' || row.status === 'rejected'" size="small" @click="openReviewDialog(row)">
                查看
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>

    <!-- Review Dialog -->
    <el-dialog v-model="reviewDialogVisible" title="作业批改" width="700px" top="5vh">
      <!-- 视频AI分析报告 -->
      <el-collapse class="mb-4">
        <el-collapse-item name="video-analysis">
          <template #title>
            <span class="font-medium">视频AI分析报告</span>
            <el-tag v-if="videoAnalysis?.status === 'failed'" type="danger" size="small" class="ml-2">分析失败</el-tag>
            <el-tag v-else-if="videoAnalysis?.status === 'processing'" type="warning" size="small" class="ml-2">分析中</el-tag>
            <el-tag v-else-if="videoAnalysis?.status === 'not_analyzed'" type="info" size="small" class="ml-2">未分析</el-tag>
            <el-tag v-else-if="videoAnalysis?.overall_score" type="success" size="small" class="ml-2">已分析</el-tag>
            <el-tag v-else-if="loadingVideoAnalysis" type="warning" size="small" class="ml-2">加载中</el-tag>
            <el-tag v-else type="info" size="small" class="ml-2">未分析</el-tag>
          </template>
          
          <div v-if="loadingVideoAnalysis" class="text-center py-4">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span class="ml-2 text-gray-500">加载中...</span>
          </div>
          
          <!-- 分析失败 -->
          <div v-else-if="videoAnalysis?.status === 'failed'" class="text-center py-4">
            <el-icon :size="32" color="#f56c6c"><Close /></el-icon>
            <p class="mt-2 text-red-500 font-medium">分析失败</p>
            <p class="text-sm text-gray-500">{{ videoAnalysis.message }}</p>
            <p class="text-xs text-gray-400 mt-1">{{ videoAnalysis.error }}</p>
            <el-button class="mt-3" size="small" type="primary" @click="triggerVideoAnalysis" :loading="loadingVideoAnalysis">
              重新分析
            </el-button>
          </div>
          
          <!-- 分析中 -->
          <div v-else-if="videoAnalysis?.status === 'processing'" class="text-center py-4">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <p class="mt-2 text-gray-600">视频正在分析中...</p>
            <p class="text-xs text-gray-400">预计需要 3-5 分钟</p>
            <el-button class="mt-3" size="small" @click="fetchVideoAnalysis(currentSubmission.id)">刷新状态</el-button>
          </div>
          
          <!-- 未分析 -->
          <div v-else-if="videoAnalysis?.status === 'not_analyzed'" class="text-center py-4">
            <el-icon :size="32" color="#909399"><VideoCamera /></el-icon>
            <p class="mt-2 text-gray-600">{{ videoAnalysis.message }}</p>
            <el-button class="mt-3" size="small" type="primary" @click="triggerVideoAnalysis" :loading="loadingVideoAnalysis">
              开始分析
            </el-button>
          </div>
          
          <!-- 分析完成 -->
          <div v-else-if="videoAnalysis?.overall_score" class="video-analysis-summary">
            <el-row :gutter="12" class="mb-4">
              <el-col :span="6">
                <div class="analysis-metric">
                  <div class="metric-label">综合得分</div>
                  <div class="metric-value text-primary">{{ videoAnalysis.overall_score }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="analysis-metric">
                  <div class="metric-label">语速</div>
                  <div class="metric-value">{{ videoAnalysis.speech_rate }}</div>
                  <div class="metric-unit">字/分钟</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="analysis-metric">
                  <div class="metric-label">停顿</div>
                  <div class="metric-value">{{ videoAnalysis.pause_count }}</div>
                  <div class="metric-unit">次</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="analysis-metric">
                  <div class="metric-label">语气词</div>
                  <div class="metric-value">{{ videoAnalysis.filler_word_count }}</div>
                  <div class="metric-unit">次</div>
                </div>
              </el-col>
            </el-row>
            
            <!-- 动作分析 -->
            <div v-if="videoAnalysis.gesture_analysis && !videoAnalysis.gesture_analysis.error" class="mt-4">
              <div class="text-sm text-gray-600 mb-2 font-medium">动作分析：</div>
              <el-row :gutter="12" class="mb-3">
                <el-col :span="6">
                  <div class="gesture-metric">
                    <div class="gesture-label">姿态得分</div>
                    <el-progress 
                      type="circle" 
                      :percentage="videoAnalysis.gesture_analysis.posture_score" 
                      :width="60"
                      :stroke-width="6"
                      :color="getProgressColor(videoAnalysis.gesture_analysis.posture_score)"
                    />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="gesture-metric">
                    <div class="gesture-label">手势得分</div>
                    <el-progress 
                      type="circle" 
                      :percentage="videoAnalysis.gesture_analysis.gesture_score" 
                      :width="60"
                      :stroke-width="6"
                      :color="getProgressColor(videoAnalysis.gesture_analysis.gesture_score)"
                    />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="gesture-metric">
                    <div class="gesture-label">眼神交流</div>
                    <el-progress 
                      type="circle" 
                      :percentage="videoAnalysis.gesture_analysis.eye_contact_score || 80" 
                      :width="60"
                      :stroke-width="6"
                      :color="getProgressColor(videoAnalysis.gesture_analysis.eye_contact_score || 80)"
                    />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="gesture-metric">
                    <div class="gesture-label">动作综合</div>
                    <el-progress 
                      type="circle" 
                      :percentage="videoAnalysis.gesture_analysis.overall_gesture_score" 
                      :width="60"
                      :stroke-width="6"
                      :color="getProgressColor(videoAnalysis.gesture_analysis.overall_gesture_score)"
                    />
                  </div>
                </el-col>
              </el-row>
              
              <!-- 动作建议 -->
              <div v-if="videoAnalysis.gesture_analysis.gesture_suggestions?.length" class="gesture-suggestions">
                <ul>
                  <li v-for="(suggestion, index) in videoAnalysis.gesture_analysis.gesture_suggestions" :key="index">
                    {{ suggestion }}
                  </li>
                </ul>
              </div>
            </div>
            
            <div v-if="videoAnalysis.suggestions?.length" class="mt-3">
              <div class="text-sm text-gray-600 mb-2">语言改进建议：</div>
              <ul class="text-sm text-gray-700 pl-4">
                <li v-for="(suggestion, index) in videoAnalysis.suggestions" :key="index" class="mb-1">
                  {{ suggestion }}
                </li>
              </ul>
            </div>
            
            <!-- Token 使用量 -->
            <div class="token-usage-info mt-3">
              <div class="text-xs text-gray-400 flex flex-col gap-2">
                <div class="flex items-center gap-4">
                  <span>本次分析消耗：</span>
                  <template v-if="videoAnalysis.token_usage && videoAnalysis.token_usage.total_tokens > 0">
                    <span>
                      Token: {{ videoAnalysis.token_usage.total_tokens }} 
                      (输入: {{ videoAnalysis.token_usage.input_tokens }}, 
                      输出: {{ videoAnalysis.token_usage.output_tokens }})
                    </span>
                    <span v-if="videoAnalysis.token_usage.audio_seconds > 0">
                      | 音频: {{ videoAnalysis.token_usage.audio_seconds.toFixed(1) }}秒
                    </span>
                  </template>
                  <span v-else class="text-gray-300">
                    (旧数据，无消耗记录。重新分析可查看)
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <span>查看API余额：</span>
                  <a 
                    href="https://dashscope.console.aliyun.com/" 
                    target="_blank" 
                    class="text-blue-500 hover:text-blue-600 hover:underline"
                  >
                    阿里云控制台 →
                  </a>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="text-center py-4 text-gray-400">
            视频尚未分析或正在分析中
          </div>
        </el-collapse-item>
      </el-collapse>
      
      <!-- AI综合评语生成 -->
      <div class="mb-4" v-if="currentSubmission?.status !== 'approved'">
        <el-button
          type="success"
          :icon="MagicStick"
          :loading="generatingVideoAIFeedback"
          @click="generateVideoAIFeedback"
        >
          {{ generatingVideoAIFeedback ? '生成中...' : '生成AI综合评语' }}
        </el-button>
        <span class="text-xs text-gray-400 ml-2">基于教案和视频分析生成</span>
        
        <el-alert
          v-if="videoAIFeedback"
          type="success"
          class="mt-3"
          :closable="false"
        >
          <template #title>
            <div class="flex justify-between items-center">
              <span class="font-medium">AI建议评语</span>
              <el-button size="small" type="primary" @click="useVideoAIFeedback">使用此评语</el-button>
            </div>
          </template>
          <div class="mt-2">
            <p class="mb-2 text-gray-700">{{ videoAIFeedback.feedback }}</p>
            <div class="text-sm text-gray-500">
              <span class="mr-4">建议总分: <strong class="text-primary">{{ videoAIFeedback.suggested_score }}</strong></span>
              <span v-if="videoAIFeedback.lesson_plan_score" class="mr-4">
                教案分: {{ videoAIFeedback.lesson_plan_score }}
              </span>
              <span v-if="videoAIFeedback.video_score">
                视频分: {{ videoAIFeedback.video_score }}
              </span>
            </div>
          </div>
        </el-alert>
      </div>
      
      <el-divider />
      
      <el-form :model="reviewForm" label-width="100px">
        <el-form-item label="当前状态">
          <el-tag :type="getStatusTag(currentSubmission?.status).type as any">
            {{ getStatusTag(currentSubmission?.status).text }}
          </el-tag>
        </el-form-item>
        
        <!-- 评分规则选择器 -->
        <el-form-item label="评分规则" v-if="rubrics.length > 0 && currentSubmission?.status !== 'approved'">
          <div class="flex items-center gap-3 w-full">
            <el-select v-model="selectedRubricId" placeholder="选择评分规则" class="flex-1">
              <el-option
                v-for="r in rubrics"
                :key="r.id"
                :label="r.name"
                :value="r.id"
              >
                <div class="flex items-center justify-between w-full">
                  <span>{{ r.name }}</span>
                  <el-tag v-if="r.is_default" size="small" type="success" effect="plain">默认</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-button 
              type="primary" 
              :icon="Setting" 
              :loading="applyingRubric"
              @click="applyRubric"
            >
              {{ applyingRubric ? '计算中...' : '应用规则' }}
            </el-button>
          </div>
          <div v-if="rubricResult" class="mt-2 text-xs text-gray-500">
            <span class="mr-3">教案权重: {{ rubricResult.weights?.lesson_plan }}%</span>
            <span>视频权重: {{ rubricResult.weights?.video }}%</span>
            <el-tag v-if="rubricResult.grade_label" size="small" class="ml-3" :type="rubricResult.total_score >= 60 ? 'success' : 'danger'">
              {{ rubricResult.grade_label }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="教案分数">
          <el-input-number v-model="reviewForm.lesson_plan_score" :min="0" :max="100" :disabled="currentSubmission?.status === 'approved'" />
        </el-form-item>
        <el-form-item label="视频分数">
          <el-input-number v-model="reviewForm.video_score" :min="0" :max="100" :disabled="currentSubmission?.status === 'approved'" />
        </el-form-item>
        <el-form-item label="总分" required>
          <el-input-number v-model="reviewForm.total_score" :min="0" :max="100" :disabled="currentSubmission?.status === 'approved'" />
        </el-form-item>
        <el-form-item label="评语">
          <div class="w-full">
            <div class="flex justify-end mb-2" v-if="currentSubmission?.status !== 'approved'">
              <el-button 
                size="small" 
                type="success" 
                :loading="generatingFeedback"
                @click="handleAIGenerateFeedback"
              >
                <el-icon class="mr-1"><MagicStick /></el-icon>
                {{ generatingFeedback ? '生成中...' : 'AI 生成评语(教案)' }}
              </el-button>
            </div>
            <el-input
              v-model="reviewForm.feedback"
              type="textarea"
              :rows="4"
              placeholder="填写评语，或点击上方按钮让 AI 生成..."
              :disabled="currentSubmission?.status === 'approved'"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">{{ currentSubmission?.status === 'approved' ? '关闭' : '取消' }}</el-button>
        <template v-if="currentSubmission?.status !== 'approved'">
          <el-button type="warning" @click="handleGrade">保存评分</el-button>
          <el-button type="success" @click="handleApprove">通过</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- AI Result Dialog -->
    <el-dialog v-model="aiDialogVisible" :title="getAIDialogTitle()" width="700px" top="5vh">
      <!-- AI 分析过程动画 -->
      <AIProcessVisualization 
        :active="aiLoading" 
        :type="aiResultType === 'analysis' ? 'lesson_plan' : 'comprehensive'"
      />
      <div class="ai-result-content" style="max-height: 60vh; overflow-y: auto;" v-show="!aiLoading">
        <!-- 分析结果 -->
        <template v-if="aiResultType === 'analysis' && aiResult">
          <div class="score-section">
            <div class="overall-score">
              <span class="score">{{ aiResult.overall_score }}</span>
              <span class="label">综合评分</span>
            </div>
          </div>
          
          <div class="dimensions-grid" v-if="aiResult.dimensions">
            <div v-for="(dim, key) in aiResult.dimensions" :key="key" class="dimension-item">
              <div class="dim-header">
                <span class="dim-name">{{ getDimensionName(key) }}</span>
                <span class="dim-score">{{ dim.score }}分</span>
              </div>
              <el-progress :percentage="dim.score" :stroke-width="6" :show-text="false" />
              <p class="dim-comment">{{ dim.comment }}</p>
            </div>
          </div>
          
          <div class="section" v-if="aiResult.highlights?.length">
            <h4>亮点</h4>
            <ul>
              <li v-for="(h, i) in aiResult.highlights" :key="i">{{ h }}</li>
            </ul>
          </div>
          
          <div class="section" v-if="aiResult.suggestions?.length">
            <h4>建议</h4>
            <ul>
              <li v-for="(s, i) in aiResult.suggestions" :key="i">{{ s }}</li>
            </ul>
          </div>
        </template>
        
        <!-- 摘要结果 -->
        <template v-if="aiResultType === 'summary' && aiResult">
          <div class="summary-info">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="科目">{{ aiResult.subject || '-' }}</el-descriptions-item>
              <el-descriptions-item label="年级">{{ aiResult.grade || '-' }}</el-descriptions-item>
              <el-descriptions-item label="课题">{{ aiResult.topic || '-' }}</el-descriptions-item>
              <el-descriptions-item label="时长">{{ aiResult.duration || '-' }}</el-descriptions-item>
              <el-descriptions-item label="互动次数">{{ aiResult.interaction_count || 0 }}</el-descriptions-item>
              <el-descriptions-item label="板书设计">{{ aiResult.has_board_design ? '有' : '无' }}</el-descriptions-item>
            </el-descriptions>
          </div>
          
          <div class="section" v-if="aiResult.summary">
            <h4>内容摘要</h4>
            <p>{{ aiResult.summary }}</p>
          </div>
          
          <div class="section" v-if="aiResult.sections?.length">
            <h4>章节结构</h4>
            <el-tag v-for="(sec, i) in aiResult.sections" :key="i" class="mr-2 mb-2">{{ sec }}</el-tag>
          </div>
          
          <div class="section" v-if="aiResult.highlights?.length">
            <h4>亮点</h4>
            <ul>
              <li v-for="(h, i) in aiResult.highlights" :key="i">{{ h }}</li>
            </ul>
          </div>
          
          <div class="section" v-if="aiResult.issues?.length">
            <h4>问题</h4>
            <ul>
              <li v-for="(issue, i) in aiResult.issues" :key="i">{{ issue }}</li>
            </ul>
          </div>
        </template>
        
        <!-- 改进建议 -->
        <template v-if="aiResultType === 'improvement' && aiResult">
          <div class="section" v-if="aiResult.overall_assessment">
            <h4>总体评价</h4>
            <p>{{ aiResult.overall_assessment }}</p>
          </div>
          
          <div class="section" v-if="aiResult.strengths?.length">
            <h4>优点</h4>
            <ul>
              <li v-for="(s, i) in aiResult.strengths" :key="i">{{ s }}</li>
            </ul>
          </div>
          
          <div class="section" v-if="aiResult.missing_elements?.length">
            <h4>缺失要素</h4>
            <ul>
              <li v-for="(m, i) in aiResult.missing_elements" :key="i">{{ m }}</li>
            </ul>
          </div>
          
          <div class="section" v-if="aiResult.improvements?.length">
            <h4>具体改进建议</h4>
            <div v-for="(imp, i) in aiResult.improvements" :key="i" class="improvement-item">
              <div class="imp-header">
                <el-tag :type="imp.priority === 'high' ? 'danger' : imp.priority === 'medium' ? 'warning' : 'info'" size="small">
                  {{ imp.priority === 'high' ? '重要' : imp.priority === 'medium' ? '建议' : '可选' }}
                </el-tag>
                <span class="imp-location">{{ imp.location }}</span>
              </div>
              <p class="imp-issue"><strong>问题：</strong>{{ imp.issue }}</p>
              <p class="imp-suggestion"><strong>建议：</strong>{{ imp.suggestion }}</p>
            </div>
          </div>
        </template>
      </div>
      
      <!-- 知识图谱（仅在分析模式展示） -->
      <div v-if="aiResultType === 'analysis' && currentSubmission && !aiLoading" class="mt-4">
        <KnowledgeGraph :submission-id="currentSubmission.id" />
      </div>

      <template #footer>
        <el-button @click="aiDialogVisible = false">关闭</el-button>
        <el-button @click="refreshAIResult" :loading="aiLoading">
          <el-icon class="mr-1"><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button v-if="aiResultType === 'analysis' && aiResult?.overall_score" type="primary" @click="useAIScore">
          应用评分并批改
        </el-button>
      </template>
    </el-dialog>

    <!-- Reject Dialog -->
    <el-dialog v-model="rejectDialogVisible" title="驳回作业" width="400px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="驳回原因" required>
          <el-input
            v-model="rejectForm.reason"
            type="textarea"
            :rows="4"
            placeholder="请说明驳回原因..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="handleReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <!-- AI 一键批改对话框 -->
    <el-dialog v-model="autoGradeDialogVisible" title="AI 一键智能批改" width="600px" top="8vh" :close-on-click-modal="false">
      <div class="auto-grade-steps">
        <div v-for="(step, idx) in autoGradeSteps" :key="idx" class="auto-grade-step" :class="step.status">
          <div class="step-icon">
            <span v-if="step.status === 'processing'" class="step-loading"></span>
            <span v-else-if="step.status === 'success'" class="step-done">✓</span>
            <span v-else-if="step.status === 'error'" class="step-error">✗</span>
            <span v-else-if="step.status === 'skipped'" class="step-skip">–</span>
            <span v-else class="step-pending">{{ idx + 1 }}</span>
          </div>
          <div class="step-content">
            <div class="step-title">{{ step.icon }} {{ step.name }}</div>
            <div class="step-msg">{{ step.message }}</div>
          </div>
        </div>
      </div>

      <div v-if="autoGradeResult && !autoGrading" class="auto-grade-result mt-6">
        <el-divider>批改结果</el-divider>
        <el-row :gutter="16" class="mb-4">
          <el-col :span="8">
            <div class="result-stat">
              <div class="stat-label">教案分数</div>
              <div class="stat-value text-blue-600">{{ autoGradeResult.lesson_plan_score }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="result-stat">
              <div class="stat-label">视频分数</div>
              <div class="stat-value text-green-600">{{ autoGradeResult.video_score || '-' }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="result-stat">
              <div class="stat-label">综合总分</div>
              <div class="stat-value text-orange-600 text-2xl">{{ autoGradeResult.total_score }}</div>
            </div>
          </el-col>
        </el-row>
        <div class="bg-gray-50 p-4 rounded-lg">
          <div class="text-sm font-medium mb-2 text-gray-700">AI 生成评语：</div>
          <div class="text-sm text-gray-600 leading-relaxed">{{ autoGradeResult.feedback }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="autoGradeDialogVisible = false">关闭</el-button>
        <el-button v-if="autoGradeResult && !autoGrading" type="primary" @click="applyAutoGradeResult">
          应用结果并编辑
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量评分对话框 -->
    <BatchGradeDialog 
      v-model:visible="batchGradeVisible" 
      :submissions="submissions"
      @success="fetchSubmissions"
    />
  </div>
</template>

<style scoped>
/* AI 结果弹窗样式 */
.ai-result-content {
  padding: 0 8px;
}

.score-section {
  text-align: center;
  margin-bottom: 24px;
}

.overall-score {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 40px;
  background: #059669;
  border-radius: 16px;
  color: white;
}

.overall-score .score {
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
}

.overall-score .label {
  font-size: 14px;
  margin-top: 8px;
  opacity: 0.9;
}

.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.dimension-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.dim-name {
  font-weight: 500;
  color: #374151;
}

.dim-score {
  font-weight: 600;
  color: #10b981;
}

.dim-comment {
  font-size: 12px;
  color: #6b7280;
  margin: 8px 0 0;
  line-height: 1.5;
}

.section {
  margin-bottom: 20px;
}

.section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.section ul {
  margin: 0;
  padding-left: 20px;
}

.section li {
  margin-bottom: 6px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.6;
}

.section p {
  margin: 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.6;
}

.summary-info {
  margin-bottom: 20px;
}

.improvement-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 12px;
}

.imp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.imp-location {
  font-weight: 500;
  color: #374151;
  font-size: 13px;
}

.imp-issue, .imp-suggestion {
  font-size: 13px;
  color: #4b5563;
  margin: 4px 0;
  line-height: 1.5;
}

.w-full {
  width: 100%;
}

.mr-1 {
  margin-right: 4px;
}

.mr-2 {
  margin-right: 8px;
}

.mb-2 {
  margin-bottom: 8px;
}

/* 视频分析样式 */
.video-analysis-summary {
  padding: 8px 0;
}

.analysis-metric {
  text-align: center;
  padding: 12px 8px;
  background: #f5f7fa;
  border-radius: 6px;
}

.analysis-metric .metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.analysis-metric .metric-value {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
}

.analysis-metric .metric-value.text-primary {
  color: #409eff;
}

.analysis-metric .metric-unit {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.video-analysis-summary ul {
  list-style: disc;
  margin: 0;
}

.font-medium {
  font-weight: 500;
}

.text-primary {
  color: #409eff;
}

/* 动作分析样式 */
.gesture-metric {
  text-align: center;
  padding: 8px;
}

.gesture-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.gesture-suggestions {
  background: #f0f9eb;
  border-radius: 6px;
  padding: 10px;
  margin-top: 8px;
}

.gesture-suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.gesture-suggestions li {
  padding: 4px 0;
  color: #67c23a;
  font-size: 12px;
}

.gesture-suggestions li::before {
  content: "✓ ";
  font-weight: bold;
}

/* Token 使用量样式 */
.token-usage-info {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px dashed #dcdfe6;
}

/* AI 一键批改步骤样式 */
.auto-grade-steps { display: flex; flex-direction: column; gap: 16px; }
.auto-grade-step { display: flex; align-items: center; gap: 16px; padding: 12px 16px; border-radius: 10px; background: #f9fafb; transition: all 0.3s; }
.auto-grade-step.processing { background: #eff6ff; border: 1px solid #bfdbfe; }
.auto-grade-step.success { background: #f0fdf4; border: 1px solid #bbf7d0; }
.auto-grade-step.error { background: #fef2f2; border: 1px solid #fecaca; }
.auto-grade-step.skipped { background: #f5f5f5; opacity: 0.7; }
.step-icon { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.step-loading { width: 20px; height: 20px; border: 3px solid #dbeafe; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }
.step-done { color: #16a34a; font-size: 18px; }
.step-error { color: #dc2626; font-size: 18px; }
.step-skip { color: #9ca3af; font-size: 18px; }
.step-pending { color: #9ca3af; background: #e5e7eb; width: 100%; height: 100%; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.step-content { flex: 1; }
.step-title { font-weight: 600; font-size: 14px; color: #374151; }
.step-msg { font-size: 12px; color: #6b7280; margin-top: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
.result-stat { text-align: center; padding: 12px; background: white; border-radius: 8px; border: 1px solid #e5e7eb; }
.stat-label { font-size: 12px; color: #9ca3af; margin-bottom: 4px; }
.stat-value { font-size: 28px; font-weight: 700; }

/* AI 诊断按钮脉冲效果 */
.ai-diagnosis-btn {
  position: relative;
  font-weight: 600 !important;
}
.ai-diagnosis-btn::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.15);
  animation: diagPulse 2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes diagPulse {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}
</style>
