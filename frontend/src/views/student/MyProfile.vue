<script setup lang="ts">
/**
 * 学生成长画像页面
 * 展示雷达图、趋势图、行动建议等
 */
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { RadarChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import AIGrowthTimeline from '@/components/AIGrowthTimeline.vue'
import { aiApi } from '@/api'
import { 
  TrendCharts, DataAnalysis, Timer, Trophy, Star, Flag, 
  ArrowUp, ArrowDown, Minus, Refresh, QuestionFilled, Cpu 
} from '@element-plus/icons-vue'

// 注册 ECharts 组件
use([RadarChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const authStore = useAuthStore()
const loading = ref(false)
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const lastUpdatedAt = ref<string>('')
const hasGenerated = ref(false)

const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7天

const isDataExpired = computed(() => {
  if (!lastUpdatedAt.value) return true
  return Date.now() - new Date(lastUpdatedAt.value).getTime() > CACHE_TTL_MS
})

const formatLastUpdated = computed(() => {
  if (!lastUpdatedAt.value) return ''
  const d = new Date(lastUpdatedAt.value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})

// 画像数据
const profileData = ref<any>({
  radar: [],
  trend: [],
  action_items: [],
  overall_score: 0,
  stats: {
    total_submissions: 0,
    approved_submissions: 0,
    average_score: 0
  }
})

// 获取批次列表（不自动加载画像）
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
  } catch (error) {
    ElMessage.error('获取批次失败')
  }
}

// 用户手动触发生成画像
const startAnalysis = async () => {
  hasGenerated.value = true
  await fetchProfile()
}

// 获取画像数据
const fetchProfile = async () => {
  if (!selectedSemesterId.value) return
  loading.value = true
  try {
    const res: any = await api.get('/profile/me', { 
      params: { semester_id: selectedSemesterId.value } 
    })
    const data = res.success ? res.data : res
    if (data) {
      profileData.value = data
      lastUpdatedAt.value = data.updated_at || ''
    }
    // 数据过期（>7天）则自动触发后台重算
    if (isDataExpired.value && profileData.value.stats?.total_submissions > 0) {
      handleRefresh()
      return
    }
    // 获取 AI 叙事
    fetchAINarrative()
  } catch (error: any) {
    if (error.response?.status === 404) {
      profileData.value = {
        radar: [],
        trend: [],
        action_items: [],
        overall_score: 0,
        stats: { total_submissions: 0, approved_submissions: 0, average_score: 0 }
      }
    } else {
      ElMessage.error('获取画像失败')
    }
  } finally {
    loading.value = false
  }
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
  const data = profileData.value
  if (!data || data.stats.total_submissions === 0) return
  aiNarrativeLoading.value = true
  try {
    const radar = data.radar || []
    const weakDims = [...radar].sort((a: any, b: any) => (a.score ?? 0) - (b.score ?? 0)).slice(0, 2)
    const strongDims = [...radar].sort((a: any, b: any) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 2)
    const res = await aiApi.dataNarrative({
      role: 'student',
      stats: {
        overall_score: data.overall_score,
        total_submissions: data.stats.total_submissions,
        approved_submissions: data.stats.approved_submissions,
        average_score: data.stats.average_score,
        weak_dimensions: weakDims.map((d: any) => `${d.label}(${d.score}分)`).join('、'),
        strong_dimensions: strongDims.map((d: any) => `${d.label}(${d.score}分)`).join('、'),
        action_items_count: data.action_items?.length || 0,
        context: '学生成长画像综合分析'
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

// 雷达图配置
const radarOption = computed(() => {
  const radar = profileData.value.radar || []
  if (radar.length === 0) return null

  // 分类数据
  const lessonPlanDims = radar.filter((d: any) => d.category === 'lesson_plan')
  const videoDims = radar.filter((d: any) => d.category === 'video')
  const allDims = [...lessonPlanDims, ...videoDims]

  return {
    animation: true,
    animationDuration: 1500,
    animationEasing: 'elasticOut',
    tooltip: {
      trigger: 'item'
    },
    legend: {
      data: ['教案能力', '视频表现', '综合能力'],
      bottom: 0,
      textStyle: { color: '#666' }
    },
    radar: {
      indicator: allDims.map((d: any) => ({
        name: d.label,
        max: 100
      })),
      center: ['50%', '48%'],
      radius: '65%',
      axisName: {
        color: '#666',
        fontSize: 11
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(8, 145, 178, 0.02)', 'rgba(8, 145, 178, 0.04)', 
                  'rgba(8, 145, 178, 0.06)', 'rgba(8, 145, 178, 0.08)']
        }
      },
      splitLine: {
        lineStyle: { color: 'rgba(8, 145, 178, 0.1)' }
      },
      axisLine: {
        lineStyle: { color: 'rgba(8, 145, 178, 0.15)' }
      }
    },
    series: [
      {
        name: '能力画像',
        type: 'radar',
        data: [
          {
            value: lessonPlanDims.map((d: any) => d.score).concat(Array(videoDims.length).fill(0)),
            name: '教案能力',
            lineStyle: { color: '#0891b2', width: 2 },
            areaStyle: { color: 'rgba(8, 145, 178, 0.15)' },
            itemStyle: { color: '#0891b2' }
          },
          {
            value: Array(lessonPlanDims.length).fill(0).concat(videoDims.map((d: any) => d.score)),
            name: '视频表现',
            lineStyle: { color: '#10b981', width: 2 },
            areaStyle: { color: 'rgba(16, 185, 129, 0.15)' },
            itemStyle: { color: '#10b981' }
          },
          {
            value: allDims.map((d: any) => d.score),
            name: '综合能力',
            lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
            areaStyle: { color: 'rgba(245, 158, 11, 0.08)' },
            itemStyle: { color: '#f59e0b' }
          }
        ]
      }
    ]
  }
})

// 趋势图配置
const trendOption = computed(() => {
  const trend = profileData.value.trend || []
  if (trend.length === 0) return null

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e5e7eb',
      textStyle: { color: '#374151' },
      formatter: (params: any) => {
        const item = params[0]
        return `
          <div style="padding: 4px 8px;">
            <div style="color: #9ca3af; font-size: 12px;">${item.axisValue}</div>
            <div style="margin-top: 4px; font-weight: 600; color: #0891b2;">
              得分: ${item.value}分
            </div>
          </div>
        `
      }
    },
    grid: {
      top: 20,
      right: 20,
      bottom: 30,
      left: 45
    },
    xAxis: {
      type: 'category',
      data: trend.map((t: any) => {
        const d = new Date(t.date)
        return `${d.getMonth() + 1}/${d.getDate()}`
      }),
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { color: '#9ca3af', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#f3f4f6' } },
      axisLabel: { color: '#9ca3af', fontSize: 11 }
    },
    series: [
      {
        type: 'line',
        data: trend.map((t: any) => t.overall_score),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: {
          color: '#0891b2',
          width: 3
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(8, 145, 178, 0.3)' },
              { offset: 1, color: 'rgba(8, 145, 178, 0.02)' }
            ]
          }
        },
        itemStyle: { color: '#0891b2' }
      }
    ]
  }
})

// 获取评分等级
const getScoreLevel = (score: number) => {
  if (score >= 90) return { text: '优秀', color: '#10b981', bg: 'bg-emerald-50' }
  if (score >= 80) return { text: '良好', color: '#0891b2', bg: 'bg-cyan-50' }
  if (score >= 70) return { text: '中等', color: '#f59e0b', bg: 'bg-amber-50' }
  if (score >= 60) return { text: '及格', color: '#ef4444', bg: 'bg-red-50' }
  return { text: '待提高', color: '#9ca3af', bg: 'bg-gray-50' }
}

// 获取优先级图标
const getPriorityIcon = (priority: number) => {
  return priority === 1 ? ArrowUp : priority === 2 ? Minus : ArrowDown
}

// 刷新画像
const handleRefresh = async () => {
  loading.value = true
  try {
    await api.post('/profile/recompute', null, {
      params: { semester_id: selectedSemesterId.value }
    })
    ElMessage.success('画像更新成功')
    await fetchProfile()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    loading.value = false
  }
}

watch(selectedSemesterId, (newId) => {
  if (!newId || !hasGenerated.value) return
  fetchProfile()
})

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading" class="profile-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <div class="flex items-center gap-3">
          <h2 class="profile-page-title">
            <span class="w-2.5 h-6 rounded-full bg-gradient-to-b from-indigo-500 to-cyan-500 inline-block mr-1"></span>
            我的成长画像
          </h2>
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-200/60 flex items-center gap-1">
            <el-icon :size="12"><Cpu /></el-icon>
            AI 多维能力建模
          </span>
        </div>
        <p class="profile-page-desc">基于历次试讲录像与教案数据，AI 深度解构教态、板书、语音与设计能力</p>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="formatLastUpdated" class="text-xs text-slate-400">上次更新: {{ formatLastUpdated }}</span>
        <el-select
          v-model="selectedSemesterId"
          placeholder="选择批次"
          class="w-52"
        >
          <el-option
            v-for="s in semesters"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
        <el-tooltip content="手动刷新画像数据（自动每7天更新一次）" placement="bottom">
          <el-button :icon="Refresh" @click="handleRefresh" circle class="!border-slate-200 shadow-xs" />
        </el-tooltip>
      </div>
    </div>

    <!-- 未生成画像：空状态引导 -->
    <div v-if="!hasGenerated && !loading" class="empty-state">
      <div class="empty-hero">
        <div class="hero-icon-wrapper">
          <el-icon :size="44"><TrendCharts /></el-icon>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-600 border border-indigo-200/60 mb-2">
          AI 多模态智能测评
        </span>
        <h3 class="hero-title">生成我的专属教学能力画像</h3>
        <p class="hero-desc">AI 将综合解析所有已提交教案规范与试讲微格视频，从姿态站位、语速起伏、教学互动、重难点把握等 6 大核心维度进行能力雷达建模与提分建议。</p>
        <div class="hero-features">
          <div class="feature-item">
            <el-icon class="text-indigo-500"><DataAnalysis /></el-icon>
            <span>六维能力雷达图</span>
          </div>
          <div class="feature-item">
            <el-icon class="text-emerald-500"><TrendCharts /></el-icon>
            <span>成绩成长轨迹</span>
          </div>
          <div class="feature-item">
            <el-icon class="text-amber-500"><Flag /></el-icon>
            <span>靶向薄弱点分析</span>
          </div>
          <div class="feature-item">
            <el-icon class="text-cyan-500"><Cpu /></el-icon>
            <span>大模型导师评语</span>
          </div>
        </div>
        <el-button type="primary" size="large" @click="startAnalysis" :loading="loading" class="hero-btn">
          <el-icon class="mr-1.5"><Cpu /></el-icon>启动 AI 画像分析
        </el-button>
        <p class="hero-hint">分析引擎正在待命，点击即可即刻获取全量诊断报告</p>
      </div>
    </div>

    <!-- 已生成但没有数据 -->
    <el-empty 
      v-else-if="hasGenerated && !loading && profileData.stats.total_submissions === 0" 
      description="暂无提交记录，完成任务后将生成画像"
      class="mt-12"
    />

    <!-- 主内容 -->
    <div v-else-if="hasGenerated" class="profile-content">
      <!-- 顶部统计卡片 -->
      <div class="stats-row">
        <div class="stat-card stat-card-modern overall-score">
          <div class="stat-icon stat-icon-trophy">
            <el-icon :size="24"><Trophy /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-indigo-600">
              {{ profileData.overall_score }}
              <span class="stat-unit text-slate-400">分</span>
            </div>
            <div class="stat-label">AI 综合评分</div>
          </div>
          <span 
            class="score-pill-tag"
            :style="{ background: getScoreLevel(profileData.overall_score).color }"
          >
            {{ getScoreLevel(profileData.overall_score).text }}
          </span>
        </div>

        <div class="stat-card stat-card-modern">
          <div class="stat-icon stat-icon-blue">
            <el-icon :size="24"><DataAnalysis /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-slate-800">
              {{ profileData.stats.approved_submissions }}<span class="text-sm font-normal text-slate-400">/{{ profileData.stats.total_submissions }}</span>
            </div>
            <div class="stat-label">通过 / 交付次数</div>
          </div>
        </div>

        <div class="stat-card stat-card-modern">
          <div class="stat-icon stat-icon-teal">
            <el-icon :size="24"><Star /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-emerald-600">
              {{ profileData.stats.average_score || 0 }}
              <span class="stat-unit text-slate-400">分</span>
            </div>
            <div class="stat-label">学期平均分</div>
          </div>
        </div>

        <div class="stat-card stat-card-modern">
          <div class="stat-icon stat-icon-amber">
            <el-icon :size="24"><Flag /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value text-amber-600">
              {{ profileData.action_items?.length || 0 }}
              <span class="stat-unit text-slate-400">项</span>
            </div>
            <div class="stat-label">AI 提分行动点</div>
          </div>
        </div>
      </div>

      <!-- AI 数据叙事 -->
      <div v-if="(aiNarrative || aiNarrativeLoading) && profileData.stats.total_submissions > 0" class="ai-narrative-card-profile">
        <div class="ai-narrative-inner-profile">
          <div class="ai-narrative-icon-profile">
            <el-icon :size="22" color="#0891b2"><Cpu /></el-icon>
          </div>
          <div class="ai-narrative-body-profile">
            <div class="ai-narrative-label-profile">
              <span class="label-text-profile">AI 画像解读</span>
              <div class="ai-gen-badge" style="margin-left: 8px;">
                <span class="badge-dot"></span>
                <span>AI 生成</span>
              </div>
            </div>
            <div v-if="aiNarrativeLoading && !aiNarrativeDisplayed" class="ai-narrative-text-profile loading">
              AI 正在分析你的成长画像...
            </div>
            <div v-else class="ai-narrative-text-profile">
              {{ aiNarrativeDisplayed }}<span v-if="aiNarrativeLoading" class="typing-dot-profile">|</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 图表区域 -->
      <div class="charts-row">
        <!-- 雷达图 -->
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="flex items-center gap-2">
              <span class="w-1 h-4 bg-cyan-500 rounded-full"></span>
              <span class="font-bold text-gray-800">能力雷达图</span>
              <el-tooltip content="展示教案设计和视频表现的多维度能力评估" placement="top">
                <el-icon class="text-gray-400 cursor-help"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div class="chart-container">
            <v-chart v-if="radarOption" :option="radarOption as any" autoresize />
            <el-empty v-else description="暂无数据" :image-size="80" />
          </div>
        </el-card>

        <!-- 趋势图 -->
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="flex items-center gap-2">
              <span class="w-1 h-4 bg-emerald-500 rounded-full"></span>
              <span class="font-bold text-gray-800">成绩趋势</span>
              <el-tooltip content="展示历次提交的成绩变化趋势" placement="top">
                <el-icon class="text-gray-400 cursor-help"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div class="chart-container">
            <v-chart v-if="trendOption" :option="trendOption" autoresize />
            <el-empty v-else description="暂无数据" :image-size="80" />
          </div>
        </el-card>
      </div>

      <!-- AI 成长时间线 -->
      <el-card class="timeline-card" shadow="never">
        <template #header>
          <div class="flex items-center gap-2">
            <span class="w-1 h-4 bg-teal-500 rounded-full"></span>
            <span class="font-bold text-gray-800">AI 成长时间线</span>
            <div class="ai-gen-badge" style="margin-left: 8px;">
              <span class="badge-dot"></span>
              <span>AI 预测</span>
            </div>
          </div>
        </template>
        <AIGrowthTimeline :semester-id="selectedSemesterId" />
      </el-card>

      <!-- AI 能力对比分析 -->
      <el-card v-if="profileData.trend && profileData.trend.length >= 2" class="comparison-card" shadow="never">
        <template #header>
          <div class="flex items-center gap-2">
            <span class="w-1 h-4 bg-blue-500 rounded-full"></span>
            <span class="font-bold text-gray-800">AI 能力对比分析</span>
            <el-tag size="small" effect="plain" type="info" round>首次 vs 最近</el-tag>
          </div>
        </template>
        <div class="comparison-body">
          <div class="comparison-summary">
            <div class="comp-item first">
              <div class="comp-label">首次评分</div>
              <div class="comp-value">{{ profileData.trend[0]?.overall_score || 0 }}</div>
            </div>
            <div class="comp-arrow">
              <span class="arrow-icon" :class="(profileData.trend[profileData.trend.length - 1]?.overall_score || 0) >= (profileData.trend[0]?.overall_score || 0) ? 'up' : 'down'">
                {{ (profileData.trend[profileData.trend.length - 1]?.overall_score || 0) >= (profileData.trend[0]?.overall_score || 0) ? '↑' : '↓' }}
              </span>
              <span class="arrow-diff" :class="(profileData.trend[profileData.trend.length - 1]?.overall_score || 0) >= (profileData.trend[0]?.overall_score || 0) ? 'up' : 'down'">
                {{ Math.abs((profileData.trend[profileData.trend.length - 1]?.overall_score || 0) - (profileData.trend[0]?.overall_score || 0)) }} 分
              </span>
            </div>
            <div class="comp-item latest">
              <div class="comp-label">最近评分</div>
              <div class="comp-value">{{ profileData.trend[profileData.trend.length - 1]?.overall_score || 0 }}</div>
            </div>
          </div>
          <div class="comparison-detail">
            <div class="detail-item" v-if="profileData.radar?.length">
              <span class="detail-icon"></span>
              <span class="detail-text">
                共完成 <strong>{{ profileData.stats.total_submissions }}</strong> 次试讲练习，
                通过 <strong>{{ profileData.stats.approved_submissions }}</strong> 次，
                综合能力
                <strong :class="(profileData.trend[profileData.trend.length - 1]?.overall_score || 0) >= (profileData.trend[0]?.overall_score || 0) ? 'text-green-600' : 'text-red-500'">
                  {{ (profileData.trend[profileData.trend.length - 1]?.overall_score || 0) >= (profileData.trend[0]?.overall_score || 0) ? '持续提升' : '有所波动' }}
                </strong>
              </span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- AI 综合评语 -->
      <el-card v-if="profileData.overall_score > 0" class="ai-comment-card" shadow="never">
        <template #header>
          <div class="flex items-center gap-2">
            <span class="w-1 h-4 bg-cyan-500 rounded-full"></span>
            <span class="font-bold text-gray-800">AI 综合评语</span>
            <div class="ai-gen-badge">
              <span class="badge-dot"></span>
              <span>AI 生成</span>
            </div>
          </div>
        </template>
        <div class="ai-comment-body">
          <div class="comment-avatar"><el-icon :size="20"><Cpu /></el-icon></div>
          <div class="comment-content">
            <p v-if="profileData.overall_score >= 90" class="comment-text">
              你的教学能力表现非常出色！教案设计和视频表现都展现了较高的专业素养。继续保持这份热情，尝试更多创新的教学方法，你一定能成为一名优秀的教师。
            </p>
            <p v-else-if="profileData.overall_score >= 80" class="comment-text">
              整体表现良好，基础扎实。建议在教学互动和课堂管理方面进一步提升，多观看优秀教师的教学视频，学习他们的授课技巧。
            </p>
            <p v-else-if="profileData.overall_score >= 70" class="comment-text">
              你已经具备了基本的教学能力，但仍有提升空间。重点关注下方的改进建议，针对薄弱环节进行专项练习，每次试讲后回顾AI分析报告，逐步提高。
            </p>
            <p v-else class="comment-text">
              不要灰心，教学能力需要时间积累。建议多参考AI生成的教案模板，利用备课助手进行模拟练习。每一次尝试都是进步，坚持练习一定会看到显著提升。
            </p>
            <div class="comment-meta">
              基于 {{ profileData.stats.total_submissions }} 次提交数据分析 · AI 综合评估
            </div>
          </div>
        </div>
      </el-card>

      <!-- 行动建议 -->
      <el-card class="action-card" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-1 h-4 bg-amber-500 rounded-full"></span>
              <span class="font-bold text-gray-800">改进建议</span>
              <el-tag type="warning" size="small" effect="plain" round>
                {{ profileData.action_items?.length || 0 }} 项
              </el-tag>
            </div>
          </div>
        </template>
        
        <div v-if="profileData.action_items?.length > 0" class="action-list">
          <div 
            v-for="(item, index) in profileData.action_items" 
            :key="index"
            class="action-item"
            :class="{ 'border-amber-200 bg-amber-50/50': item.priority === 1 }"
          >
            <div class="action-priority" :class="{
              'bg-red-100 text-red-600': item.priority === 1,
              'bg-amber-100 text-amber-600': item.priority === 2,
              'bg-blue-100 text-blue-600': item.priority === 3
            }">
              <el-icon><component :is="getPriorityIcon(item.priority)" /></el-icon>
              P{{ item.priority }}
            </div>
            <div class="action-content">
              <div class="action-dimension">
                <span class="font-medium text-gray-800">{{ item.dimension }}</span>
                <el-tag size="small" :type="item.current_score < 70 ? 'danger' : 'warning'" effect="plain">
                  {{ item.current_score }}分
                </el-tag>
              </div>
              <div class="action-suggestion">{{ item.suggestion }}</div>
            </div>
          </div>
        </div>
        <el-empty v-else description="太棒了！暂无需要改进的地方" :image-size="80" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.profile-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.profile-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.profile-title-icon { color: #0891b2; }

.profile-page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* AI Narrative */
.ai-narrative-card-profile {
  background: #ecfeff;
  border: 1px solid #cffafe;
  border-radius: 14px;
  padding: 18px 20px;
}

.ai-narrative-inner-profile {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.ai-narrative-icon-profile {
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

.ai-narrative-body-profile { flex: 1; min-width: 0; }

.ai-narrative-label-profile {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.label-text-profile {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.ai-narrative-text-profile {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}

.ai-narrative-text-profile.loading { color: #94a3b8; }

.typing-dot-profile {
  animation: blink-cursor-profile 1s infinite;
  color: #0891b2;
  font-weight: bold;
}

@keyframes blink-cursor-profile {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 统计卡片行 */
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
}

.stat-card-modern {
  background: #ffffff;
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.25rem 1.5rem;
  border-radius: 16px;
  position: relative;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-card-modern:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px -4px rgba(15, 23, 42, 0.09);
  border-color: rgba(99, 102, 241, 0.25);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  flex-shrink: 0;
}

.stat-icon-trophy {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
}

.stat-icon-blue {
  background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
  box-shadow: 0 4px 14px rgba(14, 165, 233, 0.35);
}

.stat-icon-teal {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
}

.stat-icon-amber {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
}

.score-pill-tag {
  position: absolute;
  top: 12px;
  right: 12px;
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 800;
  line-height: 1.1;
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
  letter-spacing: -0.5px;
}

.stat-unit {
  font-size: 0.875rem;
  font-weight: 600;
  margin-left: 2px;
}

.stat-label {
  font-size: 12.5px;
  font-weight: 600;
  color: #64748b;
  margin-top: 4px;
}

/* 图表区域 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  border: none;
  border-radius: 1rem;
  overflow: hidden;
}

.chart-card :deep(.el-card__header) {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #f3f4f6;
}

.chart-container {
  height: 320px;
  padding: 0.5rem;
}

/* 成长时间线 */
.timeline-card {
  border: none;
  border-radius: 1rem;
}

.timeline-card :deep(.el-card__header) {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #f3f4f6;
}

/* 能力对比 */
.comparison-card {
  border: none;
  border-radius: 1rem;
}

.comparison-card :deep(.el-card__header) {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #f3f4f6;
}

.comparison-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comparison-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 16px 0;
}

.comp-item {
  text-align: center;
}

.comp-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.comp-value {
  font-size: 36px;
  font-weight: 800;
}

.comp-item.first .comp-value {
  color: #94a3b8;
}

.comp-item.latest .comp-value {
  color: #0891b2;
}

.comp-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.arrow-icon {
  font-size: 24px;
  font-weight: 800;
}

.arrow-icon.up { color: #10b981; }
.arrow-icon.down { color: #ef4444; }

.arrow-diff {
  font-size: 14px;
  font-weight: 700;
}

.arrow-diff.up { color: #10b981; }
.arrow-diff.down { color: #ef4444; }

.comparison-detail {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px 16px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
}

.detail-icon {
  font-size: 18px;
}

/* AI 综合评语 */
.ai-comment-card {
  border: none;
  border-radius: 1rem;
  background: #faf5ff;
  border: 1px solid #cffafe;
}

.ai-comment-card :deep(.el-card__header) {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #cffafe;
}

.ai-gen-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  background: #cffafe;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  color: #0891b2;
  margin-left: 8px;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0891b2;
  animation: badge-pulse 2s infinite;
}

@keyframes badge-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.ai-comment-body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.comment-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(8, 145, 178, 0.1);
}

.comment-content {
  flex: 1;
}

.comment-text {
  font-size: 0.9rem;
  line-height: 1.7;
  color: #374151;
  margin: 0;
}

.comment-meta {
  margin-top: 12px;
  font-size: 0.75rem;
  color: #9ca3af;
}

/* 行动建议 */
.action-card {
  border: none;
  border-radius: 1rem;
}

.action-card :deep(.el-card__header) {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #f3f4f6;
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.action-item {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  transition: all 0.2s;
}

.action-item:hover {
  border-color: #c7d2fe;
  background: #fafafa;
}

.action-priority {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  height: fit-content;
}

.action-content {
  flex: 1;
}

.action-dimension {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
}

.action-suggestion {
  font-size: 0.875rem;
  color: #6b7280;
  line-height: 1.5;
}

/* 空状态引导 */
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.empty-hero {
  text-align: center;
  max-width: 480px;
  padding: 2rem;
}

.hero-icon-wrapper {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #ecfeff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1.5rem;
  box-shadow: 0 8px 32px rgba(8, 145, 178, 0.15);
}

.hero-title {
  font-size: 1.5rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 0.75rem;
}

.hero-desc {
  font-size: 0.875rem;
  color: #64748b;
  line-height: 1.7;
  margin: 0 0 1.5rem;
}

.hero-features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin-bottom: 2rem;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0.625rem 1rem;
  background: #f8fafc;
  border-radius: 10px;
  font-size: 0.8125rem;
  color: #475569;
  font-weight: 500;
}

.hero-btn {
  padding: 0.75rem 2.5rem;
  font-size: 1rem;
  border-radius: 12px;
}

.hero-hint {
  font-size: 0.75rem;
  color: #94a3b8;
  margin: 1rem 0 0;
}
</style>
