<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DataLine, User, Warning, TrendCharts } from '@element-plus/icons-vue'
import api from '@/utils/request'

const loading = ref(false)
const semesters = ref<any[]>([])
const selectedSemesterId = ref<number | null>(null)
const insightsData = ref<any>(null)

const fetchSemesters = async () => {
  try {
    const res: any = await api.get('/semesters')
    semesters.value = res
    const active = res.find((s: any) => s.status === 'active')
    if (active) selectedSemesterId.value = active.id
    else if (res.length > 0) selectedSemesterId.value = res[0].id
    if (selectedSemesterId.value) fetchInsights()
  } catch (e) { console.error(e) }
}

const fetchInsights = async () => {
  if (!selectedSemesterId.value) return
  loading.value = true
  try {
    const res: any = await api.get('/instructor/class-insights', {
      params: { semester_id: selectedSemesterId.value },
      timeout: 12000
    })
    if (res.success) insightsData.value = res.data
  } catch (e: any) {
    ElMessage.error(e.message || '获取班级洞察失败')
  } finally { loading.value = false }
}

const dimLabels: Record<string, string> = {
  structure: '结构完整性', objectives: '教学目标', key_points: '重难点设计',
  teaching_process: '教学过程', teaching_methods: '教学方法',
  board_design: '板书设计', language: '语言表达'
}

const getScoreColor = (score: number) => {
  if (score >= 85) return '#10b981'
  if (score >= 70) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

onMounted(fetchSemesters)
</script>

<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold">AI 班级洞察</h2>
        <p class="text-sm text-gray-500 mt-1">AI 自动分析班级整体教学数据，发现共性问题和优势</p>
      </div>
      <el-select v-model="selectedSemesterId" placeholder="选择批次" @change="fetchInsights" style="width:200px">
        <el-option v-for="s in semesters" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
    </div>

    <el-empty v-if="!insightsData && !loading" description="暂无数据" />

    <template v-if="insightsData">
      <!-- 概览卡片 -->
      <el-row :gutter="16" class="mb-6">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="text-center">
              <el-icon :size="28" color="#3b82f6"><User /></el-icon>
              <div class="text-3xl font-bold mt-2">{{ insightsData.total_students }}</div>
              <div class="text-sm text-gray-500">学生总数</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="text-center">
              <el-icon :size="28" color="#10b981"><TrendCharts /></el-icon>
              <div class="text-3xl font-bold mt-2" :style="{color: getScoreColor(insightsData.class_avg_score)}">
                {{ insightsData.class_avg_score }}
              </div>
              <div class="text-sm text-gray-500">班级平均分</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="text-center">
              <el-icon :size="28" color="#f59e0b"><Warning /></el-icon>
              <div class="text-3xl font-bold mt-2 text-orange-500">{{ insightsData.student_tiers?.needs_attention?.count || 0 }}</div>
              <div class="text-sm text-gray-500">需关注学生</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="text-center">
              <el-icon :size="28" color="#0d9488"><DataLine /></el-icon>
              <div class="text-3xl font-bold mt-2 text-green-500">{{ insightsData.student_tiers?.excellent?.count || 0 }}</div>
              <div class="text-sm text-gray-500">优秀学生</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <!-- 各维度平均分 -->
        <el-col :span="14">
          <el-card shadow="hover" class="mb-6">
            <template #header><span class="font-bold">各维度班级平均分</span></template>
            <div v-if="insightsData.class_avg_dimensions" class="dimension-bars">
              <div v-for="(dim, key) in insightsData.class_avg_dimensions" :key="key" class="dim-bar-item">
                <div class="dim-bar-label">{{ dim.label }}</div>
                <div class="dim-bar-track">
                  <div class="dim-bar-fill" :style="{ width: dim.avg_score + '%', background: getScoreColor(dim.avg_score) }"></div>
                </div>
                <div class="dim-bar-score" :style="{ color: getScoreColor(dim.avg_score) }">{{ dim.avg_score }}</div>
                <el-tag v-if="dim.below_60_pct > 30" type="danger" size="small">{{ dim.below_60_pct }}%不及格</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 学生分层 -->
        <el-col :span="10">
          <el-card shadow="hover" class="mb-6">
            <template #header><span class="font-bold">学生分层</span></template>
            <div class="tier-section">
              <div class="tier-group">
                <div class="tier-header excellent">优秀 (≥85分) · {{ insightsData.student_tiers?.excellent?.count || 0 }}人</div>
                <div class="tier-students">
                  <el-tag v-for="s in (insightsData.student_tiers?.excellent?.students || []).slice(0, 8)" :key="s.id" type="success" size="small" class="mr-1 mb-1">{{ s.name }} {{ s.score }}</el-tag>
                </div>
              </div>
              <div class="tier-group">
                <div class="tier-header good">良好 (70-84分) · {{ insightsData.student_tiers?.good?.count || 0 }}人</div>
                <div class="tier-students">
                  <el-tag v-for="s in (insightsData.student_tiers?.good?.students || []).slice(0, 8)" :key="s.id" size="small" class="mr-1 mb-1">{{ s.name }} {{ s.score }}</el-tag>
                </div>
              </div>
              <div class="tier-group">
                <div class="tier-header attention">需关注 (&lt;70分) · {{ insightsData.student_tiers?.needs_attention?.count || 0 }}人</div>
                <div class="tier-students">
                  <el-tag v-for="s in (insightsData.student_tiers?.needs_attention?.students || []).slice(0, 8)" :key="s.id" type="danger" size="small" class="mr-1 mb-1">{{ s.name }} {{ s.score }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- AI 洞察 -->
      <el-card v-if="insightsData.ai_insights" shadow="hover" class="mb-6 ai-insight-card">
        <template #header>
          <div class="flex items-center gap-2">
            <span class="ai-badge">AI</span>
            <span class="font-bold">AI 教学建议</span>
          </div>
        </template>
        <div class="text-sm text-gray-700 mb-4 leading-relaxed">{{ insightsData.ai_insights.summary }}</div>
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="text-sm font-bold mb-2 text-blue-600">教学建议</div>
            <ul class="text-sm text-gray-600 pl-4">
              <li v-for="(s, i) in insightsData.ai_insights.teaching_suggestions" :key="i" class="mb-2">{{ s }}</li>
            </ul>
          </el-col>
          <el-col :span="12">
            <div class="text-sm font-bold mb-2 text-orange-500">重点关注领域</div>
            <ul class="text-sm text-gray-600 pl-4">
              <li v-for="(f, i) in insightsData.ai_insights.focus_areas" :key="i" class="mb-2">{{ f }}</li>
            </ul>
          </el-col>
        </el-row>
      </el-card>

      <!-- 薄弱维度 -->
      <el-card v-if="insightsData.weak_dimensions?.length" shadow="hover">
        <template #header><span class="font-bold text-orange-500">共性薄弱维度</span></template>
        <div class="flex flex-wrap gap-3">
          <div v-for="w in insightsData.weak_dimensions" :key="w.dimension" class="weak-dim-card">
            <div class="weak-dim-name">{{ w.dimension }}</div>
            <div class="weak-dim-score">{{ w.avg_score }}分</div>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.stat-card { border-radius: 12px; }
.dimension-bars { display: flex; flex-direction: column; gap: 14px; }
.dim-bar-item { display: flex; align-items: center; gap: 12px; }
.dim-bar-label { width: 80px; font-size: 13px; color: #374151; font-weight: 500; text-align: right; flex-shrink: 0; }
.dim-bar-track { flex: 1; height: 18px; background: #f3f4f6; border-radius: 9px; overflow: hidden; }
.dim-bar-fill { height: 100%; border-radius: 9px; transition: width 0.8s ease; }
.dim-bar-score { width: 40px; font-weight: 700; font-size: 14px; text-align: center; }
.tier-section { display: flex; flex-direction: column; gap: 14px; }
.tier-header { font-size: 13px; font-weight: 600; margin-bottom: 6px; padding: 4px 10px; border-radius: 6px; }
.tier-header.excellent { background: #f0fdf4; color: #16a34a; }
.tier-header.good { background: #eff6ff; color: #2563eb; }
.tier-header.attention { background: #fef2f2; color: #dc2626; }
.ai-insight-card { border: 1px solid #a5f3fc; background: #ecfeff; }
.ai-badge { background: #0891b2; color: white; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; }
.weak-dim-card { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 10px; padding: 12px 20px; text-align: center; }
.weak-dim-name { font-size: 13px; color: #9a3412; font-weight: 500; }
.weak-dim-score { font-size: 22px; font-weight: 700; color: #ea580c; margin-top: 4px; }
</style>
