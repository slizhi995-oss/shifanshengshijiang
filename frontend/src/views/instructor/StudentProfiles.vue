<script setup lang="ts">
/**
 * 老师端学生画像看板
 * 班级概览 + 学生列表 + 详情查看
 */
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { RadarChart, BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import api from '@/utils/request'
import { 
  DataAnalysis, User, Trophy, Search, Refresh, View, 
  TrendCharts, ArrowUp, ArrowDown, Warning
} from '@element-plus/icons-vue'

// 注册 ECharts 组件
use([RadarChart, BarChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const loading = ref(false)
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const searchKeyword = ref('')

// 班级概览数据
const classOverview = ref<any>({
  total_students: 0,
  avg_score: 0,
  completed_rate: 0,
  score_distribution: {
    excellent: 0,
    good: 0,
    average: 0,
    pass: 0,
    fail: 0
  },
  dimension_averages: []
})

// 学生列表
const students = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 学生详情对话框
const showStudentDialog = ref(false)
const selectedStudent = ref<any>(null)
const studentProfile = ref<any>(null)
const profileLoading = ref(false)

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
      await Promise.all([fetchClassOverview(), fetchStudents()])
    }
  } catch (error) {
    ElMessage.error('获取批次失败')
  }
}

// 获取班级概览
const fetchClassOverview = async () => {
  if (!selectedSemesterId.value) return
  try {
    const res: any = await api.get('/profile/overview', {
      params: { semester_id: selectedSemesterId.value }
    })
    if (res.success) {
      classOverview.value = res.data
    }
  } catch (error) {
    // 静默失败，使用默认值
  }
}

// 获取学生列表
const fetchStudents = async () => {
  if (!selectedSemesterId.value) return
  loading.value = true
  try {
    const res: any = await api.get('/profile/students', {
      params: {
        semester_id: selectedSemesterId.value,
        page: currentPage.value,
        page_size: pageSize.value
      }
    })
    if (res.success) {
      students.value = res.data?.items || []
      total.value = res.data?.total || 0
    }
  } catch (error) {
    ElMessage.error('获取学生列表失败')
  } finally {
    loading.value = false
  }
}

// 查看学生详情
const viewStudent = async (student: any) => {
  selectedStudent.value = student
  showStudentDialog.value = true
  profileLoading.value = true
  
  try {
    const res: any = await api.get(`/profile/students/${student.student_id}`, {
      params: { semester_id: selectedSemesterId.value }
    })
    if (res.success) {
      studentProfile.value = res.data
    } else {
      studentProfile.value = res
    }
  } catch (error) {
    studentProfile.value = null
  } finally {
    profileLoading.value = false
  }
}

// 过滤后的学生列表
const filteredStudents = computed(() => {
  if (!searchKeyword.value) return students.value
  const keyword = searchKeyword.value.toLowerCase()
  return students.value.filter((s: any) => 
    s.name?.toLowerCase().includes(keyword) ||
    s.student_code?.toLowerCase().includes(keyword)
  )
})

// 分数分布饼图配置
const distributionOption = computed(() => {
  const dist = classOverview.value.score_distribution
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    color: ['#10b981', '#0891b2', '#f59e0b', '#ef4444', '#9ca3af'],
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      label: { show: false },
      data: [
        { value: dist.excellent, name: '优秀(90+)' },
        { value: dist.good, name: '良好(80-89)' },
        { value: dist.average, name: '中等(70-79)' },
        { value: dist.pass, name: '及格(60-69)' },
        { value: dist.fail, name: '不及格(<60)' }
      ]
    }]
  }
})

// 班级雷达图配置
const classRadarOption = computed(() => {
  const dims = classOverview.value.dimension_averages || []
  if (dims.length === 0) return null
  
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: dims.map((d: any) => ({ name: d.label, max: 100 })),
      center: ['50%', '50%'],
      radius: '65%',
      axisName: { color: '#666', fontSize: 10 },
      splitArea: {
        areaStyle: {
          color: ['rgba(8, 145, 178, 0.02)', 'rgba(8, 145, 178, 0.04)', 
                  'rgba(8, 145, 178, 0.06)', 'rgba(8, 145, 178, 0.08)']
        }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: dims.map((d: any) => d.score),
        name: '班级平均',
        lineStyle: { color: '#0891b2', width: 2 },
        areaStyle: { color: 'rgba(8, 145, 178, 0.2)' },
        itemStyle: { color: '#0891b2' }
      }]
    }]
  }
})

// 学生详情雷达图配置
const studentRadarOption = computed(() => {
  if (!studentProfile.value?.radar) return null
  const radar = studentProfile.value.radar
  
  return {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: radar.map((d: any) => ({ name: d.label, max: 100 })),
      center: ['50%', '50%'],
      radius: '65%',
      axisName: { color: '#666', fontSize: 10 }
    },
    series: [{
      type: 'radar',
      data: [{
        value: radar.map((d: any) => d.score),
        name: selectedStudent.value?.name,
        lineStyle: { color: '#0891b2', width: 2 },
        areaStyle: { color: 'rgba(8, 145, 178, 0.2)' },
        itemStyle: { color: '#0891b2' }
      }]
    }]
  }
})

// 获取评分等级样式
const getScoreStyle = (score: number) => {
  if (score >= 90) return 'text-emerald-600 bg-emerald-50'
  if (score >= 80) return 'text-cyan-600 bg-cyan-50'
  if (score >= 70) return 'text-amber-600 bg-amber-50'
  if (score >= 60) return 'text-red-500 bg-red-50'
  return 'text-gray-500 bg-gray-100'
}

// 刷新数据
const handleRefresh = async () => {
  await Promise.all([fetchClassOverview(), fetchStudents()])
  ElMessage.success('数据已刷新')
}

// 分页变化
const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchStudents()
}

watch(selectedSemesterId, () => {
  currentPage.value = 1
  fetchClassOverview()
  fetchStudents()
})

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading" class="profile-board-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <el-icon class="text-cyan-600"><DataAnalysis /></el-icon>
          学生画像看板
        </h2>
        <p class="text-gray-500 text-sm mt-1">查看班级整体情况和学生个人画像</p>
      </div>
      <div class="flex items-center gap-3">
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          style="width: 220px"
          size="large"
        >
          <el-option
            v-for="s in semesters"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
        <el-button :icon="Refresh" @click="handleRefresh" circle />
      </div>
    </div>

    <!-- 班级概览卡片 -->
    <div class="overview-section">
      <!-- 统计数字 -->
      <div class="stats-row">
        <div class="stat-card bg-cyan-50">
          <div class="stat-icon bg-cyan-100">
            <el-icon class="text-cyan-600 text-xl"><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-cyan-600">{{ classOverview.total_students }}</div>
            <div class="stat-label">总学生数</div>
          </div>
        </div>
        
        <div class="stat-card bg-emerald-50">
          <div class="stat-icon bg-emerald-100">
            <el-icon class="text-emerald-600 text-xl"><Trophy /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-emerald-600">{{ classOverview.avg_score }}</div>
            <div class="stat-label">平均分</div>
          </div>
        </div>
        
        <div class="stat-card bg-blue-50">
          <div class="stat-icon bg-blue-100">
            <el-icon class="text-blue-600 text-xl"><TrendCharts /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-blue-600">{{ classOverview.completed_rate }}%</div>
            <div class="stat-label">完成率</div>
          </div>
        </div>
        
        <div class="stat-card bg-amber-50">
          <div class="stat-icon bg-amber-100">
            <el-icon class="text-amber-600 text-xl"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-amber-600">{{ classOverview.score_distribution?.fail || 0 }}</div>
            <div class="stat-label">待关注</div>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="charts-row">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <span class="font-medium text-gray-800">成绩分布</span>
          </template>
          <div class="chart-container">
            <v-chart :option="distributionOption" autoresize />
          </div>
        </el-card>
        
        <el-card class="chart-card" shadow="never">
          <template #header>
            <span class="font-medium text-gray-800">班级能力雷达</span>
          </template>
          <div class="chart-container">
            <v-chart v-if="classRadarOption" :option="classRadarOption" autoresize />
            <el-empty v-else description="暂无数据" :image-size="60" />
          </div>
        </el-card>
      </div>
    </div>

    <!-- 学生列表 -->
    <el-card class="students-card" shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-bold text-gray-800">学生列表</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索姓名/学号"
            :prefix-icon="Search"
            clearable
            class="w-60"
          />
        </div>
      </template>
      
      <el-table :data="filteredStudents" stripe>
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="student_code" label="学号" width="140" />
        <el-table-column label="综合评分" width="120" align="center">
          <template #default="{ row }">
            <span 
              class="px-3 py-1 rounded-full text-sm font-medium"
              :class="getScoreStyle(row.overall_score || 0)"
            >
              {{ row.overall_score || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="提交情况" width="120" align="center">
          <template #default="{ row }">
            <span class="text-sm">
              {{ row.approved_submissions || 0 }}/{{ row.total_submissions || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag 
              v-if="(row.overall_score || 0) >= 80" 
              type="success" 
              size="small"
              effect="plain"
            >
              良好
            </el-tag>
            <el-tag 
              v-else-if="(row.overall_score || 0) >= 60" 
              type="warning" 
              size="small"
              effect="plain"
            >
              一般
            </el-tag>
            <el-tag 
              v-else-if="row.total_submissions > 0" 
              type="danger" 
              size="small"
              effect="plain"
            >
              需关注
            </el-tag>
            <el-tag v-else size="small" effect="plain">未提交</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后更新" min-width="150">
          <template #default="{ row }">
            <span class="text-sm text-gray-500">
              {{ row.last_updated ? new Date(row.last_updated).toLocaleString() : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button 
              type="primary" 
              link 
              :icon="View"
              @click="viewStudent(row)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="flex justify-center mt-4">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 学生详情对话框 -->
    <el-dialog
      v-model="showStudentDialog"
      :title="`${selectedStudent?.name} 的成长画像`"
      width="700px"
      class="student-profile-dialog"
    >
      <div v-loading="profileLoading">
        <div v-if="studentProfile" class="student-profile-content">
          <!-- 基本信息 -->
          <div class="profile-header">
            <div class="flex items-center gap-4">
              <el-avatar :size="64" class="bg-cyan-100 text-cyan-600 text-2xl font-bold">
                {{ selectedStudent?.name?.charAt(0) }}
              </el-avatar>
              <div>
                <div class="text-xl font-bold text-gray-800">{{ selectedStudent?.name }}</div>
                <div class="text-sm text-gray-500">{{ selectedStudent?.student_code }}</div>
              </div>
            </div>
            <div class="text-right">
              <div 
                class="text-3xl font-bold"
                :class="getScoreStyle(studentProfile.overall_score)"
                style="background: transparent;"
              >
                {{ studentProfile.overall_score }}
              </div>
              <div class="text-sm text-gray-500">综合评分</div>
            </div>
          </div>
          
          <!-- 统计数据 -->
          <div class="profile-stats">
            <div class="profile-stat">
              <div class="text-lg font-bold text-cyan-600">{{ studentProfile.stats?.total_submissions || 0 }}</div>
              <div class="text-xs text-gray-500">总提交</div>
            </div>
            <div class="profile-stat">
              <div class="text-lg font-bold text-emerald-600">{{ studentProfile.stats?.approved_submissions || 0 }}</div>
              <div class="text-xs text-gray-500">已通过</div>
            </div>
            <div class="profile-stat">
              <div class="text-lg font-bold text-blue-600">{{ studentProfile.stats?.average_score || 0 }}</div>
              <div class="text-xs text-gray-500">平均分</div>
            </div>
          </div>
          
          <!-- 雷达图 -->
          <div class="profile-radar">
            <div class="text-sm font-medium text-gray-700 mb-2">能力雷达</div>
            <div class="h-64">
              <v-chart v-if="studentRadarOption" :option="studentRadarOption" autoresize />
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>
          </div>
          
          <!-- 改进建议 -->
          <div v-if="studentProfile.action_items?.length > 0" class="profile-actions">
            <div class="text-sm font-medium text-gray-700 mb-2">改进建议</div>
            <div class="space-y-2">
              <div 
                v-for="(item, index) in studentProfile.action_items.slice(0, 3)" 
                :key="index"
                class="flex items-start gap-2 p-2 bg-amber-50 rounded-lg text-sm"
              >
                <el-icon class="text-amber-500 mt-0.5"><ArrowUp /></el-icon>
                <div>
                  <span class="font-medium text-gray-800">{{ item.dimension }}</span>
                  <span class="text-gray-500 ml-2">{{ item.suggestion }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无画像数据" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.profile-board-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

/* 概览区域 */
.overview-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}

@media (max-width: 1024px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border-radius: 0.75rem;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  border: none;
  border-radius: 0.75rem;
}

.chart-container {
  height: 240px;
}

/* 学生列表卡片 */
.students-card {
  border: none;
  border-radius: 0.75rem;
}

/* 学生详情对话框 */
.student-profile-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e5e7eb;
}

.profile-stats {
  display: flex;
  gap: 2rem;
  justify-content: center;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 0.75rem;
}

.profile-stat {
  text-align: center;
}

.profile-radar {
  padding: 1rem;
  background: #fafafa;
  border-radius: 0.75rem;
}

.profile-actions {
  padding: 1rem;
  background: #fffbeb;
  border-radius: 0.75rem;
}
</style>
