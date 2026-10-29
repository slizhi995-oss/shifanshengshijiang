<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, UploadUserFile } from 'element-plus'
import { UploadFilled, Document, VideoCamera, Loading, View, Close, MagicStick, Cpu, ChatDotRound, VideoPause, ChatLineSquare, Clock, UserFilled, DataLine, Coin, FolderOpened } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { aiApi } from '@/api'

// 跳转到 AI 多模态诊断
const goToAIReport = (taskId: number) => {
  const submission = getSubmission(taskId)
  if (submission) {
    router.push(`/student/ai-report/${submission.id}`)
  }
}

const route = useRoute()
const router = useRouter()
const activeTaskId = ref(Number(route.query.taskId) || null)
const tasks = ref<any[]>([])
const submissions = ref<any[]>([])
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const statusFilter = ref<string>('')
const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)

// AI 质检相关状态
const preCheckLoading = ref(false)
const preCheckDialogVisible = ref(false)
const preCheckResult = ref<any>(null)

// AI 对比分析相关状态
const compareDialogVisible = ref(false)
const compareLoading = ref(false)
const compareResult = ref<any>(null)

// 视频分析相关状态
const videoAnalysisDialogVisible = ref(false)
const currentVideoAnalysis = ref<any>(null)
const loadingVideoAnalysis = ref(false)
const currentAnalysisSubmission = ref<any>(null)

// Form Data
const form = ref({
  task_id: null,
  student_remark: ''
})

const lessonPlanFiles = ref<UploadUserFile[]>([])
const videoFiles = ref<UploadUserFile[]>([])

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
  } catch (error) {}
}

// Fetch Data
const fetchData = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    // Get tasks
    const tasksRes: any = await api.get('/tasks', { params: { semester_id: selectedSemesterId.value } })
    tasks.value = tasksRes
    
    // Get my submissions
    const subsRes: any = await api.get('/submissions/my', { params: { semester_id: selectedSemesterId.value } })
    submissions.value = subsRes
    
    // Open dialog if taskId is in query
    if (activeTaskId.value) {
      openSubmitDialog(activeTaskId.value)
    }
  } finally {
    loading.value = false
  }
}

const handleSemesterChange = () => {
  fetchData()
}

const handleStatusFilterChange = () => {
  // Filter is applied in computed, no need to refetch
}

// Computed filtered tasks based on status
const filteredTasks = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter((task: any) => {
    const status = getSubmissionStatus(task.id)
    return status === statusFilter.value
  })
})

// 当前选中的任务
const currentTask = computed(() => {
  return tasks.value.find((t: any) => t.id === form.value.task_id)
})

const openSubmitDialog = (taskId: number) => {
  const task = tasks.value.find((t: any) => t.id === taskId)
  if (task) {
    form.value.task_id = taskId as any
    form.value.student_remark = ''
    lessonPlanFiles.value = []
    videoFiles.value = []
    dialogVisible.value = true

    // 如果是通过路由上的 taskId 打开的，只在第一次打开后清理参数，避免后续刷新数据时再次自动弹窗
    if (activeTaskId.value) {
      activeTaskId.value = null
      const newQuery: Record<string, any> = { ...route.query }
      delete newQuery.taskId
      router.replace({ query: newQuery })
    }
  }
}

const handleSubmit = async () => {
  const task: any = tasks.value.find((t: any) => t.id === form.value.task_id)
  
  // Validation
  if (task.require_lesson_plan && lessonPlanFiles.value.length === 0) {
    ElMessage.warning('请上传教案')
    return
  }
  if (task.require_video && videoFiles.value.length === 0) {
    ElMessage.warning('请上传视频')
    return
  }

  submitLoading.value = true
  const formData = new FormData()
  formData.append('task_id', String(form.value.task_id))
  formData.append('student_remark', form.value.student_remark)
  
  if (lessonPlanFiles.value.length > 0) {
    formData.append('lesson_plan', lessonPlanFiles.value[0].raw as File)
  }
  if (videoFiles.value.length > 0) {
    formData.append('video', videoFiles.value[0].raw as File)
  }

  try {
    const result: any = await api.post('/submissions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000 // 10 minutes for large files
    })
    
    // 如果提交了视频，自动触发AI分析
    if (videoFiles.value.length > 0 && result.id) {
      try {
        await api.post(`/video-analysis/submissions/${result.id}/analyze-video`)
        ElMessage.success('作业提交成功，视频正在AI分析中...')
      } catch (error) {
        console.error('启动视频分析失败', error)
        ElMessage.success('作业提交成功')
      }
    } else {
      ElMessage.success('作业提交成功')
    }
    
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    // Error handled by interceptor
  } finally {
    submitLoading.value = false
  }
}

const getSubmissionStatus = (taskId: number) => {
  const sub: any = submissions.value.find((s: any) => s.task_id === taskId)
  return sub ? sub.status : 'not_submitted'
}

const getSubmission = (taskId: number) => {
  return submissions.value.find((s: any) => s.task_id === taskId)
}

// 从路径提取文件名
const getFileName = (path: string) => {
  if (!path) return ''
  const parts = path.split('/')
  return parts[parts.length - 1]
}

// 打开文件
const openFile = (path: string) => {
  window.open(`/uploads/${path}`, '_blank')
}

// 视频预览URL
const videoPreviewUrl = ref('')
const pdfPreviewUrl = ref('')

// 监听文件变化生成预览
const handleVideoChange = (file: any) => {
  if (file.raw) {
    videoPreviewUrl.value = URL.createObjectURL(file.raw)
  }
}

const handlePdfChange = (file: any) => {
  if (file.raw) {
    pdfPreviewUrl.value = URL.createObjectURL(file.raw)
  }
}

const handleVideoRemove = () => {
  videoPreviewUrl.value = ''
}

const handlePdfRemove = () => {
  pdfPreviewUrl.value = ''
}

// 查看视频分析结果
const viewVideoAnalysis = async (row: any) => {
  const submission = getSubmission(row.id)
  if (!submission?.video_path) {
    ElMessage.warning('该提交没有视频')
    return
  }
  
  loadingVideoAnalysis.value = true
  videoAnalysisDialogVisible.value = true
  currentVideoAnalysis.value = null
  currentAnalysisSubmission.value = submission
  
  try {
    const result: any = await api.get(`/video-analysis/submissions/${submission.id}/video-analysis`)
    
    if (result.status === 'completed') {
      currentVideoAnalysis.value = result.analysis
    } else if (result.status === 'failed') {
      currentVideoAnalysis.value = { 
        status: 'failed', 
        error: result.error,
        message: result.message 
      }
    } else if (result.status === 'not_analyzed') {
      currentVideoAnalysis.value = { status: 'not_analyzed', message: result.message }
    } else {
      currentVideoAnalysis.value = { status: 'processing' }
    }
  } catch (error) {
    ElMessage.error('获取视频分析失败')
    videoAnalysisDialogVisible.value = false
  } finally {
    loadingVideoAnalysis.value = false
  }
}

// 手动触发视频分析
const triggerVideoAnalysis = async () => {
  if (!currentAnalysisSubmission.value) return
  
  loadingVideoAnalysis.value = true
  try {
    await api.post(`/video-analysis/submissions/${currentAnalysisSubmission.value.id}/analyze-video`)
    ElMessage.success('视频分析已启动，请稍后刷新查看结果')
    currentVideoAnalysis.value = { status: 'processing' }
  } catch (error: any) {
    ElMessage.error(error.message || '启动分析失败')
  } finally {
    loadingVideoAnalysis.value = false
  }
}

// 刷新视频分析结果
const refreshVideoAnalysis = async () => {
  if (!currentAnalysisSubmission.value) return
  
  loadingVideoAnalysis.value = true
  try {
    const result: any = await api.get(`/video-analysis/submissions/${currentAnalysisSubmission.value.id}/video-analysis`)
    
    if (result.status === 'completed') {
      currentVideoAnalysis.value = result.analysis
      ElMessage.success('分析结果已更新')
    } else {
      currentVideoAnalysis.value = { status: 'processing' }
      ElMessage.info('视频仍在分析中，请稍后再试')
    }
  } catch (error) {
    ElMessage.error('刷新失败')
  } finally {
    loadingVideoAnalysis.value = false
  }
}

// 获取得分等级样式
const getScoreClass = (score: number) => {
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'good'
  if (score >= 70) return 'fair'
  return 'poor'
}

// 格式化时长
const formatDuration = (seconds: number) => {
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${minutes}分${secs}秒`
}

// 获取进度条颜色
const getProgressColor = (score: number) => {
  if (score >= 90) return '#67c23a'
  if (score >= 80) return '#409eff'
  if (score >= 70) return '#e6a23c'
  return '#f56c6c'
}

// AI 预提交质检
const handlePreCheck = async () => {
  if (lessonPlanFiles.value.length === 0) {
    ElMessage.warning('请先上传教案文件')
    return
  }
  preCheckLoading.value = true
  preCheckResult.value = null
  try {
    // 先解析文件获取文本
    const parseRes: any = await aiApi.parseFile(lessonPlanFiles.value[0].raw as File)
    if (parseRes.success && parseRes.data?.content) {
      const checkRes: any = await aiApi.preCheck({ text: parseRes.data.content })
      if (checkRes.success) {
        preCheckResult.value = checkRes.data
        preCheckDialogVisible.value = true
      }
    } else {
      ElMessage.error('文件解析失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || 'AI 质检失败')
  } finally {
    preCheckLoading.value = false
  }
}

// AI 对比分析
const handleCompare = async (taskId: number) => {
  // 获取同一任务的所有提交
  const taskSubmissions = submissions.value.filter((s: any) => s.task_id === taskId)
  if (taskSubmissions.length < 2) {
    ElMessage.warning('需要至少两次提交才能对比')
    return
  }
  compareLoading.value = true
  compareResult.value = null
  compareDialogVisible.value = true
  try {
    const sorted = [...taskSubmissions].sort((a: any, b: any) => new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime())
    const res: any = await aiApi.compareSubmissions({
      submission_id_1: sorted[0].id,
      submission_id_2: sorted[sorted.length - 1].id,
    })
    if (res.success) {
      compareResult.value = res.data
    }
  } catch (error: any) {
    ElMessage.error(error.message || '对比分析失败')
  } finally {
    compareLoading.value = false
  }
}

// 获取同一任务的提交次数
const getSubmissionCount = (taskId: number) => {
  return submissions.value.filter((s: any) => s.task_id === taskId).length
}

const getCheckStatusType = (status: string) => {
  if (status === 'pass') return 'success'
  if (status === 'warning') return 'warning'
  return 'danger'
}

onMounted(fetchSemesters)
</script>

<template>
  <div class="submissions-page">
    <div class="ms-page-header">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="ms-page-title">
            <span class="w-2.5 h-6 rounded-full bg-gradient-to-b from-indigo-500 to-cyan-500 inline-block mr-1"></span>
            我的提交记录
          </h2>
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-200/60 flex items-center gap-1">
            <el-icon :size="12"><Cpu /></el-icon>
            AI 质检与微格诊断
          </span>
        </div>
        <p class="ms-page-desc">沉淀每次实训演练，查看教案视频质检指标、AI 多模态诊断与版本演化对比</p>
      </div>
      <div class="flex items-center gap-3">
        <el-select
          v-model="statusFilter"
          placeholder="筛选状态"
          clearable
          @change="handleStatusFilterChange"
          style="width: 140px"
        >
          <el-option label="全部状态" value="" />
          <el-option label="未提交" value="not_submitted" />
          <el-option label="待批改" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
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

    <el-empty v-if="semesters.length === 0 && !loading" description="暂无批次" />
    <div v-else class="submission-card">
      <el-table :data="filteredTasks" v-loading="loading" class="modern-submission-table">
        <el-table-column prop="title" label="作业名称" min-width="180">
          <template #default="scope">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0">
                <el-icon :size="16"><Document /></el-icon>
              </div>
              <div class="flex flex-col min-w-0">
                <span class="font-bold text-slate-800 text-sm truncate">{{ scope.row.title }}</span>
                <span class="text-[11px] text-slate-400">ID: #{{ scope.row.id }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="截止日期" width="130">
          <template #default="scope">
            <div class="flex items-center gap-1.5 text-xs text-slate-600 font-medium">
              <el-icon class="text-slate-400"><Clock /></el-icon>
              <span>{{ new Date(scope.row.deadline).toLocaleDateString() }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="要求规范" width="140">
          <template #default="scope">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span v-if="scope.row.require_lesson_plan" class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100">教案</span>
              <span v-if="scope.row.require_video" class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-cyan-50 text-cyan-700 border border-cyan-100">视频</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="审核状态" width="120">
          <template #default="scope">
            <span v-if="getSubmissionStatus(scope.row.id) === 'pending'" class="status-badge status-pending">
              <span class="status-dot"></span>待批改
            </span>
            <span v-else-if="getSubmissionStatus(scope.row.id) === 'approved'" class="status-badge status-approved">
              <span class="status-dot"></span>已通过
            </span>
            <span v-else-if="getSubmissionStatus(scope.row.id) === 'rejected'" class="status-badge status-rejected">
              <span class="status-dot"></span>已驳回
            </span>
            <span v-else class="status-badge status-none">
              <span class="status-dot"></span>未提交
            </span>
          </template>
        </el-table-column>
        <el-table-column label="已传教案" min-width="170">
          <template #default="scope">
            <template v-if="scope.row.require_lesson_plan">
              <div v-if="getSubmission(scope.row.id)?.lesson_plan_name" class="file-chip" @click="openFile(getSubmission(scope.row.id)?.lesson_plan_path)">
                <el-icon class="text-indigo-500 flex-shrink-0"><Document /></el-icon>
                <el-tooltip :content="getSubmission(scope.row.id)?.lesson_plan_name" placement="top">
                  <span class="file-name truncate">{{ getSubmission(scope.row.id)?.lesson_plan_name }}</span>
                </el-tooltip>
              </div>
              <span v-else class="text-slate-400 text-xs italic">尚未提交</span>
            </template>
            <span v-else class="text-slate-300 text-xs">无需上传</span>
          </template>
        </el-table-column>
        <el-table-column label="实训录像" min-width="170">
          <template #default="scope">
            <template v-if="scope.row.require_video">
              <div v-if="getSubmission(scope.row.id)?.video_name" class="file-chip" @click="openFile(getSubmission(scope.row.id)?.video_path)">
                <el-icon class="text-cyan-500 flex-shrink-0"><VideoCamera /></el-icon>
                <el-tooltip :content="getSubmission(scope.row.id)?.video_name" placement="top">
                  <span class="file-name truncate">{{ getSubmission(scope.row.id)?.video_name }}</span>
                </el-tooltip>
              </div>
              <span v-else class="text-slate-400 text-xs italic">尚未提交</span>
            </template>
            <span v-else class="text-slate-300 text-xs">无需上传</span>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="90" align="center">
          <template #default="scope">
            <span v-if="getSubmission(scope.row.id)?.total_score" class="font-extrabold text-base text-indigo-600 font-mono">
              {{ getSubmission(scope.row.id)?.total_score }}
            </span>
            <span v-else class="text-slate-300 font-mono">—</span>
          </template>
        </el-table-column>
        <el-table-column label="多模态诊断" width="110" align="center">
          <template #default="scope">
            <template v-if="getSubmission(scope.row.id)?.video_path">
              <el-button
                type="primary"
                size="small"
                link
                class="!text-cyan-600 hover:!text-cyan-700 !font-semibold"
                @click="viewVideoAnalysis(scope.row)"
              >
                <el-icon class="mr-1"><View /></el-icon>
                查看指标
              </el-button>
            </template>
            <span v-else class="text-slate-300 text-xs">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="200">
          <template #default="scope">
            <div class="flex items-center gap-1.5 flex-wrap">
              <el-button 
                v-if="getSubmissionStatus(scope.row.id) === 'not_submitted' || getSubmissionStatus(scope.row.id) === 'rejected'"
                type="primary" 
                size="small" 
                class="!rounded-lg !bg-indigo-600 hover:!bg-indigo-700 !border-none !shadow-xs"
                @click="openSubmitDialog(scope.row.id)"
              >
                {{ getSubmissionStatus(scope.row.id) === 'rejected' ? '重新提交' : '提交实训' }}
              </el-button>
              <el-button v-else size="small" disabled class="!rounded-lg !text-slate-400">已交付</el-button>
              <el-button
                v-if="getSubmissionCount(scope.row.id) >= 2"
                type="success"
                size="small"
                link
                class="!text-emerald-600 hover:!text-emerald-700 !font-semibold"
                @click="handleCompare(scope.row.id)"
              >
                AI对比
              </el-button>
              <el-button
                v-if="getSubmission(scope.row.id)?.video_path"
                type="primary"
                size="small"
                link
                class="ai-diagnosis-btn !font-bold"
                @click="goToAIReport(scope.row.id)"
              >
                <el-icon class="mr-0.5"><Cpu /></el-icon>AI全案诊断
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Submission Dialog -->
    <el-dialog v-model="dialogVisible" title="提交作业" width="600px">
      <el-form label-position="top">
        <el-form-item v-if="currentTask?.require_lesson_plan" label="教案 (PDF)" required>
          <el-upload
            class="w-full"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            v-model:file-list="lessonPlanFiles"
            accept=".pdf,.doc,.docx"
            @change="handlePdfChange"
            @remove="handlePdfRemove"
          >
            <template v-if="pdfPreviewUrl && lessonPlanFiles.length > 0">
              <div class="flex flex-col items-center py-2">
                <el-icon class="text-4xl text-red-500 mb-2"><Document /></el-icon>
                <span class="text-sm text-gray-600 truncate max-w-[200px]">{{ lessonPlanFiles[0]?.name }}</span>
                <span class="text-xs text-green-500 mt-1">✅ 已选择</span>
              </div>
            </template>
            <template v-else>
              <el-icon class="el-icon--upload"><Document /></el-icon>
              <div class="el-upload__text">
                拖拽PDF/Word文件到此处或 <em>点击上传</em>
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item v-if="currentTask?.require_video" label="讲课视频 (MP4)" required>
          <el-upload
            class="w-full"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            v-model:file-list="videoFiles"
            accept="video/*"
            @change="handleVideoChange"
            @remove="handleVideoRemove"
          >
            <template v-if="videoPreviewUrl && videoFiles.length > 0">
              <div class="flex flex-col items-center py-2">
                <video :src="videoPreviewUrl" class="w-48 h-28 object-cover rounded mb-2" />
                <span class="text-sm text-gray-600 truncate max-w-[200px]">{{ videoFiles[0]?.name }}</span>
                <span class="text-xs text-green-500 mt-1">✅ 已选择</span>
              </div>
            </template>
            <template v-else>
              <el-icon class="el-icon--upload"><VideoCamera /></el-icon>
              <div class="el-upload__text">
                拖拽视频文件到此处或 <em>点击上传</em>
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.student_remark"
            type="textarea"
            :rows="3"
            placeholder="如有特殊说明请填写"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button v-if="currentTask?.require_lesson_plan" type="warning" @click="handlePreCheck" :loading="preCheckLoading">
            <el-icon class="mr-1"><MagicStick /></el-icon>AI 质检
          </el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitLoading">
            提交
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- AI 质检结果对话框 -->
    <el-dialog v-model="preCheckDialogVisible" title="AI 预提交质量检测" width="550px">
      <div v-if="preCheckResult" class="pre-check-result">
        <div class="check-score-bar" :class="preCheckResult.overall_status">
          <div class="check-score">{{ preCheckResult.score }}</div>
          <div class="check-label">
            <span v-if="preCheckResult.overall_status === 'pass'" class="text-green-600 font-bold">检测通过</span>
            <span v-else-if="preCheckResult.overall_status === 'warning'" class="text-orange-500 font-bold">部分问题</span>
            <span v-else class="text-red-500 font-bold">需要改进</span>
          </div>
          <div class="check-summary text-sm text-gray-500">{{ preCheckResult.summary }}</div>
        </div>
        <div class="check-items mt-4">
          <div v-for="(check, idx) in preCheckResult.checks" :key="idx" class="check-item" :class="check.status">
            <span class="check-dot"></span>
            <span class="check-name">{{ check.item }}</span>
            <el-tag :type="getCheckStatusType(check.status)" size="small">
              {{ check.status === 'pass' ? '通过' : check.status === 'warning' ? '警告' : '未通过' }}
            </el-tag>
            <span class="check-msg">{{ check.message }}</span>
          </div>
        </div>
        <div v-if="preCheckResult.suggestions?.length" class="mt-4 bg-orange-50 p-3 rounded-lg">
          <div class="text-sm font-medium text-orange-700 mb-2">改进建议：</div>
          <ul class="text-sm text-orange-600 pl-4">
            <li v-for="(s, i) in preCheckResult.suggestions" :key="i" class="mb-1">{{ s }}</li>
          </ul>
        </div>
      </div>
      <template #footer>
        <el-button @click="preCheckDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 视频分析结果对话框 -->
    <el-dialog
      v-model="videoAnalysisDialogVisible"
      title="视频AI分析报告"
      width="800px"
      top="5vh"
    >
      <div v-if="loadingVideoAnalysis" class="text-center py-8">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p class="mt-4 text-gray-500">加载中...</p>
      </div>
      
      <div v-else-if="currentVideoAnalysis?.status === 'processing'" class="text-center py-8">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p class="mt-4 text-gray-600">视频正在分析中...</p>
        <p class="text-sm text-gray-400">预计需要 3-5 分钟</p>
        <el-button class="mt-4" @click="refreshVideoAnalysis">刷新状态</el-button>
      </div>
      
      <div v-else-if="currentVideoAnalysis?.status === 'failed'" class="text-center py-8">
        <el-icon :size="40" color="#f56c6c"><Close /></el-icon>
        <p class="mt-4 text-red-500 font-medium">分析失败</p>
        <p class="text-sm text-gray-500 mt-2">{{ currentVideoAnalysis.message }}</p>
        <p class="text-xs text-gray-400 mt-1">{{ currentVideoAnalysis.error }}</p>
        <el-button class="mt-4" type="primary" @click="triggerVideoAnalysis" :loading="loadingVideoAnalysis">
          重新分析
        </el-button>
      </div>
      
      <div v-else-if="currentVideoAnalysis?.status === 'not_analyzed'" class="text-center py-8">
        <el-icon :size="40" color="#909399"><VideoCamera /></el-icon>
        <p class="mt-4 text-gray-600">{{ currentVideoAnalysis.message }}</p>
        <el-button class="mt-4" type="primary" @click="triggerVideoAnalysis" :loading="loadingVideoAnalysis">
          开始分析
        </el-button>
      </div>
      
      <div v-else-if="currentVideoAnalysis" class="video-analysis-content">
        <!-- 综合得分 -->
        <div class="score-section text-center mb-6">
          <div class="score-circle" :class="getScoreClass(currentVideoAnalysis.overall_score)">
            <div class="score-value">{{ currentVideoAnalysis.overall_score }}</div>
            <div class="score-label">综合得分</div>
          </div>
        </div>
        
        <!-- 详细指标 -->
        <el-row :gutter="16" class="mb-6">
          <el-col :span="6">
            <el-card shadow="hover" class="metric-card">
              <div class="metric-item">
                <div class="metric-icon"><el-icon :size="24" color="#0891b2"><ChatDotRound /></el-icon></div>
                <div class="metric-label">语速</div>
                <div class="metric-value">{{ currentVideoAnalysis.speech_rate }}</div>
                <div class="metric-unit">字/分钟</div>
                <div class="metric-ideal">理想：120-160</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="metric-card">
              <div class="metric-item">
                <div class="metric-icon"><el-icon :size="24" color="#0891b2"><VideoPause /></el-icon></div>
                <div class="metric-label">停顿次数</div>
                <div class="metric-value">{{ currentVideoAnalysis.pause_count }}</div>
                <div class="metric-unit">次</div>
                <div class="metric-ideal">理想：≤3次</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="metric-card">
              <div class="metric-item">
                <div class="metric-icon"><el-icon :size="24" color="#0891b2"><ChatLineSquare /></el-icon></div>
                <div class="metric-label">语气词</div>
                <div class="metric-value">{{ currentVideoAnalysis.filler_word_count }}</div>
                <div class="metric-unit">次</div>
                <div class="metric-ideal">理想：≤5次</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="metric-card">
              <div class="metric-item">
                <div class="metric-icon"><el-icon :size="24" color="#0891b2"><Clock /></el-icon></div>
                <div class="metric-label">视频时长</div>
                <div class="metric-value-small">{{ formatDuration(currentVideoAnalysis.duration) }}</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 语气词详情 -->
        <div v-if="currentVideoAnalysis.filler_words && Object.keys(currentVideoAnalysis.filler_words).length > 0" class="mb-6">
          <h4 class="section-title">语气词详情</h4>
          <div class="flex flex-wrap gap-2">
            <el-tag v-for="(count, word) in currentVideoAnalysis.filler_words" :key="word" type="warning">
              {{ word }}: {{ count }}次
            </el-tag>
          </div>
        </div>
        
        <!-- 动作分析 -->
        <div v-if="currentVideoAnalysis.gesture_analysis && !currentVideoAnalysis.gesture_analysis.error" class="mb-6">
          <h4 class="section-title"><el-icon class="mr-1"><UserFilled /></el-icon>动作分析</h4>
          <el-row :gutter="12" class="mb-4">
            <el-col :span="6">
              <div class="gesture-metric">
                <div class="gesture-label">姿态得分</div>
                <el-progress 
                  type="circle" 
                  :percentage="currentVideoAnalysis.gesture_analysis.posture_score" 
                  :width="80"
                  :stroke-width="8"
                  :color="getProgressColor(currentVideoAnalysis.gesture_analysis.posture_score)"
                />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="gesture-metric">
                <div class="gesture-label">手势得分</div>
                <el-progress 
                  type="circle" 
                  :percentage="currentVideoAnalysis.gesture_analysis.gesture_score" 
                  :width="80"
                  :stroke-width="8"
                  :color="getProgressColor(currentVideoAnalysis.gesture_analysis.gesture_score)"
                />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="gesture-metric">
                <div class="gesture-label">眼神交流</div>
                <el-progress 
                  type="circle" 
                  :percentage="currentVideoAnalysis.gesture_analysis.eye_contact_score || 80" 
                  :width="80"
                  :stroke-width="8"
                  :color="getProgressColor(currentVideoAnalysis.gesture_analysis.eye_contact_score || 80)"
                />
              </div>
            </el-col>
            <el-col :span="6">
              <div class="gesture-metric">
                <div class="gesture-label">动作综合</div>
                <el-progress 
                  type="circle" 
                  :percentage="currentVideoAnalysis.gesture_analysis.overall_gesture_score" 
                  :width="80"
                  :stroke-width="8"
                  :color="getProgressColor(currentVideoAnalysis.gesture_analysis.overall_gesture_score)"
                />
              </div>
            </el-col>
          </el-row>
          
          <!-- 动作建议 -->
          <div v-if="currentVideoAnalysis.gesture_analysis.gesture_suggestions?.length" class="gesture-suggestions">
            <ul>
              <li v-for="(suggestion, index) in currentVideoAnalysis.gesture_analysis.gesture_suggestions" :key="index">
                {{ suggestion }}
              </li>
            </ul>
          </div>
        </div>
        
        <!-- 改进建议 -->
        <div class="mb-6">
          <h4 class="section-title"><el-icon class="mr-1"><MagicStick /></el-icon>语言改进建议</h4>
          <ul class="suggestions-list">
            <li v-for="(suggestion, index) in currentVideoAnalysis.suggestions" :key="index">
              {{ suggestion }}
            </li>
          </ul>
        </div>
        
        <!-- 完整文字稿 -->
        <el-collapse class="mt-4">
          <el-collapse-item name="transcript">
            <template #title><el-icon class="mr-1"><Document /></el-icon>查看完整文字稿</template>
            <div class="transcript-content">
              {{ currentVideoAnalysis.transcript }}
            </div>
          </el-collapse-item>
        </el-collapse>
        
        <!-- Token 使用量 -->
        <div class="token-usage-info mt-4">
          <div class="text-xs text-gray-400 flex flex-col gap-2">
            <div class="flex items-center gap-4">
              <span><el-icon class="mr-1"><DataLine /></el-icon>本次分析消耗：</span>
              <template v-if="currentVideoAnalysis.token_usage && currentVideoAnalysis.token_usage.total_tokens > 0">
                <span>
                  Token: {{ currentVideoAnalysis.token_usage.total_tokens }} 
                  (输入: {{ currentVideoAnalysis.token_usage.input_tokens }}, 
                  输出: {{ currentVideoAnalysis.token_usage.output_tokens }})
                </span>
                <span v-if="currentVideoAnalysis.token_usage.audio_seconds > 0">
                  | 音频: {{ currentVideoAnalysis.token_usage.audio_seconds.toFixed(1) }}秒
                </span>
              </template>
              <span v-else class="text-gray-300">
                (旧数据，无消耗记录。重新分析可查看)
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span><el-icon class="mr-1"><Coin /></el-icon>查看API余额：</span>
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
      
      <div v-else class="text-center py-8 text-gray-400">
        暂无分析结果
      </div>
      
      <template #footer>
        <el-button @click="videoAnalysisDialogVisible = false">关闭</el-button>
        <el-button v-if="currentVideoAnalysis && currentVideoAnalysis.status !== 'processing'" @click="refreshVideoAnalysis" :loading="loadingVideoAnalysis">
          刷新
        </el-button>
      </template>
    </el-dialog>

    <!-- AI 对比分析对话框 -->
    <el-dialog v-model="compareDialogVisible" title="AI 提交对比分析" width="700px" top="5vh">
      <div v-if="compareLoading" class="text-center py-12">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p class="mt-4 text-gray-500">正在AI对比分析中...</p>
      </div>
      <div v-else-if="compareResult" class="compare-result">
        <div class="text-center mb-6">
          <div class="inline-flex items-center gap-3 bg-blue-50 px-6 py-3 rounded-full">
            <span class="text-lg font-bold text-blue-600">进步指数: {{ compareResult.progress_score || 0 }}</span>
          </div>
        </div>
        <div class="text-sm text-gray-600 mb-4 bg-gray-50 p-3 rounded-lg">{{ compareResult.overall_comment }}</div>
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="mb-4">
              <div class="text-sm font-bold text-green-600 mb-2">改进点</div>
              <ul class="text-sm text-gray-600 pl-4">
                <li v-for="(item, i) in (compareResult.improvements || [])" :key="i" class="mb-1">{{ item }}</li>
              </ul>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="mb-4">
              <div class="text-sm font-bold text-orange-500 mb-2">仍需改进</div>
              <ul class="text-sm text-gray-600 pl-4">
                <li v-for="(item, i) in (compareResult.unchanged_issues || [])" :key="i" class="mb-1">{{ item }}</li>
              </ul>
            </div>
          </el-col>
        </el-row>
        <div v-if="compareResult.dimension_changes" class="mt-4">
          <div class="text-sm font-bold mb-3">各维度变化</div>
          <div class="grid grid-cols-2 gap-3">
            <div v-for="(val, key) in compareResult.dimension_changes" :key="key" class="flex items-center justify-between bg-gray-50 p-2 rounded">
              <span class="text-xs text-gray-600">{{ val.comment || key }}</span>
              <el-tag :type="val.change > 0 ? 'success' : val.change < 0 ? 'danger' : 'info'" size="small">
                {{ val.change > 0 ? '+' : '' }}{{ val.change }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="compareDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.submissions-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1440px;
  margin: 0 auto;
}

.ms-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.ms-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  margin: 0;
}

.ms-page-desc {
  font-size: 13px;
  color: #64748b;
  margin: 4px 0 0;
}

.submission-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  overflow: hidden;
  padding: 8px;
}

:deep(.modern-submission-table) {
  --el-table-border-color: #f1f5f9;
  --el-table-header-bg-color: #f8fafc;
}

:deep(.modern-submission-table .el-table__header th) {
  font-weight: 700;
  color: #475569;
  font-size: 13px;
  padding: 12px 10px;
}

:deep(.modern-submission-table .el-table__row) {
  transition: background-color 0.15s ease;
}

:deep(.modern-submission-table .el-table__row:hover) {
  background-color: #f8fafc !important;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 700;
}

.status-badge .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-pending {
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fef3c7;
}
.status-pending .status-dot {
  background: #f59e0b;
}

.status-approved {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #dcfce7;
}
.status-approved .status-dot {
  background: #10b981;
}

.status-rejected {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fee2e2;
}
.status-rejected .status-dot {
  background: #ef4444;
}

.status-none {
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #e2e8f0;
}
.status-none .status-dot {
  background: #94a3b8;
}

.file-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  max-width: 100%;
  transition: all 0.2s ease;
}

.file-chip:hover {
  background: #f0f9ff;
  border-color: #7dd3fc;
  transform: translateY(-1px);
}

.file-name {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.file-chip:hover .file-name {
  color: #0284c7;
  text-decoration: underline;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 4px solid;
  margin: 0 auto;
}

.score-circle.excellent {
  border-color: #67c23a;
  background: #f0f9eb;
}

.score-circle.good {
  border-color: #409eff;
  background: #ecf5ff;
}

.score-circle.fair {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.score-circle.poor {
  border-color: #f56c6c;
  background: #fef0f0;
}

.score-value {
  font-size: 36px;
  font-weight: bold;
  color: #303133;
}

.score-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.metric-card {
  height: 100%;
}

.metric-item {
  text-align: center;
  padding: 8px;
}

.metric-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.metric-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.metric-value-small {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-top: 8px;
}

.metric-unit {
  font-size: 12px;
  color: #999;
}

.metric-ideal {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.suggestions-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.suggestions-list li {
  padding: 12px;
  background: #fff7e6;
  border-left: 3px solid #e6a23c;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 14px;
  color: #606266;
}

.transcript-content {
  line-height: 1.8;
  color: #606266;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.mr-1 {
  margin-right: 4px;
}

/* 动作分析样式 */
.gesture-metric {
  text-align: center;
  padding: 12px;
}

.gesture-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.gesture-suggestions {
  background: #f0f9eb;
  border-radius: 6px;
  padding: 12px;
}

.gesture-suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.gesture-suggestions li {
  padding: 6px 0;
  color: #67c23a;
  font-size: 13px;
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

/* AI 诊断按钮脉冲动画 */
.ai-diagnosis-btn {
  position: relative;
}

.ai-diagnosis-btn::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 4px;
  background: rgba(8, 145, 178, 0.15);
  animation: diagnosis-pulse 2s infinite;
  z-index: -1;
}

@keyframes diagnosis-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 0; transform: scale(1.15); }
}

/* AI 质检结果样式 */
.check-score-bar { text-align: center; padding: 20px; border-radius: 12px; }
.check-score-bar.pass { background: #f0fdf4; border: 1px solid #dcfce7; }
.check-score-bar.warning { background: #fffbeb; border: 1px solid #fef3c7; }
.check-score-bar.fail { background: #fef2f2; border: 1px solid #fecaca; }
.check-score { font-size: 48px; font-weight: 700; line-height: 1; }
.check-score-bar.pass .check-score { color: #16a34a; }
.check-score-bar.warning .check-score { color: #d97706; }
.check-score-bar.fail .check-score { color: #dc2626; }
.check-items { display: flex; flex-direction: column; gap: 8px; }
.check-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 8px; background: #f9fafb; }
.check-item.pass { border-left: 3px solid #16a34a; }
.check-item.warning { border-left: 3px solid #d97706; }
.check-item.fail { border-left: 3px solid #dc2626; }
.check-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.check-item.pass .check-dot { background: #16a34a; }
.check-item.warning .check-dot { background: #d97706; }
.check-item.fail .check-dot { background: #dc2626; }
.check-name { font-weight: 500; font-size: 13px; min-width: 80px; }
.check-msg { font-size: 12px; color: #6b7280; flex: 1; text-align: right; }
</style>
