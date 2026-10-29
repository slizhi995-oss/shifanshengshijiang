<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Download, View, VideoCamera, Cpu, TrendCharts, DataLine } from '@element-plus/icons-vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { aiApi } from '@/api/ai'
import VideoAnalysisCard from '@/components/VideoAnalysisCard.vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, LineChart, RadarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const authStore = useAuthStore()

const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const students = ref<any[]>([])
const loading = ref(false)
const total = ref(0)

// 筛选条件
const filterOptions = ref<{ colleges: string[], majors: string[], classes: string[] }>({
  colleges: [],
  majors: [],
  classes: [],
})
const filterCollege = ref('')
const filterMajor = ref('')
const filterClass = ref('')
const keyword = ref('')

// 分页
const pagination = ref({
  page: 1,
  page_size: 20,
})

// 学生详情对话框
const detailDialogVisible = ref(false)
const selectedStudent = ref<any>(null)
const studentDetail = ref<any>(null)
const detailLoading = ref(false)

// 视频分析对话框
const videoAnalysisDialogVisible = ref(false)
const currentAnalysisSubmissionId = ref<number | null>(null)
const currentAnalysisSubmission = ref<any>(null)

// AI 成绩洞察
const insightData = ref<any>(null)
const insightLoading = ref(false)
const aiNarrative = ref('')
const aiNarrativeDisplayed = ref('')
const aiNarrativeLoading = ref(false)
let narrativeTimer: ReturnType<typeof setInterval> | null = null

// 是否为超级管理员
const isSuperAdmin = computed(() => authStore.user?.is_super_admin)

// 是否为指导老师
const isInstructor = computed(() => authStore.userRole === 'instructor')

// 获取批次列表
const fetchSemesters = async () => {
  const res: any = await api.get('/semesters')
  semesters.value = res.filter((s: any) => s.status === 'active' || s.status === 'completed')
  if (semesters.value.length > 0 && !selectedSemesterId.value) {
    selectedSemesterId.value = semesters.value[0].id
    fetchStudents()
  }
}

// 获取筛选选项
const fetchFilterOptions = async () => {
  try {
    const res: any = await api.get('/grades/filter-options')
    filterOptions.value = res
  } catch (error) {
    // Error handled by interceptor
  }
}

// 获取学生列表
const fetchStudents = async () => {
  if (!selectedSemesterId.value) return
  
  loading.value = true
  try {
    const params: any = {
      semester_id: selectedSemesterId.value,
      page: pagination.value.page,
      page_size: pagination.value.page_size,
    }
    
    if (filterCollege.value) params.college = filterCollege.value
    if (filterMajor.value) params.major = filterMajor.value
    if (filterClass.value) params.class_name = filterClass.value
    if (keyword.value) params.keyword = keyword.value
    
    const res: any = await api.get('/grades/students', { params })
    students.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

// 批次切换
const handleSemesterChange = () => {
  pagination.value.page = 1
  filterCollege.value = ''
  filterMajor.value = ''
  filterClass.value = ''
  keyword.value = ''
  fetchStudents()
}

// 搜索
const handleSearch = () => {
  pagination.value.page = 1
  fetchStudents()
}

// 分页
const handlePageChange = (page: number) => {
  pagination.value.page = page
  fetchStudents()
}

// 查看详情
const handleViewDetail = async (student: any) => {
  selectedStudent.value = student
  detailDialogVisible.value = true
  detailLoading.value = true
  
  try {
    const res: any = await api.get(`/grades/students/${student.id}/detail`, {
      params: { semester_id: selectedSemesterId.value }
    })
    studentDetail.value = res
  } finally {
    detailLoading.value = false
  }
}

// 打开文件
const openFile = (path: string) => {
  if (!path) return
  window.open(`/uploads/${path}`, '_blank')
}

// 查看视频分析
const viewVideoAnalysis = (submission: any) => {
  currentAnalysisSubmission.value = submission
  currentAnalysisSubmissionId.value = submission.id
  videoAnalysisDialogVisible.value = true
}

// 获取状态标签类型
const getStatusType = (status: string) => {
  const typeMap: any = {
    'pending': 'warning',
    'approved': 'success',
    'rejected': 'danger',
  }
  return typeMap[status] || ''
}

// 获取状态文本
const getStatusText = (status: string) => {
  const textMap: any = {
    'pending': '待批改',
    'approved': '已通过',
    'rejected': '已驳回',
  }
  return textMap[status] || status
}

// 导出成绩
const handleExport = async () => {
  if (!selectedSemesterId.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  
  ElMessage.info('导出功能开发中...')
}

// AI 成绩洞察
const fetchAIInsight = async () => {
  if (!selectedSemesterId.value) return
  insightLoading.value = true
  try {
    const res: any = await api.get('/grades/ai-insight', { params: { semester_id: selectedSemesterId.value } })
    if (res.success && res.data) {
      insightData.value = res.data
      fetchInsightNarrative(res.data)
    }
  } catch { insightData.value = null }
  finally { insightLoading.value = false }
}

const typewriterEffect = (text: string) => {
  aiNarrativeDisplayed.value = ''
  let i = 0
  if (narrativeTimer) clearInterval(narrativeTimer)
  narrativeTimer = setInterval(() => {
    if (i < text.length) { aiNarrativeDisplayed.value += text[i]; i++ }
    else { if (narrativeTimer) clearInterval(narrativeTimer) }
  }, 30)
}

const fetchInsightNarrative = async (data: any) => {
  aiNarrativeLoading.value = true
  try {
    const stats = {
      total_students: data.total_students,
      total_submissions: data.total_submissions,
      pass_rate: data.pass_rate,
      avg_score: data.avg_score,
      weakest_dimension: data.weakest_dimension,
      approved: data.approved,
      rejected: data.rejected,
      context: '管理员查看学生成绩页面，分析整体教学质量'
    }
    const res = await aiApi.dataNarrative({ role: 'admin', stats })
    if (res.success && res.data?.narrative) {
      aiNarrative.value = res.data.narrative
      typewriterEffect(res.data.narrative)
    }
  } catch { aiNarrative.value = '' }
  finally { aiNarrativeLoading.value = false }
}

// 班级对比柱状图
const classBarOption = computed(() => {
  if (!insightData.value?.class_comparison?.length) return null
  const data = insightData.value.class_comparison
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: data.map((c: any) => c.class_name), axisLabel: { fontSize: 11, rotate: 15 } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar', data: data.map((c: any) => c.avg_score), barWidth: '50%',
      itemStyle: { borderRadius: [4, 4, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#0891b2' }, { offset: 1, color: '#06b6d4' }] } },
      label: { show: true, position: 'top', fontSize: 11 }
    }]
  }
})

// 维度雷达图
const dimRadarOption = computed(() => {
  if (!insightData.value?.dimensions?.length) return null
  const dims = insightData.value.dimensions
  return {
    tooltip: {},
    radar: {
      indicator: dims.map((d: any) => ({ name: d.label, max: 100 })),
      radius: '65%',
      splitLine: { lineStyle: { color: '#e5e7eb' } },
      axisName: { fontSize: 11 }
    },
    series: [{ type: 'radar', data: [{
      value: dims.map((d: any) => d.avg_score),
      name: '全校平均',
      itemStyle: { color: '#0891b2' },
      areaStyle: { color: 'rgba(8,145,178,0.15)' }
    }] }]
  }
})

// 成长趋势（学生详情中的多次提交分数走势）
const growthTrendOption = computed(() => {
  if (!studentDetail.value?.submissions?.length) return null
  const subs = studentDetail.value.submissions
    .filter((s: any) => s.score !== null)
    .sort((a: any, b: any) => new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime())
  if (subs.length < 1) return null
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: subs.map((_: any, i: number) => `第${i+1}次`), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'line', data: subs.map((s: any) => s.score), smooth: true, showSymbol: true,
      lineStyle: { color: '#10b981', width: 3 }, itemStyle: { color: '#10b981' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.3)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } },
      markLine: { data: [{ type: 'average', name: '平均分' }], lineStyle: { color: '#f59e0b' } }
    }]
  }
})

watch(selectedSemesterId, () => {
  if (selectedSemesterId.value) fetchAIInsight()
})

onMounted(() => {
  fetchSemesters()
  fetchFilterOptions()
})
</script>

<template>
  <div v-loading="loading" class="h-full flex flex-col">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-bold">学生成绩</h2>
      <div class="flex items-center gap-3">
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          @change="handleSemesterChange"
          style="width: 200px"
        >
          <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-button :icon="Download" @click="handleExport">导出成绩</el-button>
      </div>
    </div>

    <!-- AI 成绩洞察面板 -->
    <div v-if="insightData" v-loading="insightLoading" class="mb-4">
      <!-- AI 叙事 -->
      <el-card shadow="never" class="!rounded-2xl !border-cyan-100 mb-4" style="background: #f0f9ff;">
        <div class="flex items-start gap-3">
          <div class="w-9 h-9 rounded-lg bg-cyan-100 flex items-center justify-center text-cyan-600 flex-shrink-0">
            <el-icon :size="18"><Cpu /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-semibold text-sm text-gray-700">AI 成绩洞察</span>
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse"></span>
              <span class="text-xs text-cyan-600">AI 分析</span>
            </div>
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="text-sm text-gray-400">AI 正在分析成绩数据...</div>
            <div v-else-if="aiNarrativeDisplayed" class="text-sm text-gray-600 leading-relaxed">
              {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="text-cyan-500 font-bold animate-pulse">|</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 统计卡片行 -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div class="bg-white rounded-xl border p-3 text-center">
          <div class="text-2xl font-bold text-blue-600">{{ insightData.total_students }}</div>
          <div class="text-xs text-gray-500 mt-1">学生总数</div>
        </div>
        <div class="bg-white rounded-xl border p-3 text-center">
          <div class="text-2xl font-bold text-green-600">{{ insightData.pass_rate }}%</div>
          <div class="text-xs text-gray-500 mt-1">通过率</div>
        </div>
        <div class="bg-white rounded-xl border p-3 text-center">
          <div class="text-2xl font-bold text-orange-600">{{ insightData.avg_score }}</div>
          <div class="text-xs text-gray-500 mt-1">平均分</div>
        </div>
        <div class="bg-white rounded-xl border p-3 text-center">
          <div class="text-2xl font-bold text-red-500">{{ insightData.rejected }}</div>
          <div class="text-xs text-gray-500 mt-1">驳回数</div>
        </div>
        <div class="bg-white rounded-xl border p-3 text-center">
          <div class="text-2xl font-bold text-cyan-600">{{ insightData.weakest_dimension || '-' }}</div>
          <div class="text-xs text-gray-500 mt-1">最弱维度</div>
        </div>
      </div>

      <!-- 图表行 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <el-card shadow="never" class="!rounded-xl">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon class="text-cyan-600"><DataLine /></el-icon>
              <span class="font-medium text-sm">班级平均分对比</span>
            </div>
          </template>
          <v-chart v-if="classBarOption" :option="classBarOption" style="height: 220px;" autoresize />
          <el-empty v-else description="暂无班级对比数据" :image-size="50" />
        </el-card>
        <el-card shadow="never" class="!rounded-xl">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon class="text-cyan-600"><TrendCharts /></el-icon>
              <span class="font-medium text-sm">教学维度雷达</span>
              <el-tag size="small" effect="plain" type="info">AI</el-tag>
            </div>
          </template>
          <v-chart v-if="dimRadarOption" :option="dimRadarOption" style="height: 220px;" autoresize />
          <el-empty v-else description="暂无维度分析数据" :image-size="50" />
        </el-card>
      </div>
    </div>

    <el-card class="flex-1" body-style="height: 100%; display: flex; flex-direction: column;">
      <!-- 筛选条件 -->
      <div class="mb-4 flex items-center gap-3 flex-wrap">
        <el-select 
          v-if="isSuperAdmin" 
          v-model="filterCollege" 
          placeholder="学院" 
          clearable 
          size="small" 
          style="width: 140px"
        >
          <el-option v-for="c in filterOptions.colleges" :key="c" :label="c" :value="c" />
        </el-select>
        <el-select 
          v-model="filterMajor" 
          placeholder="专业" 
          clearable 
          size="small" 
          style="width: 140px"
        >
          <el-option v-for="m in filterOptions.majors" :key="m" :label="m" :value="m" />
        </el-select>
        <el-select 
          v-model="filterClass" 
          placeholder="班级" 
          clearable 
          size="small" 
          style="width: 140px"
        >
          <el-option v-for="c in filterOptions.classes" :key="c" :label="c" :value="c" />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索姓名/学号"
          :prefix-icon="Search"
          clearable
          size="small"
          style="width: 200px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" size="small" @click="handleSearch">查询</el-button>
      </div>

      <!-- 数据表格 -->
      <div class="flex-1 overflow-hidden">
        <el-table :data="students" stripe height="100%" style="width: 100%">
          <el-table-column prop="user_code" label="学号" width="120" fixed />
          <el-table-column prop="name" label="姓名" width="100" fixed />
          <el-table-column prop="college" label="学院" min-width="150" show-overflow-tooltip v-if="isSuperAdmin" />
          <el-table-column prop="major" label="专业" min-width="120" show-overflow-tooltip />
          <el-table-column prop="class_name" label="班级" min-width="120" />
          <el-table-column label="指导老师" min-width="120" v-if="!isInstructor">
          <template #default="{ row }">
            {{ row.instructor?.name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="作业统计" min-width="200" v-if="selectedSemesterId">
          <template #default="{ row }">
            <div v-if="row.statistics" class="text-sm">
              <div>
                <span class="text-gray-600">已提交：</span>
                <span class="font-medium">{{ row.statistics.submitted }}/{{ row.statistics.total_tasks }}</span>
              </div>
              <div class="flex gap-2 mt-1">
                <el-tag size="small" type="success">通过 {{ row.statistics.approved }}</el-tag>
                <el-tag size="small" type="warning">待批 {{ row.statistics.pending }}</el-tag>
                <el-tag size="small" type="danger" v-if="row.statistics.rejected > 0">
                  驳回 {{ row.statistics.rejected }}
                </el-tag>
              </div>
            </div>
            <span v-else class="text-gray-400">未分配</span>
          </template>
        </el-table-column>
        <el-table-column label="最终成绩" width="100" v-if="selectedSemesterId">
          <template #default="{ row }">
            <span v-if="row.statistics?.final_score !== null && row.statistics?.final_score !== undefined" class="font-medium text-blue-600">
              {{ row.statistics.final_score }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="完成率" width="120" v-if="selectedSemesterId">
          <template #default="{ row }">
            <el-progress 
              v-if="row.statistics"
              :percentage="row.statistics.completion_rate" 
              :status="row.statistics.completion_rate === 100 ? 'success' : ''"
            />
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              :icon="View" 
              @click="handleViewDetail(row)"
              :disabled="!selectedSemesterId"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
        </el-table>
      </div>

      <!-- 分页 -->
      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.page_size"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 学生详情对话框 -->
    <el-dialog 
      v-model="detailDialogVisible" 
      :title="`${selectedStudent?.name} 的成绩详情`"
      width="900px"
      top="5vh"
    >
      <div v-loading="detailLoading">
        <div v-if="studentDetail">
          <!-- 基本信息 -->
          <el-descriptions :column="2" border class="mb-4">
            <el-descriptions-item label="学号">{{ studentDetail.student.user_code }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ studentDetail.student.name }}</el-descriptions-item>
            <el-descriptions-item label="学院">{{ studentDetail.student.college || '-' }}</el-descriptions-item>
            <el-descriptions-item label="专业">{{ studentDetail.student.major || '-' }}</el-descriptions-item>
            <el-descriptions-item label="班级">{{ studentDetail.student.class_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="指导老师">
              {{ studentDetail.instructor?.name || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- 统计信息 -->
          <div class="grid grid-cols-5 gap-3 mb-4">
            <el-card shadow="hover">
              <div class="text-center">
                <div class="text-2xl font-bold text-blue-600">{{ studentDetail.statistics.total_tasks }}</div>
                <div class="text-sm text-gray-500 mt-1">总作业数</div>
              </div>
            </el-card>
            <el-card shadow="hover">
              <div class="text-center">
                <div class="text-2xl font-bold text-green-600">{{ studentDetail.statistics.approved }}</div>
                <div class="text-sm text-gray-500 mt-1">已通过</div>
              </div>
            </el-card>
            <el-card shadow="hover">
              <div class="text-center">
                <div class="text-2xl font-bold text-orange-600">
                  {{ studentDetail.statistics.avg_score || '-' }}
                </div>
                <div class="text-sm text-gray-500 mt-1">平均成绩</div>
              </div>
            </el-card>
            <el-card shadow="hover">
              <div class="text-center">
                <div class="text-2xl font-bold text-red-600">
                  {{ studentDetail.submissions && studentDetail.submissions.length > 0 ? 
                    (studentDetail.submissions.filter((s: any) => s.score !== null).sort((a: any, b: any) => 
                      new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime()
                    )[0]?.score || '-') : '-' }}
                </div>
                <div class="text-sm text-gray-500 mt-1">最终成绩</div>
              </div>
            </el-card>
            <el-card shadow="hover">
              <div class="text-center">
                <div class="text-2xl font-bold text-teal-600">
                  {{ studentDetail.statistics.completion_rate }}%
                </div>
                <div class="text-sm text-gray-500 mt-1">完成率</div>
              </div>
            </el-card>
          </div>

          <!-- 成长趋势图 -->
          <div v-if="growthTrendOption" class="mb-4">
            <el-card shadow="never" class="!rounded-xl !border-green-100">
              <template #header>
                <div class="flex items-center gap-2">
                  <el-icon class="text-green-600"><TrendCharts /></el-icon>
                  <span class="font-medium text-sm">成绩成长趋势</span>
                  <el-tag size="small" effect="plain" type="success">AI</el-tag>
                </div>
              </template>
              <v-chart :option="growthTrendOption" style="height: 200px;" autoresize />
            </el-card>
          </div>

          <!-- 提交记录 -->
          <div class="mb-2 font-medium text-lg">提交记录</div>
          <el-table :data="studentDetail.submissions" stripe max-height="400">
            <el-table-column prop="task_title" label="作业名称" min-width="150" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="成绩" width="80">
              <template #default="{ row }">
                <span v-if="row.score !== null" class="font-medium text-blue-600">
                  {{ row.score }}
                </span>
                <span v-else class="text-gray-400">-</span>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="160">
              <template #default="{ row }">
                <span v-if="row.submitted_at">
                  {{ new Date(row.submitted_at).toLocaleString() }}
                </span>
                <span v-else class="text-gray-400">未提交</span>
              </template>
            </el-table-column>
            <el-table-column label="教案" width="100">
              <template #default="{ row }">
                <el-button 
                  v-if="row.lesson_plan_path" 
                  size="small" 
                  @click="openFile(row.lesson_plan_path)"
                >
                  查看
                </el-button>
                <span v-else class="text-gray-400">无</span>
              </template>
            </el-table-column>
            <el-table-column label="视频" width="100">
              <template #default="{ row }">
                <el-button 
                  v-if="row.video_path" 
                  size="small" 
                  @click="openFile(row.video_path)"
                >
                  查看
                </el-button>
                <span v-else class="text-gray-400">无</span>
              </template>
            </el-table-column>
            <el-table-column label="视频分析" width="100">
              <template #default="{ row }">
                <el-button 
                  v-if="row.video_path" 
                  size="small"
                  type="primary"
                  link
                  @click="viewVideoAnalysis(row)"
                >
                  <el-icon class="mr-1"><VideoCamera /></el-icon>
                  分析
                </el-button>
                <span v-else class="text-gray-400">-</span>
              </template>
            </el-table-column>
            <el-table-column label="反馈" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.feedback || '-' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

    <!-- 视频分析对话框 -->
    <el-dialog
      v-model="videoAnalysisDialogVisible"
      title="视频AI分析报告"
      width="900px"
      top="5vh"
    >
      <div v-if="currentAnalysisSubmission" class="mb-4">
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="作业">{{ currentAnalysisSubmission.task_title }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentAnalysisSubmission.status)" size="small">
              {{ getStatusText(currentAnalysisSubmission.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="成绩">
            <span v-if="currentAnalysisSubmission.score !== null" class="font-medium text-blue-600">
              {{ currentAnalysisSubmission.score }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      
      <VideoAnalysisCard
        v-if="currentAnalysisSubmissionId"
        :submission-id="currentAnalysisSubmissionId"
        :can-trigger="true"
        :can-reanalyze="isSuperAdmin || isInstructor"
      />
      
      <template #footer>
        <el-button @click="videoAnalysisDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
:deep(.el-progress__text) {
  font-size: 12px !important;
}

.mr-1 {
  margin-right: 4px;
}
</style>
