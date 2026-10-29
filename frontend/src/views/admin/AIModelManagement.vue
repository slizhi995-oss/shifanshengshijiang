<script setup lang="ts">
/**
 * 管理员 · AI 模型管理
 * Tab 1：模型配置（CRUD / API Key / 切换默认）
 * Tab 2：调用日志（分页 / 多维筛选）
 * Tab 3：额度统计（月度消耗 / 剩余量）
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cpu, Plus, Edit, Delete, Switch, Star, StarFilled,
  Setting, Connection, Refresh, Search, Key, DataAnalysis, PieChart
} from '@element-plus/icons-vue'
import { aiModelApi, type AIModelConfig, type AIModelConfigCreate, type AIModelUsageLogItem } from '@/api/aiModels'

// ─── Tab ───────────────────────────────────────────────
const activeTab = ref('models')

// ══════════════════════════════════════════════════════
// Tab 1 · 模型配置
// ══════════════════════════════════════════════════════
const models = ref<AIModelConfig[]>([])
const modelsLoading = ref(false)
const showDialog = ref(false)
const dialogTitle = ref('添加 AI 模型')
const editingId = ref<number | null>(null)
const testingId = ref<number | null>(null)

const emptyForm = (): AIModelConfigCreate => ({
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
  monthly_quota: undefined,
  description: '',
  remark: '',
})
const form = ref<AIModelConfigCreate>(emptyForm())

const providerOptions = [
  { value: 'dashscope', label: '阿里云通义千问 (DashScope)' },
  { value: 'openai',    label: 'OpenAI' },
  { value: 'azure',     label: 'Azure OpenAI' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'gemini',    label: 'Google Gemini' },
  { value: 'deepseek',  label: 'DeepSeek' },
  { value: 'zhipu',     label: '智谱 AI' },
  { value: 'moonshot',  label: '月之暗面 Kimi' },
  { value: 'other',     label: '其他' },
]

const modelTypeOptions = [
  { value: 'text',   label: '文本模型' },
  { value: 'audio',  label: '音频模型' },
  { value: 'vision', label: '视觉模型' },
]

const providerLabel = (p: string) => providerOptions.find(o => o.value === p)?.label ?? p
const typeLabel = (t: string) => modelTypeOptions.find(o => o.value === t)?.label ?? t

const modelsByType = computed(() => {
  const r: Record<string, AIModelConfig[]> = { text: [], audio: [], vision: [] }
  models.value.forEach(m => { if (r[m.model_type]) r[m.model_type].push(m) })
  return r
})

const fetchModels = async () => {
  modelsLoading.value = true
  try {
    const res: any = await aiModelApi.getModels({ include_disabled: true })
    models.value = res?.data?.data?.items ?? res?.data?.items ?? []
  } catch {
    ElMessage.error('获取模型列表失败')
  } finally {
    modelsLoading.value = false
  }
}

const openAdd = () => {
  editingId.value = null
  dialogTitle.value = '添加 AI 模型'
  form.value = emptyForm()
  showDialog.value = true
}

const openEdit = async (model: AIModelConfig) => {
  editingId.value = model.id
  dialogTitle.value = '编辑 AI 模型'
  try {
    const res: any = await aiModelApi.getModel(model.id)
    const data = res?.data?.data ?? res?.data ?? model
    form.value = {
      name: data.name,
      provider: data.provider,
      model_id: data.model_id,
      api_key: data.api_key ?? '',
      api_base_url: data.api_base_url ?? '',
      model_type: data.model_type,
      is_enabled: data.is_enabled,
      is_default: data.is_default,
      priority: data.priority,
      max_tokens: data.max_tokens,
      temperature: data.temperature,
      price_per_1k_tokens: data.price_per_1k_tokens,
      monthly_quota: data.monthly_quota ?? undefined,
      description: data.description ?? '',
      remark: data.remark ?? '',
    }
    showDialog.value = true
  } catch {
    ElMessage.error('获取模型详情失败')
  }
}

const saveModel = async () => {
  if (!form.value.name || !form.value.model_id || !form.value.api_key) {
    ElMessage.warning('请填写模型名称、模型 ID 和 API Key')
    return
  }
  try {
    if (editingId.value) {
      await aiModelApi.updateModel(editingId.value, form.value)
      ElMessage.success('模型更新成功')
    } else {
      await aiModelApi.createModel(form.value)
      ElMessage.success('模型添加成功')
    }
    showDialog.value = false
    fetchModels()
  } catch {
    ElMessage.error('保存失败，请检查填写内容')
  }
}

const deleteModel = async (model: AIModelConfig) => {
  await ElMessageBox.confirm(`确定删除模型 "${model.name}"？此操作不可恢复。`, '确认删除', { type: 'warning' })
  try {
    await aiModelApi.deleteModel(model.id)
    ElMessage.success('模型已删除')
    fetchModels()
  } catch {
    ElMessage.error('删除失败')
  }
}

const toggleStatus = async (model: AIModelConfig) => {
  try {
    await aiModelApi.toggleModel(model.id)
    ElMessage.success(model.is_enabled ? '模型已禁用' : '模型已启用')
    fetchModels()
  } catch {
    ElMessage.error('操作失败')
  }
}

const setDefault = async (model: AIModelConfig) => {
  try {
    await aiModelApi.setDefaultModel(model.id)
    ElMessage.success(`已将 "${model.name}" 设为默认模型`)
    fetchModels()
  } catch {
    ElMessage.error('设置失败')
  }
}

const testConnection = async () => {
  if (!form.value.api_key) { ElMessage.warning('请先填写 API Key'); return }
  testingId.value = -1
  try {
    const res: any = await aiModelApi.testConnection(form.value)
    if (res?.data?.success || res?.success) {
      ElMessage.success(res.message || '连接测试成功')
    } else {
      ElMessage.error(`连接失败：${res?.data?.message || res?.message || '未知错误'}`)
    }
  } catch {
    ElMessage.error('连接测试失败')
  } finally {
    testingId.value = null
  }
}

// ══════════════════════════════════════════════════════
// Tab 2 · 调用日志
// ══════════════════════════════════════════════════════
const logs = ref<AIModelUsageLogItem[]>([])
const logsLoading = ref(false)
const logsTotal = ref(0)
const logsPage = ref(1)
const logsPageSize = ref(20)

const logFilter = ref({
  model_id: undefined as number | undefined,
  usage_type: '',
  is_success: undefined as boolean | undefined,
  range: 'week',
})

const usageTypeOptions = [
  { value: '', label: '全部类型' },
  { value: 'analyze', label: '教案分析' },
  { value: 'video_analyze', label: '视频分析' },
  { value: 'chat', label: 'AI 对话' },
  { value: 'feedback', label: '评语生成' },
  { value: 'summary', label: '摘要生成' },
  { value: 'improve', label: '改进建议' },
  { value: 'generate', label: '教案生成' },
]

const rangeOptions = [
  { value: 'day', label: '最近 24h' },
  { value: 'week', label: '最近 7 天' },
  { value: 'month', label: '最近 30 天' },
  { value: 'all', label: '全部' },
]

const fetchLogs = async (page = 1) => {
  logsLoading.value = true
  logsPage.value = page
  try {
    const params: any = {
      page,
      page_size: logsPageSize.value,
      range: logFilter.value.range,
    }
    if (logFilter.value.model_id) params.model_id = logFilter.value.model_id
    if (logFilter.value.usage_type) params.usage_type = logFilter.value.usage_type
    if (logFilter.value.is_success !== undefined) params.is_success = logFilter.value.is_success
    const res: any = await aiModelApi.getUsageLogs(params)
    const d = res?.data?.data ?? res?.data ?? {}
    logs.value = d.items ?? []
    logsTotal.value = d.total ?? 0
  } catch {
    ElMessage.error('获取调用日志失败')
  } finally {
    logsLoading.value = false
  }
}

const formatLatency = (ms: number) => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
const formatTokens = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n)

const usageTypeMap: Record<string, string> = {
  analyze: '教案分析', video_analyze: '视频分析', chat: 'AI对话',
  feedback: '评语生成', summary: '摘要', improve: '改进建议', generate: '教案生成',
}

// ══════════════════════════════════════════════════════
// Tab 3 · 额度统计
// ══════════════════════════════════════════════════════
const quotaStats = ref<any[]>([])
const quotaLoading = ref(false)
const quotaRange = ref('month')

// 余额查询
const balanceMap = ref<Record<number, any>>({})
const balanceLoading = ref<Record<number, boolean>>({})

const checkBalance = async (row: any) => {
  balanceLoading.value[row.id] = true
  try {
    const res: any = await aiModelApi.checkBalance(row.id)
    if (res?.success) {
      balanceMap.value[row.id] = res.data
    } else {
      balanceMap.value[row.id] = { message: '查询失败', supported: false }
    }
  } catch {
    balanceMap.value[row.id] = { message: '接口错误', supported: false }
  } finally {
    balanceLoading.value[row.id] = false
  }
}

const fetchQuota = async () => {
  quotaLoading.value = true
  try {
    const [statsRes, modelsRes]: any[] = await Promise.all([
      aiModelApi.getUsageStats({ range: quotaRange.value }),
      aiModelApi.getModels({ include_disabled: true }),
    ])
    const byModel: Record<string, any> = statsRes?.data?.data?.by_model ?? {}
    const allModels: AIModelConfig[] = modelsRes?.data?.data?.items ?? modelsRes?.data?.items ?? []

    quotaStats.value = allModels.map(m => {
      const s = byModel[String(m.id)]
      const consumed = s?.tokens ?? 0
      const quota = m.monthly_quota ?? null
      const remaining = quota !== null ? Math.max(0, quota - consumed) : null
      const pct = quota ? Math.min(100, Math.round((consumed / quota) * 100)) : null
      return {
        id: m.id,
        name: m.name,
        model_type: m.model_type,
        provider: m.provider,
        is_enabled: m.is_enabled,
        consumed,
        quota,
        remaining,
        pct,
        cost: s?.cost ?? 0,
        calls: s?.calls ?? 0,
      }
    })
  } catch {
    ElMessage.error('获取额度统计失败')
  } finally {
    quotaLoading.value = false
  }
}

const quotaStatus = (row: any): '' | 'success' | 'warning' | 'exception' => {
  if (row.pct === null) return ''
  if (row.pct >= 90) return 'exception'
  if (row.pct >= 70) return 'warning'
  return 'success'
}

// ══════════════════════════════════════════════════════
// Init
// ══════════════════════════════════════════════════════
onMounted(() => {
  fetchModels()
  fetchLogs()
  fetchQuota()
})
</script>

<template>
  <div class="ai-model-page">
    <!-- 页头 -->
    <div class="page-header">
      <div class="flex items-center gap-3">
        <div class="header-icon">
          <el-icon :size="24"><Cpu /></el-icon>
        </div>
        <div>
          <h1 class="text-xl font-bold text-gray-800">AI 模型管理</h1>
          <p class="text-sm text-gray-500 mt-0.5">配置 API Key · 切换默认模型 · 查看调用日志与额度消耗</p>
        </div>
      </div>
      <el-button :icon="Refresh" @click="fetchModels(); fetchLogs(); fetchQuota()">刷新</el-button>
    </div>

    <!-- Tab 主体 -->
    <el-tabs v-model="activeTab" class="model-tabs">

      <!-- ══ Tab 1: 模型配置 ══ -->
      <el-tab-pane name="models">
        <template #label>
          <span class="flex items-center gap-1.5"><el-icon><Setting /></el-icon> 模型配置</span>
        </template>

        <div class="tab-toolbar">
          <span class="text-sm text-gray-500">共 {{ models.length }} 个模型</span>
          <el-button type="primary" :icon="Plus" @click="openAdd">添加模型</el-button>
        </div>

        <div v-loading="modelsLoading">
          <template v-for="(typeModels, type) in modelsByType" :key="type">
            <div class="type-section">
              <div class="type-label">
                <el-tag :type="type === 'text' ? 'primary' : type === 'audio' ? 'success' : 'warning'" effect="dark" size="small">
                  {{ typeLabel(type as string) }}
                </el-tag>
                <span class="ml-2 text-gray-400 text-sm">{{ typeModels.length }} 个</span>
              </div>

              <div class="model-grid">
                <div
                  v-for="m in typeModels" :key="m.id"
                  class="model-card" :class="{ disabled: !m.is_enabled }"
                >
                  <!-- 卡片头 -->
                  <div class="card-head">
                    <div class="flex items-center gap-2 min-w-0">
                      <span class="font-semibold text-gray-800 truncate">{{ m.name }}</span>
                      <el-tag v-if="m.is_default" type="warning" size="small" effect="plain">
                        <el-icon class="mr-0.5"><StarFilled /></el-icon>默认
                      </el-tag>
                      <el-tag v-if="!m.is_enabled" type="info" size="small">已禁用</el-tag>
                    </div>
                    <el-dropdown trigger="click" @command="(cmd: string) => {
                      if (cmd === 'edit') openEdit(m)
                      else if (cmd === 'default') setDefault(m)
                      else if (cmd === 'toggle') toggleStatus(m)
                      else if (cmd === 'delete') deleteModel(m)
                    }">
                      <el-button text :icon="Setting" size="small" />
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="edit"><el-icon><Edit /></el-icon> 编辑</el-dropdown-item>
                          <el-dropdown-item v-if="!m.is_default && m.is_enabled" command="default">
                            <el-icon><Star /></el-icon> 设为默认
                          </el-dropdown-item>
                          <el-dropdown-item command="toggle">
                            <el-icon><Switch /></el-icon> {{ m.is_enabled ? '禁用' : '启用' }}
                          </el-dropdown-item>
                          <el-dropdown-item command="delete" divided>
                            <span class="text-red-500"><el-icon><Delete /></el-icon> 删除</span>
                          </el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>

                  <!-- 卡片信息 -->
                  <div class="card-body">
                    <div class="info-row"><span class="lbl">提供商</span><span>{{ providerLabel(m.provider) }}</span></div>
                    <div class="info-row">
                      <span class="lbl">模型 ID</span>
                      <code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">{{ m.model_id }}</code>
                    </div>
                    <div class="info-row">
                      <span class="lbl">API Key</span>
                      <span class="text-gray-400 text-xs font-mono">{{ m.api_key_masked || '****' }}</span>
                    </div>
                    <div class="info-row">
                      <span class="lbl">参数</span>
                      <span class="text-xs text-gray-500">{{ m.max_tokens }} tokens · {{ m.temperature }} temp</span>
                    </div>
                    <div class="info-row">
                      <span class="lbl">月度额度</span>
                      <span class="text-xs">
                        {{ m.monthly_quota ? `${(m.monthly_quota / 1000).toFixed(0)}K tokens` : '不限制' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- 空状态 -->
                <div v-if="typeModels.length === 0" class="model-card model-card-empty" @click="openAdd">
                  <el-icon :size="28" class="text-gray-300"><Plus /></el-icon>
                  <span class="text-gray-400 text-sm mt-2">点击添加{{ typeLabel(type as string) }}模型</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- ══ Tab 2: 调用日志 ══ -->
      <el-tab-pane name="logs">
        <template #label>
          <span class="flex items-center gap-1.5"><el-icon><DataAnalysis /></el-icon> 调用日志</span>
        </template>

        <!-- 筛选栏 -->
        <div class="filter-bar">
          <el-select v-model="logFilter.model_id" placeholder="全部模型" clearable style="width:160px">
            <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
          <el-select v-model="logFilter.usage_type" placeholder="全部类型" clearable style="width:130px">
            <el-option v-for="t in usageTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-select v-model="logFilter.is_success" placeholder="全部状态" clearable style="width:110px">
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
          <el-select v-model="logFilter.range" style="width:120px">
            <el-option v-for="r in rangeOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="fetchLogs(1)">查询</el-button>
        </div>

        <el-table :data="logs" v-loading="logsLoading" size="small" stripe border class="log-table">
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">
              <span class="text-xs text-gray-500">{{ new Date(row.created_at).toLocaleString() }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="model_name" label="模型" width="140">
            <template #default="{ row }">
              <el-tag size="small" type="primary" effect="plain">{{ row.model_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="110" />
          <el-table-column prop="usage_type" label="类型" width="100">
            <template #default="{ row }">
              <span class="text-xs">{{ usageTypeMap[row.usage_type] ?? row.usage_type }}</span>
            </template>
          </el-table-column>
          <el-table-column label="输入 / 输出" width="130" align="center">
            <template #default="{ row }">
              <span class="text-xs font-mono">{{ formatTokens(row.input_tokens) }} / {{ formatTokens(row.output_tokens) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="total_tokens" label="总 Token" width="90" align="right">
            <template #default="{ row }">
              <span class="font-mono text-sm font-medium">{{ formatTokens(row.total_tokens) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="耗时" width="80" align="right">
            <template #default="{ row }">
              <span class="text-xs text-gray-500">{{ formatLatency(row.latency_ms) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="estimated_cost" label="估算费用" width="90" align="right">
            <template #default="{ row }">
              <span class="text-amber-600 text-xs font-mono">¥{{ row.estimated_cost.toFixed(4) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="is_success" label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_success ? 'success' : 'danger'" size="small" effect="plain">
                {{ row.is_success ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误信息" min-width="160">
            <template #default="{ row }">
              <span v-if="row.error_message" class="text-red-500 text-xs">{{ row.error_message }}</span>
              <span v-else class="text-gray-300 text-xs">—</span>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-row">
          <span class="text-sm text-gray-400">共 {{ logsTotal }} 条记录</span>
          <el-pagination
            v-model:current-page="logsPage"
            :page-size="logsPageSize"
            :total="logsTotal"
            layout="prev, pager, next"
            small
            @current-change="fetchLogs"
          />
        </div>
      </el-tab-pane>

      <!-- ══ Tab 3: 额度统计 ══ -->
      <el-tab-pane name="quota">
        <template #label>
          <span class="flex items-center gap-1.5"><el-icon><PieChart /></el-icon> 额度统计</span>
        </template>

        <div class="tab-toolbar">
          <el-radio-group v-model="quotaRange" @change="fetchQuota">
            <el-radio-button v-for="r in rangeOptions" :key="r.value" :label="r.value">{{ r.label }}</el-radio-button>
          </el-radio-group>
          <el-button :icon="Refresh" @click="fetchQuota">刷新</el-button>
        </div>

        <el-table :data="quotaStats" v-loading="quotaLoading" stripe border>
          <el-table-column prop="name" label="模型名称" min-width="140">
            <template #default="{ row }">
              <div class="flex items-center gap-2">
                <el-tag :type="row.model_type === 'text' ? 'primary' : row.model_type === 'audio' ? 'success' : 'warning'" size="small" effect="plain">
                  {{ typeLabel(row.model_type) }}
                </el-tag>
                <span class="font-medium">{{ row.name }}</span>
                <el-tag v-if="!row.is_enabled" type="info" size="small">已禁用</el-tag>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="calls" label="调用次数" width="90" align="right">
            <template #default="{ row }">
              <span class="font-mono font-medium">{{ row.calls }}</span>
            </template>
          </el-table-column>

          <el-table-column label="已消耗 Token" width="130" align="right">
            <template #default="{ row }">
              <span class="font-mono text-blue-600">{{ formatTokens(row.consumed) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="月度额度" width="130" align="right">
            <template #default="{ row }">
              <span v-if="row.quota" class="font-mono">{{ formatTokens(row.quota) }}</span>
              <span v-else class="text-gray-400 text-xs">不限制</span>
            </template>
          </el-table-column>

          <el-table-column label="剩余额度" width="130" align="right">
            <template #default="{ row }">
              <span v-if="row.remaining !== null" :class="['font-mono font-semibold', row.pct >= 90 ? 'text-red-500' : row.pct >= 70 ? 'text-amber-500' : 'text-green-600']">
                {{ formatTokens(row.remaining) }}
              </span>
              <span v-else class="text-gray-400 text-xs">不限制</span>
            </template>
          </el-table-column>

          <el-table-column label="使用进度" width="200">
            <template #default="{ row }">
              <div v-if="row.pct !== null" class="flex items-center gap-2">
                <el-progress
                  :percentage="row.pct"
                  :status="quotaStatus(row)"
                  :stroke-width="8"
                  style="flex:1"
                  :show-text="false"
                />
                <span class="text-xs w-8 text-right font-mono">{{ row.pct }}%</span>
              </div>
              <span v-else class="text-gray-400 text-xs">—</span>
            </template>
          </el-table-column>

          <el-table-column prop="cost" label="估算费用" width="100" align="right">
            <template #default="{ row }">
              <span class="text-amber-600 font-mono">¥{{ row.cost.toFixed(2) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="API 账户余额" min-width="180">
            <template #default="{ row }">
              <div v-if="balanceMap[row.id]" class="text-xs">
                <div v-if="balanceMap[row.id].supported !== false && balanceMap[row.id].balance !== null"
                  class="font-semibold text-green-600">¥{{ Number(balanceMap[row.id].balance).toFixed(2) }}
                  <span class="text-gray-400 ml-1">{{ balanceMap[row.id].currency }}</span>
                  <span v-if="balanceMap[row.id].granted_balance" class="text-blue-400 ml-2">
                    (赠: ¥{{ Number(balanceMap[row.id].granted_balance).toFixed(2) }})
                  </span>
                </div>
                <div class="text-gray-400 text-xs mt-0.5">{{ balanceMap[row.id].message }}</div>
                <div v-if="balanceMap[row.id].local_stats" class="text-gray-500 mt-1">
                  本系统消耗: {{ formatTokens(balanceMap[row.id].local_stats.total_tokens) }} tokens
                  · {{ balanceMap[row.id].local_stats.total_calls }} 次
                  · ¥{{ balanceMap[row.id].local_stats.estimated_cost }}
                </div>
              </div>
              <span v-else class="text-gray-300 text-xs">—</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button
                size="small" type="primary" plain
                :loading="balanceLoading[row.id]"
                @click="checkBalance(row)"
              >查询余额</el-button>
              <el-button text size="small" :icon="Edit" @click="activeTab='models'" title="去编辑额度" />
            </template>
          </el-table-column>
        </el-table>

        <el-alert
          title="额度说明"
          type="info" :closable="false" show-icon class="mt-4"
        >
          <template #default>
            <span class="text-sm text-gray-600">
              月度额度在模型配置中设置（<code>monthly_quota</code> 字段，单位 Token）；
              "不限制"表示未设置上限。进度条颜色：绿色 &lt;70%，橙色 70‑90%，红色 ≥90%。
              支持 DashScope、DeepSeek、Moonshot 余额查询。
            </span>
          </template>
        </el-alert>
      </el-tab-pane>
    </el-tabs>

    <!-- ══ 模型编辑对话框 ══ -->
    <el-dialog v-model="showDialog" :title="dialogTitle" width="620px" destroy-on-close>
      <el-form :model="form" label-width="120px" label-position="right">
        <el-form-item label="模型名称" required>
          <el-input v-model="form.name" placeholder="例：通义千问 Plus" />
        </el-form-item>
        <el-form-item label="提供商" required>
          <el-select v-model="form.provider" style="width:100%">
            <el-option v-for="p in providerOptions" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型 ID" required>
          <el-input v-model="form.model_id" placeholder="例：qwen-plus" font-family="monospace" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <div class="flex gap-2 w-full">
            <el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." style="flex:1" />
            <el-button :loading="testingId === -1" :icon="Connection" @click="testConnection">测试连接</el-button>
          </div>
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="form.api_base_url" placeholder="留空使用默认端点" />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-radio-group v-model="form.model_type">
            <el-radio-button v-for="t in modelTypeOptions" :key="t.value" :label="t.value">{{ t.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="最大 Token">
              <el-input-number v-model="form.max_tokens" :min="512" :max="200000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="温度">
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="每千 Token 价格">
              <el-input-number v-model="form.price_per_1k_tokens" :min="0" :step="0.001" :precision="4" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="月度额度(Token)">
              <el-input-number
                v-model="form.monthly_quota"
                :min="0"
                :step="100000"
                placeholder="不填=不限制"
                style="width:100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="排序优先级">
              <el-input-number v-model="form.priority" :min="1" :max="999" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.is_enabled" active-text="启用" inactive-text="禁用" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" active-text="是（同类型其余自动取消）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简短描述此模型的用途" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveModel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ai-model-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.header-icon {
  width: 48px;
  height: 48px;
  background: #0891b2;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.model-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 0;
}

/* ── 模型配置 ── */
.type-section {
  margin-bottom: 24px;
}

.type-label {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.model-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  transition: box-shadow .2s;
}

.model-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}

.model-card.disabled {
  opacity: .55;
}

.model-card-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  cursor: pointer;
  border: 2px dashed #d1d5db;
  background: #f9fafb;
}

.model-card-empty:hover {
  border-color: #06b6d4;
  background: #f0fdfe;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #374151;
}

.info-row .lbl {
  color: #9ca3af;
  min-width: 56px;
  flex-shrink: 0;
}

/* ── 调用日志 ── */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.log-table {
  font-size: 12px;
}

.pagination-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}
</style>
