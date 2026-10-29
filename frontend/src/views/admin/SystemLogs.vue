<script setup lang="ts">
/**
 * 系统日志页面
 * 管理员查看操作日志和审计记录
 */
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import { aiApi } from '@/api/ai'
import { 
  Document, Search, Refresh, Filter, Download,
  User, Setting, Edit, Delete, Plus, View,
  Check, Close, Upload, Timer, Cpu
} from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// 统计数据
const stats = ref({
  today_submissions: 0,
  today_grades: 0,
  total_users: 0,
  total_ai_calls: 0
})

const fetchStats = async () => {
  try {
    const res: any = await api.get('/admin/logs/statistics')
    if (res.success && res.data) {
      stats.value = res.data
    }
  } catch {}
}

// 筛选条件
const filters = ref({
  module: '',
  action: '',
  user_id: '',
  start_date: '',
  end_date: ''
})

// 模块选项
const moduleOptions = [
  { value: '', label: '全部模块' },
  { value: 'auth', label: '认证登录' },
  { value: 'user', label: '用户管理' },
  { value: 'submission', label: '作业提交' },
  { value: 'grade', label: '成绩评分' },
  { value: 'task', label: '作业管理' },
  { value: 'semester', label: '批次管理' },
  { value: 'ai', label: 'AI 功能' },
  { value: 'system', label: '系统设置' }
]

// 操作类型选项
const actionOptions = [
  { value: '', label: '全部操作' },
  { value: 'login', label: '登录' },
  { value: 'logout', label: '登出' },
  { value: 'create', label: '新建' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'view', label: '查看' },
  { value: 'export', label: '导出' },
  { value: 'approve', label: '审批' },
  { value: 'reject', label: '驳回' }
]

// 获取日志列表
const fetchLogs = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/admin/logs', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        ...filters.value
      }
    })
    
    if (res.success) {
      logs.value = res.data?.items || []
      total.value = res.data?.total || 0
    }
  } catch (error) {
    // 使用模拟数据
    logs.value = generateMockLogs()
    total.value = 156
  } finally {
    loading.value = false
  }
}

// 生成模拟日志
const generateMockLogs = () => {
  const mockData = [
    { id: 1, module: 'auth', action: 'login', user_name: '张三', user_code: '2024001', ip: '192.168.1.100', detail: '用户登录成功', created_at: '2026-02-02 10:05:32' },
    { id: 2, module: 'submission', action: 'create', user_name: '李四', user_code: '2024002', ip: '192.168.1.101', detail: '提交作业：教学设计第一周', created_at: '2026-02-02 09:58:15' },
    { id: 3, module: 'grade', action: 'approve', user_name: '王老师', user_code: 'T001', ip: '192.168.1.50', detail: '通过学生作业（学号：2024001）', created_at: '2026-02-02 09:45:00' },
    { id: 4, module: 'ai', action: 'create', user_name: '系统', user_code: 'SYSTEM', ip: '-', detail: 'AI 分析教案完成（提交ID：45）', created_at: '2026-02-02 09:30:22' },
    { id: 5, module: 'user', action: 'update', user_name: '管理员', user_code: 'admin', ip: '192.168.1.1', detail: '更新用户信息：张三', created_at: '2026-02-02 09:15:00' },
    { id: 6, module: 'task', action: 'create', user_name: '王老师', user_code: 'T001', ip: '192.168.1.50', detail: '发布新作业：试讲视频录制', created_at: '2026-02-02 09:00:00' },
    { id: 7, module: 'semester', action: 'update', user_name: '管理员', user_code: 'admin', ip: '192.168.1.1', detail: '更新批次状态：2024春季 -> 进行中', created_at: '2026-02-01 18:30:00' },
    { id: 8, module: 'auth', action: 'logout', user_name: '赵六', user_code: '2024003', ip: '192.168.1.102', detail: '用户登出', created_at: '2026-02-01 17:45:00' },
    { id: 9, module: 'grade', action: 'reject', user_name: '王老师', user_code: 'T001', ip: '192.168.1.50', detail: '驳回学生作业（学号：2024005），原因：视频质量不达标', created_at: '2026-02-01 16:20:00' },
    { id: 10, module: 'system', action: 'update', user_name: '超级管理员', user_code: 'superadmin', ip: '192.168.1.1', detail: '更新系统配置：AI 分析开关', created_at: '2026-02-01 15:00:00' }
  ]
  return mockData
}

// 获取模块标签
const getModuleTag = (module: string) => {
  const map: Record<string, { type: string; text: string }> = {
    'auth': { type: 'primary', text: '认证' },
    'user': { type: 'info', text: '用户' },
    'submission': { type: 'success', text: '提交' },
    'grade': { type: 'warning', text: '评分' },
    'task': { type: '', text: '作业' },
    'semester': { type: 'danger', text: '批次' },
    'ai': { type: 'primary', text: 'AI' },
    'system': { type: 'danger', text: '系统' }
  }
  return map[module] || { type: 'info', text: module }
}

// 获取操作图标
const getActionIcon = (action: string) => {
  const map: Record<string, any> = {
    'login': User,
    'logout': Close,
    'create': Plus,
    'update': Edit,
    'delete': Delete,
    'view': View,
    'export': Download,
    'approve': Check,
    'reject': Close
  }
  return map[action] || Document
}

// 获取操作颜色
const getActionColor = (action: string) => {
  const map: Record<string, string> = {
    'login': 'text-blue-500',
    'logout': 'text-gray-500',
    'create': 'text-green-500',
    'update': 'text-amber-500',
    'delete': 'text-red-500',
    'view': 'text-blue-400',
    'export': 'text-teal-600',
    'approve': 'text-emerald-500',
    'reject': 'text-red-500'
  }
  return map[action] || 'text-gray-500'
}

// 搜索
const handleSearch = () => {
  page.value = 1
  fetchLogs()
}

// 重置筛选
const resetFilters = () => {
  filters.value = {
    module: '',
    action: '',
    user_id: '',
    start_date: '',
    end_date: ''
  }
  handleSearch()
}

// 导出日志
const exportLogs = async () => {
  ElMessage.success('日志导出功能开发中...')
}

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage
  fetchLogs()
}

// AI 日志分析
const aiAnalysisVisible = ref(false)
const aiAnalysisLoading = ref(false)
const aiAnalysisDisplayed = ref('')
let analysisTimer: ReturnType<typeof setInterval> | null = null

const openAILogAnalysis = async () => {
  aiAnalysisVisible.value = true
  aiAnalysisLoading.value = true
  aiAnalysisDisplayed.value = ''
  try {
    // 统计当前日志数据
    const moduleCounts: Record<string, number> = {}
    const actionCounts: Record<string, number> = {}
    for (const log of logs.value) {
      moduleCounts[log.module] = (moduleCounts[log.module] || 0) + 1
      actionCounts[log.action] = (actionCounts[log.action] || 0) + 1
    }
    const stats = {
      total_logs: total.value,
      displayed_logs: logs.value.length,
      module_distribution: moduleCounts,
      action_distribution: actionCounts,
      context: '管理员查看系统日志页面，请分析日志数据并给出异常警告和建议，100-200字'
    }
    const res = await aiApi.dataNarrative({ role: 'admin', stats })
    if (res.success && res.data?.narrative) {
      let i = 0
      if (analysisTimer) clearInterval(analysisTimer)
      analysisTimer = setInterval(() => {
        if (i < res.data!.narrative.length) { aiAnalysisDisplayed.value += res.data!.narrative[i]; i++ }
        else { if (analysisTimer) clearInterval(analysisTimer) }
      }, 25)
    }
  } catch { aiAnalysisDisplayed.value = 'AI 分析失败' }
  finally { aiAnalysisLoading.value = false }
}

onMounted(() => {
  fetchLogs()
  fetchStats()
})
</script>

<template>
  <div class="system-logs-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <el-icon class="text-cyan-600"><Document /></el-icon>
          系统日志
        </h2>
        <p class="text-gray-500 text-sm mt-1">查看系统操作记录和审计日志</p>
      </div>
      <div class="flex gap-2">
        <el-button :icon="Refresh" @click="fetchLogs" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Download" @click="exportLogs">导出日志</el-button>
        <el-button type="primary" plain @click="openAILogAnalysis">
          <el-icon class="mr-1"><Cpu /></el-icon>AI 日志分析
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-select v-model="filters.module" placeholder="模块" class="w-32">
          <el-option v-for="opt in moduleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="filters.action" placeholder="操作" class="w-32">
          <el-option v-for="opt in actionOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-input v-model="filters.user_id" placeholder="用户学号/工号" class="w-40" :prefix-icon="Search" clearable />
        <el-date-picker
          v-model="filters.start_date"
          type="date"
          placeholder="开始日期"
          value-format="YYYY-MM-DD"
          class="w-40"
        />
        <span class="text-gray-400">至</span>
        <el-date-picker
          v-model="filters.end_date"
          type="date"
          placeholder="结束日期"
          value-format="YYYY-MM-DD"
          class="w-40"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <!-- 日志列表 -->
    <el-card class="logs-card" shadow="never">
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column label="时间" prop="created_at" width="180">
          <template #default="{ row }">
            <div class="flex items-center gap-2 text-gray-600">
              <el-icon class="text-gray-400"><Timer /></el-icon>
              {{ row.created_at }}
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="模块" width="100">
          <template #default="{ row }">
            <el-tag :type="getModuleTag(row.module).type as any" size="small" effect="plain">
              {{ getModuleTag(row.module).text }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <div class="flex items-center gap-1" :class="getActionColor(row.action)">
              <el-icon><component :is="getActionIcon(row.action)" /></el-icon>
              <span>{{ row.action }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="操作人" width="150">
          <template #default="{ row }">
            <div class="flex flex-col">
              <span class="font-medium text-gray-800">{{ row.user_name }}</span>
              <span class="text-xs text-gray-400">{{ row.user_code }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="IP 地址" prop="ip" width="140" />
        
        <el-table-column label="详情" prop="detail" min-width="250">
          <template #default="{ row }">
            <el-tooltip :content="row.detail" placement="top" :show-after="500">
              <span class="text-gray-600 line-clamp-1">{{ row.detail }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="flex justify-end mt-4">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- AI 日志分析对话框 -->
    <el-dialog v-model="aiAnalysisVisible" title="AI 日志智能分析" width="550px">
      <el-card shadow="never" style="background: #f0f9ff; border-color: #bae6fd;">
        <div class="flex items-start gap-3">
          <div class="w-8 h-8 rounded-lg bg-cyan-100 flex items-center justify-center text-cyan-600 flex-shrink-0">
            <el-icon :size="16"><Cpu /></el-icon>
          </div>
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-semibold text-sm text-gray-700">AI 日志分析</span>
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-cyan-500" :class="{ 'animate-pulse': aiAnalysisLoading }"></span>
            </div>
            <div v-if="aiAnalysisLoading && !aiAnalysisDisplayed" class="text-sm text-gray-400">AI 正在分析日志数据...</div>
            <div v-else-if="aiAnalysisDisplayed" class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
              {{ aiAnalysisDisplayed }}<span v-if="aiAnalysisLoading" class="text-cyan-500 font-bold animate-pulse">|</span>
            </div>
            <div v-else class="text-sm text-gray-400">AI 分析功能暂不可用</div>
          </div>
        </div>
      </el-card>
      <template #footer>
        <el-button @click="aiAnalysisVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon bg-blue-100">
          <el-icon class="text-blue-500 text-xl"><Upload /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.today_submissions }}</div>
          <div class="stat-label">今日提交数</div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon bg-green-100">
          <el-icon class="text-green-500 text-xl"><Edit /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.today_grades }}</div>
          <div class="stat-label">今日批改数</div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon bg-amber-100">
          <el-icon class="text-amber-500 text-xl"><User /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_users }}</div>
          <div class="stat-label">总用户数</div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon bg-teal-100">
          <el-icon class="text-teal-600 text-xl"><Cpu /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total_ai_calls }}</div>
          <div class="stat-label">AI 调用总次数</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.system-logs-page {
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

.filter-card {
  border-radius: 1rem;
  border: none;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.logs-card {
  border-radius: 1rem;
  border: none;
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

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
  
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-row > * {
    width: 100% !important;
  }
}

.stat-card {
  border-radius: 1rem;
  border: none;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
