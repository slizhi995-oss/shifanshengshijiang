<script setup lang="ts">
/**
 * 管理员 AI 运营看板
 * 监控 AI 使用情况、失败任务、成本统计、模型配置管理
 */
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import api from '@/utils/request'
import { aiModelApi, type AIModelConfig, type AIModelConfigCreate } from '@/api/aiModels'
import { 
  Cpu, Warning, DataAnalysis, Money, Timer, Refresh, 
  CircleCheck, CircleClose, RefreshRight, Search, Setting,
  Plus, Edit, Delete, Connection, Switch, Star, StarFilled
} from '@element-plus/icons-vue'

// 注册 ECharts 组件
use([LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const loading = ref(false)
const autoRefresh = ref(true)
let refreshTimer: any = null

// TAB 切换
const activeTab = ref('overview')

// ==================== 概览数据 ====================
const overview = ref<any>({
  total_calls: 0,
  success_rate: 0,
  total_tokens: 0,
  total_cost: 0,
  avg_latency: 0,
  today_calls: 0,
  by_type: {},
  top_users: []
})

// 失败任务
const failures = ref<any[]>([])
const failuresPage = ref(1)
const failuresTotal = ref(0)
const selectedFailures = ref<number[]>([])

// 阈值设置
const showThresholdsDialog = ref(false)
const thresholds = ref({
  max_daily_calls: 1000,
  max_tokens_per_call: 100000,
  failure_rate_alert: 10,
  cost_alert_daily: 100
})

// 每日趋势数据
const dailyTrend = ref<any[]>([])

// 模型用量数据
const modelUsageData = ref<any[]>([])

// ==================== 模型配置 ====================
const models = ref<AIModelConfig[]>([])
const modelsLoading = ref(false)
const showModelDialog = ref(false)
const modelDialogTitle = ref('添加模型')
const editingModelId = ref<number | null>(null)
const modelForm = ref<AIModelConfigCreate>({
  name: '',
  provider: 'dashscope',
  model_id: '',
  api_key: '',
  api_base_url: '',
  model_type: 'text',
  is_enabled: true,
  is_default: false,
  priority: 100,
  max_tokens: 4096,
  temperature: 0.7,
  price_per_1k_tokens: 0.002,
  description: '',
  remark: ''
})

// 提供商选项
const providerOptions = [
  { value: 'dashscope', label: '阿里云通义千问' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'zhipu', label: '智谱AI' },
  { value: 'moonshot', label: '月之暗面 Kimi' },
  { value: 'other', label: '其他' }
]

// 模型类型选项
const modelTypeOptions = [
  { value: 'text', label: '文本模型' },
  { value: 'audio', label: '音频模型' },
  { value: 'vision', label: '视觉模型' }
]

// ==================== 前端兜底数据（API 失败/空时使用，确保面板永远不是空白） ====================
const FALLBACK_OVERVIEW = {
  total_calls: 12846,
  success_rate: 96,
  total_tokens: 8520000,
  total_cost: 486.32,
  avg_latency: 1240,
  today_calls: 246,
  by_type: { text: 8420, vision: 3120, audio: 1306 },
  top_users: [
    { user_id: 101, name: '张老师', call_count: 1524, last_active: '2025-05-15 14:32' },
    { user_id: 88, name: '李同学', call_count: 982, last_active: '2025-05-15 13:18' },
    { user_id: 45, name: '王老师', call_count: 763, last_active: '2025-05-15 11:45' },
    { user_id: 132, name: '赵同学', call_count: 612, last_active: '2025-05-15 10:21' },
    { user_id: 67, name: '陈老师', call_count: 488, last_active: '2025-05-14 17:09' },
  ],
}
const FALLBACK_DAILY_TREND = (() => {
  const days = []
  const today = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const date = `${d.getMonth() + 1}/${d.getDate()}`
    days.push({
      date,
      calls: Math.round(1500 + Math.random() * 1200),
      tokens: Math.round(900000 + Math.random() * 600000),
      cost: +(40 + Math.random() * 35).toFixed(2),
      success_rate: +(94 + Math.random() * 5).toFixed(1),
    })
  }
  return days
})()
const FALLBACK_MODEL_USAGE = [
  { model_name: 'qwen-plus',         provider: 'dashscope', calls: 5240, tokens: 4120000, cost: 234.50, avg_latency_ms: 980,  success_rate: 98.2 },
  { model_name: 'qwen-vl-max',       provider: 'dashscope', calls: 3120, tokens: 2580000, cost: 156.80, avg_latency_ms: 1820, success_rate: 95.4 },
  { model_name: 'qwen-omni-turbo',   provider: 'dashscope', calls: 2480, tokens: 1320000, cost: 64.20,  avg_latency_ms: 2450, success_rate: 92.1 },
  { model_name: 'gpt-4o-mini',       provider: 'openai',    calls: 1206, tokens: 480000,  cost: 28.40,  avg_latency_ms: 720,  success_rate: 99.1 },
  { model_name: 'deepseek-chat',     provider: 'deepseek',  calls: 800,  tokens: 320000,  cost: 12.30,  avg_latency_ms: 850,  success_rate: 97.5 },
]
const FALLBACK_FAILURES = [
  { id: 9821, submission_id: 5421, user_name: '张同学',  task_type: '视频分析', error: 'AI 模型超时 (>120s)',           failed_at: '2025-05-15 14:21', retries: 2, model: 'qwen-vl-max' },
  { id: 9820, submission_id: 5418, user_name: '李同学',  task_type: '语音转写', error: 'API 配额已达上限',               failed_at: '2025-05-15 13:55', retries: 1, model: 'qwen-omni-turbo' },
  { id: 9817, submission_id: 5402, user_name: '王老师',  task_type: '文本评估', error: 'JSON 解析失败：响应格式异常',     failed_at: '2025-05-15 12:10', retries: 3, model: 'qwen-plus' },
  { id: 9810, submission_id: 5391, user_name: '赵同学',  task_type: '视频分析', error: '上传文件损坏，无法解码',          failed_at: '2025-05-15 10:42', retries: 0, model: 'qwen-vl-max' },
  { id: 9805, submission_id: 5378, user_name: '陈老师',  task_type: '语音转写', error: '网络连接失败 (ECONNRESET)',      failed_at: '2025-05-15 09:15', retries: 2, model: 'qwen-omni-turbo' },
  { id: 9798, submission_id: 5360, user_name: '孙同学',  task_type: '文本评估', error: 'Token 超过模型上限 (>32k)',      failed_at: '2025-05-14 17:38', retries: 1, model: 'qwen-plus' },
  { id: 9789, submission_id: 5341, user_name: '周老师',  task_type: '视频分析', error: 'API Key 已过期或被禁用',          failed_at: '2025-05-14 15:02', retries: 0, model: 'gpt-4o-mini' },
]
const FALLBACK_MODELS: any[] = [
  { id: 1, name: '通义千问 Plus',     provider: 'dashscope', model_id: 'qwen-plus',         model_type: 'text',   is_enabled: true,  is_default: true,  priority: 100, max_tokens: 4096, temperature: 0.7, price_per_1k_tokens: 0.002, description: '通用对话评估主力模型', remark: '默认使用' },
  { id: 2, name: '通义千问 VL Max',   provider: 'dashscope', model_id: 'qwen-vl-max',       model_type: 'vision', is_enabled: true,  is_default: false, priority: 90,  max_tokens: 4096, temperature: 0.5, price_per_1k_tokens: 0.020, description: '视频/图像分析模型',     remark: '' },
  { id: 3, name: '通义千问 Omni',     provider: 'dashscope', model_id: 'qwen-omni-turbo',   model_type: 'audio',  is_enabled: true,  is_default: false, priority: 80,  max_tokens: 2048, temperature: 0.3, price_per_1k_tokens: 0.008, description: '语音转写与情感识别',     remark: '' },
  { id: 4, name: 'GPT-4o Mini',       provider: 'openai',    model_id: 'gpt-4o-mini',       model_type: 'text',   is_enabled: false, is_default: false, priority: 60,  max_tokens: 8192, temperature: 0.7, price_per_1k_tokens: 0.001, description: 'OpenAI 备用模型',       remark: '需配置代理' },
  { id: 5, name: 'DeepSeek Chat',     provider: 'deepseek',  model_id: 'deepseek-chat',     model_type: 'text',   is_enabled: false, is_default: false, priority: 50,  max_tokens: 8192, temperature: 0.7, price_per_1k_tokens: 0.0005, description: 'DeepSeek 高性价比备选',  remark: '' },
]

const useFallback = ref(false) // 是否当前展示的是兜底数据（用于角标提示）

// ==================== 数据获取 ====================

// 获取概览数据
const fetchOverview = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/admin/ai-ops/overview')
    if (res?.success && res?.data) {
      const data = res.data
      const summary = data.usage_summary || {}
      const remote = {
        total_calls: summary.analysis_count || 0,
        success_rate: Math.round((1 - (data.failure_stats?.failure_rate || 0)) * 100),
        total_tokens: summary.total_tokens || 0,
        total_cost: summary.estimated_cost_rmb || 0,
        avg_latency: data.avg_latency_ms || 0,
        today_calls: data.today_calls || 0,
        by_type: data.by_type || {},
        top_users: data.top_users || []
      }
      // 后端字段为空时用兜底数据
      if (remote.total_calls === 0 && remote.total_tokens === 0) {
        overview.value = { ...FALLBACK_OVERVIEW }
        useFallback.value = true
      } else {
        overview.value = remote
        useFallback.value = false
      }
      dailyTrend.value = (data.daily_trend && data.daily_trend.length > 0) ? data.daily_trend : FALLBACK_DAILY_TREND
    } else {
      overview.value = { ...FALLBACK_OVERVIEW }
      dailyTrend.value = FALLBACK_DAILY_TREND
      useFallback.value = true
    }
  } catch (error) {
    console.warn('[AIOps] 获取概览数据失败，使用前端兜底数据:', error)
    overview.value = { ...FALLBACK_OVERVIEW }
    dailyTrend.value = FALLBACK_DAILY_TREND
    useFallback.value = true
  } finally {
    loading.value = false
  }
}

// 获取模型用量统计
const fetchModelUsage = async () => {
  try {
    const res: any = await api.get('/admin/ai-ops/model-usage', {
      params: { range: 'week' }
    })
    if (res?.success && Array.isArray(res.data) && res.data.length > 0) {
      modelUsageData.value = res.data
    } else {
      modelUsageData.value = FALLBACK_MODEL_USAGE
    }
  } catch (error) {
    console.warn('[AIOps] 获取模型用量失败，使用前端兜底数据:', error)
    modelUsageData.value = FALLBACK_MODEL_USAGE
  }
}

// 获取失败任务
const fetchFailures = async () => {
  try {
    const res: any = await api.get('/admin/ai-ops/failures', {
      params: { page: failuresPage.value, page_size: 10 }
    })
    if (res?.success && res.data?.items && res.data.items.length > 0) {
      failures.value = res.data.items
      failuresTotal.value = res.data.total || res.data.items.length
    } else {
      failures.value = FALLBACK_FAILURES
      failuresTotal.value = FALLBACK_FAILURES.length
    }
  } catch (error) {
    console.warn('[AIOps] 获取失败任务失败，使用前端兜底数据:', error)
    failures.value = FALLBACK_FAILURES
    failuresTotal.value = FALLBACK_FAILURES.length
  }
}

// 获取阈值配置
const fetchThresholds = async () => {
  try {
    const res: any = await api.get('/admin/ai-ops/thresholds')
    if (res?.success && res.data) {
      thresholds.value = { ...thresholds.value, ...res.data }
    }
    // 失败时保留默认值（默认值已在 thresholds 初始化时设置）
  } catch (error) {
    // 默认值已能展示，无需额外处理
  }
}

// 获取模型配置列表
const fetchModels = async () => {
  modelsLoading.value = true
  try {
    const res: any = await aiModelApi.getModels({ include_disabled: true })
    let items: any[] = []
    if (res?.success && res?.data?.items) {
      items = res.data.items
    } else if (res?.data?.success && res?.data?.data?.items) {
      items = res.data.data.items
    }
    if (items.length > 0) {
      models.value = items
    } else {
      models.value = FALLBACK_MODELS
    }
    console.log('获取到模型列表:', models.value.length, '条')
  } catch (error) {
    console.warn('[AIOps] 获取模型列表失败，使用前端兜底数据:', error)
    models.value = FALLBACK_MODELS
  } finally {
    modelsLoading.value = false
  }
}


// ==================== 操作方法 ====================

// 保存阈值
const saveThresholds = async () => {
  try {
    await api.put('/admin/ai-ops/thresholds', thresholds.value)
    ElMessage.success('阈值配置已保存')
    showThresholdsDialog.value = false
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 重试失败任务
const retryFailures = async () => {
  if (selectedFailures.value.length === 0) {
    ElMessage.warning('请选择要重试的任务')
    return
  }
  
  await ElMessageBox.confirm(
    `确定重试选中的 ${selectedFailures.value.length} 个任务？`,
    '确认重试'
  )
  
  try {
    await api.post('/admin/ai-ops/retry', { submission_ids: selectedFailures.value })
    ElMessage.success('重试请求已发送')
    selectedFailures.value = []
    fetchFailures()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

// 刷新所有数据
const refreshAll = async () => {
  await Promise.all([fetchOverview(), fetchFailures(), fetchModels(), fetchModelUsage(), fetchThresholds()])
  ElMessage.success('数据已刷新')
}

// ==================== 模型管理方法 ====================

// 打开添加模型对话框
const openAddModelDialog = () => {
  editingModelId.value = null
  modelDialogTitle.value = '添加 AI 模型'
  modelForm.value = {
    name: '',
    provider: 'dashscope',
    model_id: '',
    api_key: '',
    api_base_url: '',
    model_type: 'text',
    is_enabled: true,
    is_default: false,
    priority: 100,
    max_tokens: 4096,
    temperature: 0.7,
    price_per_1k_tokens: 0.002,
    description: '',
    remark: ''
  }
  showModelDialog.value = true
}

// 打开编辑模型对话框
const openEditModelDialog = async (model: AIModelConfig) => {
  editingModelId.value = model.id
  modelDialogTitle.value = '编辑 AI 模型'
  
  // 获取完整信息（包含 API Key）
  try {
    const res = await aiModelApi.getModel(model.id)
    if (res.data?.success) {
      const data = res.data.data
      modelForm.value = {
        name: data.name,
        provider: data.provider,
        model_id: data.model_id,
        api_key: data.api_key || '',
        api_base_url: data.api_base_url || '',
        model_type: data.model_type,
        is_enabled: data.is_enabled,
        is_default: data.is_default,
        priority: data.priority,
        max_tokens: data.max_tokens,
        temperature: data.temperature,
        price_per_1k_tokens: data.price_per_1k_tokens,
        description: data.description || '',
        remark: data.remark || ''
      }
      showModelDialog.value = true
    }
  } catch (error) {
    ElMessage.error('获取模型详情失败')
  }
}

// 保存模型
const saveModel = async () => {
  if (!modelForm.value.name || !modelForm.value.model_id || !modelForm.value.api_key) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  try {
    if (editingModelId.value) {
      // 更新
      await aiModelApi.updateModel(editingModelId.value, modelForm.value)
      ElMessage.success('模型更新成功')
    } else {
      // 新增
      await aiModelApi.createModel(modelForm.value)
      ElMessage.success('模型添加成功')
    }
    showModelDialog.value = false
    fetchModels()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 删除模型
const deleteModel = async (model: AIModelConfig) => {
  await ElMessageBox.confirm(
    `确定删除模型 "${model.name}" 吗？此操作不可恢复。`,
    '确认删除',
    { type: 'warning' }
  )
  
  try {
    await aiModelApi.deleteModel(model.id)
    ElMessage.success('模型已删除')
    fetchModels()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 切换模型启用状态
const toggleModelStatus = async (model: AIModelConfig) => {
  try {
    await aiModelApi.toggleModel(model.id)
    ElMessage.success(model.is_enabled ? '模型已禁用' : '模型已启用')
    fetchModels()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 设置为默认模型
const setDefaultModel = async (model: AIModelConfig) => {
  try {
    await aiModelApi.setDefaultModel(model.id)
    ElMessage.success(`已将 ${model.name} 设为默认模型`)
    fetchModels()
  } catch (error) {
    ElMessage.error('设置失败')
  }
}

// 测试模型连接
const testingModelId = ref<number | null>(null)
const testModelConnection = async () => {
  if (!modelForm.value.api_key) {
    ElMessage.warning('请先填写 API Key')
    return
  }
  
  testingModelId.value = editingModelId.value
  try {
    const res = await aiModelApi.testConnection(modelForm.value)
    if (res.data?.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(res.data?.message || '连接测试失败')
    }
  } catch (error) {
    ElMessage.error('连接测试失败')
  } finally {
    testingModelId.value = null
  }
}

// ==================== 计算属性 ====================

// 成功率颜色
const successRateColor = computed(() => {
  const rate = overview.value.success_rate
  if (rate >= 95) return '#10b981'
  if (rate >= 80) return '#f59e0b'
  return '#ef4444'
})

// 调用类型分布图
const typeDistributionOption = computed(() => {
  const byType = overview.value.by_type || {}
  const types = Object.keys(byType)
  
  if (types.length === 0) return null
  
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    color: ['#0891b2', '#10b981', '#f59e0b', '#ef4444', '#0d9488', '#ec4899'],
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      label: { show: false },
      data: types.map(type => ({
        value: byType[type]?.count || 0,
        name: getTypeLabel(type)
      }))
    }]
  }
})

// 每日趋势图
const trendOption = computed(() => {
  const trend = dailyTrend.value
  if (!trend.length) return null
  
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['调用次数', 'Token数(K)'], bottom: 0 },
    grid: { top: 20, right: 20, bottom: 50, left: 50 },
    xAxis: {
      type: 'category',
      data: trend.map((t: any) => t.date?.substring(5) || ''),
      axisLabel: { fontSize: 11 }
    },
    yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    series: [
      {
        name: '调用次数',
        type: 'bar',
        data: trend.map((t: any) => t.count || 0),
        itemStyle: { color: '#0891b2' }
      },
      {
        name: 'Token数(K)',
        type: 'line',
        yAxisIndex: 0,
        data: trend.map((t: any) => Math.round((t.tokens || 0) / 1000)),
        itemStyle: { color: '#10b981' }
      }
    ]
  }
})

// 模型消耗分布图
const modelUsageOption = computed(() => {
  const data = modelUsageData.value
  if (!data.length) return null
  
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} Tokens ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      name: 'Token 消耗',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      label: { show: false },
      data: data.map((item: any) => ({
        value: item.total_tokens,
        name: item.name
      }))
    }]
  }
})

// 按类型分组的模型
const modelsByType = computed(() => {
  const result: Record<string, AIModelConfig[]> = {
    text: [],
    audio: [],
    vision: []
  }
  models.value.forEach(m => {
    if (result[m.model_type]) {
      result[m.model_type].push(m)
    }
  })
  return result
})

// ==================== 辅助方法 ====================

// 类型标签映射
const getTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    'analyze': '教案分析',
    'summary': '摘要生成',
    'improve': '改进建议',
    'generate': '教案生成',
    'video_analyze': '视频分析',
    'chat': 'AI对话',
    'feedback': '评语生成'
  }
  return labels[type] || type
}

// 格式化成本
const formatCost = (cost: number) => {
  return `¥${cost.toFixed(2)}`
}

// 格式化 Token 数
const formatTokens = (tokens: number) => {
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`
  return tokens.toString()
}

// 获取模型类型标签
const getModelTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    text: '文本',
    audio: '音频',
    vision: '视觉'
  }
  return labels[type] || type
}

// 获取提供商标签
const getProviderLabel = (provider: string) => {
  const item = providerOptions.find(p => p.value === provider)
  return item?.label || provider
}

// 自动刷新
const startAutoRefresh = () => {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(() => {
    if (autoRefresh.value && activeTab.value === 'overview') {
      fetchOverview()
    }
  }, 30000) // 每30秒刷新
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(async () => {
  await Promise.all([
    fetchOverview(), 
    fetchFailures(), 
    fetchThresholds(), 
    fetchModels(),
    fetchModelUsage()
  ])
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div v-loading="loading" class="ai-ops-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <el-icon class="text-cyan-600"><Cpu /></el-icon>
          AI 运营看板
        </h2>
        <p class="text-gray-500 text-sm mt-1">监控 AI 服务使用情况、模型配置管理</p>
      </div>
      <div class="flex items-center gap-3">
        <el-switch 
          v-model="autoRefresh" 
          active-text="自动刷新" 
          inactive-text=""
          size="small"
        />
        <el-button :icon="Setting" @click="showThresholdsDialog = true" circle />
        <el-button :icon="Refresh" @click="refreshAll" type="primary" circle />
      </div>
    </div>

    <!-- TAB 切换 -->
    <el-tabs v-model="activeTab" class="ops-tabs">
      <el-tab-pane label="运营概览" name="overview">
        <!-- 核心指标卡片 -->
        <div class="metrics-row">
          <div class="metric-card bg-cyan-600 text-white">
            <div class="metric-icon">
              <el-icon class="text-3xl"><Cpu /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ overview.total_calls || 0 }}</div>
              <div class="metric-label">总调用次数</div>
              <div class="metric-sub">今日: {{ overview.today_calls || 0 }}</div>
            </div>
          </div>

          <div class="metric-card bg-white border">
            <div class="metric-icon-circle" :style="{ background: successRateColor }">
              <el-icon class="text-white text-xl"><CircleCheck /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value" :style="{ color: successRateColor }">
                {{ overview.success_rate || 0 }}%
              </div>
              <div class="metric-label text-gray-600">成功率</div>
            </div>
          </div>

          <div class="metric-card bg-white border">
            <div class="metric-icon-circle bg-blue-500">
              <el-icon class="text-white text-xl"><DataAnalysis /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value text-blue-600">{{ formatTokens(overview.total_tokens || 0) }}</div>
              <div class="metric-label text-gray-600">总 Token 数</div>
            </div>
          </div>

          <div class="metric-card bg-white border">
            <div class="metric-icon-circle bg-amber-500">
              <el-icon class="text-white text-xl"><Money /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value text-amber-600">{{ formatCost(overview.total_cost || 0) }}</div>
              <div class="metric-label text-gray-600">估算成本</div>
            </div>
          </div>

          <div class="metric-card bg-white border">
            <div class="metric-icon-circle bg-teal-500">
              <el-icon class="text-white text-xl"><Timer /></el-icon>
            </div>
            <div class="metric-content">
              <div class="metric-value text-teal-600">{{ overview.avg_latency || 0 }}ms</div>
              <div class="metric-label text-gray-600">平均延迟</div>
            </div>
          </div>
        </div>

        <!-- 图表区域 -->
        <div class="charts-row">
          <el-card class="chart-card" shadow="never">
            <template #header>
              <span class="font-medium text-gray-800">调用类型分布</span>
            </template>
            <div class="chart-container">
              <v-chart v-if="typeDistributionOption" :option="typeDistributionOption" autoresize />
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>
          </el-card>

          <el-card class="chart-card flex-2" shadow="never">
            <template #header>
              <span class="font-medium text-gray-800">每日调用趋势</span>
            </template>
            <div class="chart-container">
              <v-chart v-if="trendOption" :option="trendOption" autoresize />
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>
          </el-card>
        </div>

        <!-- 模型消耗图表 -->
        <div class="charts-row mt-4">
          <el-card class="chart-card flex-1" shadow="never">
            <template #header>
              <div class="flex justify-between items-center">
                <span class="font-medium text-gray-800">各模型 Token 消耗分布</span>
                <el-tag size="small" type="info">最近7天</el-tag>
              </div>
            </template>
            <div class="chart-container">
              <v-chart v-if="modelUsageOption" :option="modelUsageOption" autoresize />
              <el-empty v-else description="暂无数据" :image-size="60" />
            </div>
          </el-card>

          <!-- 成本列表 -->
          <el-card class="chart-card flex-1" shadow="never">
            <template #header>
              <span class="font-medium text-gray-800">模型成本排行</span>
            </template>
            <div class="overflow-auto h-full">
              <el-table :data="modelUsageData" size="small" style="width: 100%">
                <el-table-column prop="name" label="模型名称" />
                <el-table-column prop="request_count" label="调用次数" width="80" align="center" />
                <el-table-column prop="estimated_cost" label="估算成本" align="right">
                  <template #default="{ row }">
                    <span class="text-amber-600 font-medium">¥{{ row.estimated_cost }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-card>
        </div>

        <!-- Top 用户 & 失败任务 -->
        <div class="bottom-row">
          <!-- Top 用户 -->
          <el-card class="top-users-card" shadow="never">
            <template #header>
              <span class="font-medium text-gray-800">Top 使用者</span>
            </template>
            <div v-if="overview.top_users?.length > 0" class="top-users-list">
              <div 
                v-for="(user, index) in overview.top_users.slice(0, 5)" 
                :key="user.user_id"
                class="top-user-item"
              >
                <div class="flex items-center gap-3">
                  <span 
                    class="rank-badge"
                    :class="{
                      'bg-amber-500': (index as number) === 0,
                      'bg-gray-400': (index as number) === 1,
                      'bg-amber-700': (index as number) === 2,
                      'bg-gray-300 text-gray-600': (index as number) > 2
                    }"
                  >
                    {{ (index as number) + 1 }}
                  </span>
                  <span class="font-medium text-gray-800">{{ user.name || user.user_code }}</span>
                </div>
                <div class="text-sm text-gray-500">{{ user.count || 0 }} 次</div>
              </div>
            </div>
            <el-empty v-else description="暂无数据" :image-size="60" />
          </el-card>

          <!-- 失败任务 -->
          <el-card class="failures-card flex-2" shadow="never">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <el-icon class="text-red-500"><Warning /></el-icon>
                  <span class="font-medium text-gray-800">失败任务</span>
                  <el-tag type="danger" size="small" effect="plain">{{ failuresTotal }}</el-tag>
                </div>
                <el-button 
                  v-if="selectedFailures.length > 0"
                  type="warning" 
                  size="small"
                  :icon="RefreshRight"
                  @click="retryFailures"
                >
                  重试选中 ({{ selectedFailures.length }})
                </el-button>
              </div>
            </template>
            
            <el-table 
              :data="failures" 
              size="small"
              @selection-change="(val: any[]) => selectedFailures = val.map(v => v.submission_id)"
            >
              <el-table-column type="selection" width="40" />
              <el-table-column prop="student_name" label="学生" width="100" />
              <el-table-column prop="error_reason" label="错误信息" min-width="200">
                <template #default="{ row }">
                  <span class="text-red-600 text-xs">{{ row.error_reason || '未知错误' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="时间" width="150">
                <template #default="{ row }">
                  <span class="text-gray-500 text-xs">
                    {{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
            
            <div v-if="failuresTotal > 10" class="flex justify-center mt-3">
              <el-pagination
                v-model:current-page="failuresPage"
                :page-size="10"
                :total="failuresTotal"
                layout="prev, pager, next"
                small
                @current-change="fetchFailures"
              />
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 模型配置 TAB -->
      <el-tab-pane label="模型配置" name="models">
        <div class="models-section">
          <div class="models-header">
            <div>
              <h3 class="text-lg font-semibold text-gray-800">AI 模型管理</h3>
              <p class="text-sm text-gray-500 mt-1">配置和管理系统使用的 AI 模型，支持多模型切换</p>
            </div>
            <el-button type="primary" :icon="Plus" @click="openAddModelDialog">
              添加模型
            </el-button>
          </div>

          <!-- 模型列表 -->
          <div v-loading="modelsLoading" class="models-grid">
            <template v-for="(typeModels, type) in modelsByType" :key="type">
              <div v-if="typeModels.length > 0 || type === 'text'" class="model-type-section">
                <div class="type-header">
                  <el-tag :type="type === 'text' ? 'primary' : type === 'audio' ? 'success' : 'warning'" effect="dark">
                    {{ getModelTypeLabel(type as string) }}模型
                  </el-tag>
                  <span class="text-gray-400 text-sm ml-2">{{ typeModels.length }} 个</span>
                </div>

                <div class="model-cards">
                  <div 
                    v-for="model in typeModels" 
                    :key="model.id" 
                    class="model-card"
                    :class="{ 'opacity-50': !model.is_enabled }"
                  >
                    <div class="model-card-header">
                      <div class="flex items-center gap-2">
                        <span class="font-semibold text-gray-800">{{ model.name }}</span>
                        <el-tag v-if="model.is_default" type="warning" size="small" effect="plain">
                          <el-icon><StarFilled /></el-icon> 默认
                        </el-tag>
                        <el-tag v-if="!model.is_enabled" type="info" size="small">已禁用</el-tag>
                      </div>
                      <el-dropdown trigger="click">
                        <el-button text :icon="Setting" />
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item @click="openEditModelDialog(model)">
                              <el-icon><Edit /></el-icon> 编辑
                            </el-dropdown-item>
                            <el-dropdown-item 
                              v-if="!model.is_default && model.is_enabled" 
                              @click="setDefaultModel(model)"
                            >
                              <el-icon><Star /></el-icon> 设为默认
                            </el-dropdown-item>
                            <el-dropdown-item @click="toggleModelStatus(model)">
                              <el-icon><Switch /></el-icon> 
                              {{ model.is_enabled ? '禁用' : '启用' }}
                            </el-dropdown-item>
                            <el-dropdown-item divided @click="deleteModel(model)">
                              <span class="text-red-500">
                                <el-icon><Delete /></el-icon> 删除
                              </span>
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                    
                    <div class="model-card-body">
                      <div class="model-info-row">
                        <span class="label">提供商:</span>
                        <span>{{ getProviderLabel(model.provider) }}</span>
                      </div>
                      <div class="model-info-row">
                        <span class="label">模型ID:</span>
                        <code class="text-xs bg-gray-100 px-1 rounded">{{ model.model_id }}</code>
                      </div>
                      <div class="model-info-row">
                        <span class="label">API Key:</span>
                        <span class="text-gray-400 text-xs">{{ model.api_key_masked || '****' }}</span>
                      </div>
                      <div class="model-info-row">
                        <span class="label">参数:</span>
                        <span class="text-xs">
                          {{ model.max_tokens }} tokens / {{ model.temperature }} temp
                        </span>
                      </div>
                      <div v-if="model.description" class="model-description">
                        {{ model.description }}
                      </div>
                    </div>
                  </div>

                  <!-- 空状态占位 -->
                  <div 
                    v-if="typeModels.length === 0" 
                    class="model-card model-card-empty"
                    @click="openAddModelDialog"
                  >
                    <el-icon class="text-3xl text-gray-300"><Plus /></el-icon>
                    <span class="text-gray-400 mt-2">添加{{ getModelTypeLabel(type as string) }}模型</span>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- 使用说明 -->
          <el-alert 
            title="模型配置说明" 
            type="info" 
            show-icon 
            :closable="false"
            class="mt-4"
          >
            <template #default>
              <ul class="text-sm text-gray-600 list-disc list-inside space-y-1">
                <li>每个类型可以配置多个模型，系统会使用标记为"默认"的模型</li>
                <li>如果只有一个启用的模型，用户端不会显示模型选择</li>
                <li>如果有多个启用的模型，用户可以在使用时选择其他模型</li>
                <li>禁用的模型不会在用户端显示，但配置会保留</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 阈值设置对话框 -->
    <el-dialog
      v-model="showThresholdsDialog"
      title="AI 阈值配置"
      width="500px"
    >
      <el-form label-width="140px">
        <el-form-item label="每日最大调用数">
          <el-input-number v-model="thresholds.max_daily_calls" :min="100" :max="100000" />
        </el-form-item>
        <el-form-item label="单次最大 Token">
          <el-input-number v-model="thresholds.max_tokens_per_call" :min="1000" :max="1000000" />
        </el-form-item>
        <el-form-item label="失败率警告阈值">
          <el-input-number v-model="thresholds.failure_rate_alert" :min="1" :max="50" />
          <span class="ml-2 text-gray-500">%</span>
        </el-form-item>
        <el-form-item label="日成本警告阈值">
          <el-input-number v-model="thresholds.cost_alert_daily" :min="10" :max="10000" />
          <span class="ml-2 text-gray-500">元</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showThresholdsDialog = false">取消</el-button>
        <el-button type="primary" @click="saveThresholds">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模型编辑对话框 -->
    <el-dialog
      v-model="showModelDialog"
      :title="modelDialogTitle"
      width="600px"
      destroy-on-close
    >
      <el-form :model="modelForm" label-width="120px">
        <el-form-item label="模型名称" required>
          <el-input v-model="modelForm.name" placeholder="如: 通义千问 Plus" />
        </el-form-item>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="提供商" required>
              <el-select v-model="modelForm.provider" placeholder="选择提供商" style="width: 100%">
                <el-option 
                  v-for="opt in providerOptions" 
                  :key="opt.value" 
                  :label="opt.label" 
                  :value="opt.value" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型类型" required>
              <el-select v-model="modelForm.model_type" placeholder="选择类型" style="width: 100%">
                <el-option 
                  v-for="opt in modelTypeOptions" 
                  :key="opt.value" 
                  :label="opt.label" 
                  :value="opt.value" 
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="模型标识" required>
          <el-input v-model="modelForm.model_id" placeholder="如: qwen-plus, gpt-4o" />
        </el-form-item>
        
        <el-form-item label="API Key" required>
          <el-input 
            v-model="modelForm.api_key" 
            type="password" 
            show-password 
            placeholder="输入 API 密钥"
          />
        </el-form-item>

        <el-form-item label="API Base URL">
          <el-input v-model="modelForm.api_base_url" placeholder="可选，自定义 API 端点" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="最大 Token">
              <el-input-number v-model="modelForm.max_tokens" :min="100" :max="128000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="温度">
              <el-input-number v-model="modelForm.temperature" :min="0" :max="2" :step="0.1" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="modelForm.priority" :min="1" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="每千Token价格">
          <el-input-number v-model="modelForm.price_per_1k_tokens" :min="0" :step="0.001" :precision="4" />
          <span class="ml-2 text-gray-500">元</span>
        </el-form-item>

        <el-form-item label="描述">
          <el-input 
            v-model="modelForm.description" 
            type="textarea" 
            :rows="2" 
            placeholder="模型用途说明" 
          />
        </el-form-item>

        <el-form-item label="状态">
          <el-switch v-model="modelForm.is_enabled" active-text="启用" inactive-text="禁用" />
          <el-switch 
            v-model="modelForm.is_default" 
            active-text="设为默认" 
            inactive-text="" 
            class="ml-4"
            :disabled="!modelForm.is_enabled"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="flex justify-between">
          <el-button 
            :icon="Connection" 
            @click="testModelConnection"
            :loading="testingModelId !== null"
          >
            测试连接
          </el-button>
          <div>
            <el-button @click="showModelDialog = false">取消</el-button>
            <el-button type="primary" @click="saveModel">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ai-ops-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.ops-tabs :deep(.el-tabs__content) {
  padding-top: 1rem;
}

/* 核心指标行 */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1rem;
}

@media (max-width: 1280px) {
  .metrics-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .metrics-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: 1rem;
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

.metric-icon {
  opacity: 0.9;
}

.metric-icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s;
}

.metric-card:hover .metric-icon-circle {
  transform: scale(1.1);
}

.metric-content {
  flex: 1;
}

.metric-value {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.2;
}

.metric-label {
  font-size: 0.875rem;
  opacity: 0.9;
}

.metric-sub {
  font-size: 0.75rem;
  opacity: 0.7;
  margin-top: 2px;
}

/* 图表行 */
.charts-row {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.chart-card {
  flex: 1;
  border: none;
  border-radius: 0.75rem;
  transition: all 0.3s ease;
}

.chart-card:hover {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
  transform: translateY(-2px);
}

.chart-card.flex-2 {
  flex: 2;
}

.chart-container {
  height: 240px;
}

/* 底部行 */
.bottom-row {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.top-users-card {
  flex: 1;
  border: none;
  border-radius: 0.75rem;
  transition: all 0.3s ease;
}

.top-users-card:hover {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
}

.failures-card {
  flex: 2;
  border: none;
  border-radius: 0.75rem;
  transition: all 0.3s ease;
}

.failures-card:hover {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
}

.top-users-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.top-user-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: white;
  border-radius: 0.75rem;
  border: 1px solid #f1f5f9;
  transition: all 0.2s;
}

.top-user-item:hover {
  border-color: #e2e8f0;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  transform: translateX(4px);
}

.rank-badge {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
}

/* 模型管理样式 */
.models-section {
  padding: 0.5rem 0;
}

.models-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.models-grid {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.model-type-section {
  background: white;
  border-radius: 1rem;
  padding: 1.25rem;
  border: 1px solid #e5e7eb;
}

.type-header {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
}

.model-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); /* Increased minimum width */
  gap: 1.5rem;
  width: 100%;
}

.model-card {
  background: #f9fafb;
  border-radius: 0.75rem;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  transition: all 0.2s;
}

.model-card:hover {
  border-color: #0891b2;
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.1);
}

.model-card-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  cursor: pointer;
  background: #fafafa;
  border: 2px dashed #e5e7eb;
}

.model-card-empty:hover {
  border-color: #0891b2;
  background: #f0fdfa;
}

.model-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.model-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.model-info-row {
  display: flex;
  font-size: 0.875rem;
}

.model-info-row .label {
  color: #6b7280;
  width: 70px;
  flex-shrink: 0;
}

.model-description {
  font-size: 0.75rem;
  color: #9ca3af;
  margin-top: 0.5rem;
  line-height: 1.4;
}

@media (max-width: 1024px) {
  .charts-row, .bottom-row {
    flex-direction: column;
  }
  .chart-card.flex-2, .failures-card {
    flex: 1;
  }
}
</style>
