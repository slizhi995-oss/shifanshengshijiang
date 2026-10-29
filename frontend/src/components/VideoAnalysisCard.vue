<template>
  <div class="video-analysis-card">
    <!-- 加载中状态 -->
    <div v-if="loading" class="text-center py-8">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p class="mt-4 text-gray-600">视频正在分析中...</p>
      <p class="text-sm text-gray-400">预计需要 3-5 分钟</p>
      <el-button class="mt-4" @click="fetchAnalysis">刷新状态</el-button>
    </div>

    <!-- 分析失败状态 -->
    <div v-else-if="analysisData?.status === 'failed'" class="text-center py-8">
      <el-icon :size="40" color="#f56c6c"><CircleClose /></el-icon>
      <p class="mt-4 text-red-500 font-medium">分析失败</p>
      <p class="text-sm text-gray-500 mt-2">{{ analysisData.message }}</p>
      <p class="text-xs text-gray-400 mt-1">{{ analysisData.error }}</p>
      <el-button class="mt-4" type="primary" @click="handleTriggerAnalysis" :loading="triggering">
        重新分析
      </el-button>
    </div>

    <!-- 未分析状态 -->
    <div v-else-if="!analysisData || analysisData.status === 'not_analyzed'" class="text-center py-8">
      <el-icon :size="40" color="#909399"><VideoCamera /></el-icon>
      <p class="mt-4 text-gray-600">{{ analysisData?.message || '视频尚未分析' }}</p>
      <el-button v-if="canTrigger" class="mt-4" type="primary" @click="handleTriggerAnalysis" :loading="triggering">
        开始分析
      </el-button>
    </div>

    <!-- 分析中状态 -->
    <div v-else-if="analysisData.status === 'processing'" class="text-center py-8">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p class="mt-4 text-gray-600">视频正在分析中...</p>
      <p class="text-sm text-gray-400">预计需要 3-5 分钟</p>
      <el-button class="mt-4" @click="fetchAnalysis">刷新状态</el-button>
    </div>

    <!-- 分析结果 -->
    <div v-else-if="analysis" class="analysis-result">
      <div class="result-header flex justify-between items-center mb-4">
        <h3 class="text-lg font-semibold"><el-icon><DataAnalysis /></el-icon> 视频AI分析报告</h3>
        <el-button v-if="canReanalyze" size="small" @click="handleReanalyze" :loading="triggering">
          重新分析
        </el-button>
      </div>

      <!-- 综合得分 -->
      <div class="score-section text-center mb-6">
        <div class="score-circle" :class="getScoreClass(analysis.overall_score)">
          <div class="score-value">{{ analysis.overall_score }}</div>
          <div class="score-label">综合得分</div>
        </div>
      </div>

      <!-- 详细指标 -->
      <el-row :gutter="16" class="mb-6">
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-item">
              <div class="metric-icon"><el-icon :size="28" color="#409eff"><Mic /></el-icon></div>
              <div class="metric-label">语速</div>
              <div class="metric-value">{{ analysis.speech_rate }}</div>
              <div class="metric-unit">字/分钟</div>
              <div class="metric-ideal">理想：120-160</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-item">
              <div class="metric-icon"><el-icon :size="28" color="#e6a23c"><VideoPause /></el-icon></div>
              <div class="metric-label">停顿次数</div>
              <div class="metric-value">{{ analysis.pause_count }}</div>
              <div class="metric-unit">次</div>
              <div class="metric-ideal">理想：≤3次</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-item">
              <div class="metric-icon"><el-icon :size="28" color="#f56c6c"><ChatLineSquare /></el-icon></div>
              <div class="metric-label">语气词</div>
              <div class="metric-value">{{ analysis.filler_word_count }}</div>
              <div class="metric-unit">次</div>
              <div class="metric-ideal">理想：≤5次</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-item">
              <div class="metric-icon"><el-icon :size="28" color="#909399"><Timer /></el-icon></div>
              <div class="metric-label">视频时长</div>
              <div class="metric-value-small">{{ formatDuration(analysis.duration) }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 语气词详情 -->
      <div v-if="analysis.filler_words && Object.keys(analysis.filler_words).length > 0" class="mb-6">
        <h4 class="section-title">语气词详情</h4>
        <div class="flex flex-wrap gap-2">
          <el-tag v-for="(count, word) in analysis.filler_words" :key="word" type="warning">
            {{ word }}: {{ count }}次
          </el-tag>
        </div>
      </div>

      <!-- 视觉分析 (云端AI分析) -->
      <div v-if="analysis.gesture_analysis && !analysis.gesture_analysis.error" class="mb-6">
        <h4 class="section-title">
          <el-icon><Film /></el-icon> 视觉分析
          <el-tag v-if="analysis.gesture_analysis.analysis_method === 'local_mediapipe'" size="small" type="info" class="ml-2">本地分析</el-tag>
          <el-tag v-else size="small" type="success" class="ml-2">云端AI分析</el-tag>
        </h4>
        
        <!-- 第一行：基础指标 -->
        <el-row :gutter="12" class="mb-4">
          <el-col :span="6">
            <div class="gesture-metric">
              <div class="gesture-label">姿态仪表</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.posture_score || 0" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.posture_score || 0)"
              />
              <div v-if="analysis.gesture_analysis.posture_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.posture_comment }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="gesture-metric">
              <div class="gesture-label">手势运用</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.gesture_score || 0" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.gesture_score || 0)"
              />
              <div v-if="analysis.gesture_analysis.gesture_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.gesture_comment }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="gesture-metric">
              <div class="gesture-label">眼神交流</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.eye_contact_score || 0" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.eye_contact_score || 0)"
              />
              <div v-if="analysis.gesture_analysis.eye_contact_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.eye_contact_comment }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="gesture-metric">
              <div class="gesture-label">表情管理</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.expression_score || 80" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.expression_score || 80)"
              />
              <div v-if="analysis.gesture_analysis.expression_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.expression_comment }}
              </div>
            </div>
          </el-col>
        </el-row>
        
        <!-- 第二行：进阶指标 -->
        <el-row :gutter="12" class="mb-4">
          <el-col :span="8">
            <div class="gesture-metric">
              <div class="gesture-label">空间运用</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.movement_score || 80" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.movement_score || 80)"
              />
              <div v-if="analysis.gesture_analysis.movement_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.movement_comment }}
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="gesture-metric">
              <div class="gesture-label">教具使用</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.teaching_aids_score || 80" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.teaching_aids_score || 80)"
              />
              <div v-if="analysis.gesture_analysis.teaching_aids_comment" class="gesture-comment">
                {{ analysis.gesture_analysis.teaching_aids_comment }}
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="gesture-metric">
              <div class="gesture-label">综合得分</div>
              <el-progress 
                type="circle" 
                :percentage="analysis.gesture_analysis.overall_gesture_score || 0" 
                :width="70"
                :stroke-width="6"
                :color="getProgressColor(analysis.gesture_analysis.overall_gesture_score || 0)"
              />
            </div>
          </el-col>
        </el-row>
        
        <!-- 亮点 -->
        <div v-if="analysis.gesture_analysis.highlights?.length" class="highlights-section mb-3">
          <div class="text-sm font-medium text-green-600 mb-2"><el-icon><Star /></el-icon> 亮点</div>
          <div class="flex flex-wrap gap-2">
            <el-tag v-for="(item, index) in analysis.gesture_analysis.highlights" :key="index" type="success" size="small">
              {{ item }}
            </el-tag>
          </div>
        </div>
        
        <!-- 待改进 -->
        <div v-if="analysis.gesture_analysis.improvements?.length" class="improvements-section mb-3">
          <div class="text-sm font-medium text-orange-600 mb-2"><el-icon><Edit /></el-icon> 待改进</div>
          <div class="flex flex-wrap gap-2">
            <el-tag v-for="(item, index) in analysis.gesture_analysis.improvements" :key="index" type="warning" size="small">
              {{ item }}
            </el-tag>
          </div>
        </div>
        
        <!-- 动作建议 (本地分析) -->
        <div v-if="analysis.gesture_analysis.gesture_suggestions?.length" class="gesture-suggestions">
          <ul>
            <li v-for="(suggestion, index) in analysis.gesture_analysis.gesture_suggestions" :key="index">
              {{ suggestion }}
            </li>
          </ul>
        </div>
      </div>

      <!-- 改进建议 -->
      <div class="mb-6">
        <h4 class="section-title"><el-icon><MagicStick /></el-icon> 语言改进建议</h4>
        <ul class="suggestions-list">
          <li v-for="(suggestion, index) in analysis.suggestions" :key="index">
            {{ suggestion }}
          </li>
        </ul>
      </div>

      <!-- 完整文字稿 -->
      <el-collapse class="mt-4">
        <el-collapse-item title="查看完整文字稿" name="transcript">
          <div class="transcript-content">
            {{ analysis.transcript }}
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- Token 使用量 -->
      <div class="token-usage-info mt-4">
        <div class="text-xs text-gray-400 flex flex-col gap-2">
          <div class="flex items-center gap-4">
            <span><el-icon><Coin /></el-icon> 本次分析消耗：</span>
            <template v-if="analysis.token_usage && analysis.token_usage.total_tokens > 0">
              <span>
                Token: {{ analysis.token_usage.total_tokens }} 
                (输入: {{ analysis.token_usage.input_tokens }}, 
                输出: {{ analysis.token_usage.output_tokens }})
              </span>
              <span v-if="analysis.token_usage.audio_seconds > 0">
                | 音频: {{ analysis.token_usage.audio_seconds.toFixed(1) }}秒
              </span>
            </template>
            <span v-else class="text-gray-300">
              (旧数据，无消耗记录。重新分析可查看)
            </span>
          </div>
          <div class="flex items-center gap-2">
            <span><el-icon><Money /></el-icon> 查看API余额：</span>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Loading, VideoCamera, CircleClose, DataAnalysis, Mic, VideoPause, ChatLineSquare, Timer, Film, Star, Edit, MagicStick, Coin, Money } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'

interface Props {
  submissionId: number
  canTrigger?: boolean
  canReanalyze?: boolean
  autoRefresh?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  canTrigger: true,
  canReanalyze: false,
  autoRefresh: true,
})

const emit = defineEmits<{
  (e: 'analyzed', analysis: any): void
}>()

const loading = ref(false)
const triggering = ref(false)
const analysisData = ref<any>(null)
let refreshTimer: number | null = null

const analysis = computed(() => {
  if (analysisData.value?.status === 'completed') {
    return analysisData.value.analysis || analysisData.value
  }
  if (analysisData.value?.overall_score !== undefined) {
    return analysisData.value
  }
  return null
})

// 获取分析结果
async function fetchAnalysis() {
  if (!props.submissionId) return
  
  loading.value = true
  try {
    const result: any = await api.get(`/video-analysis/submissions/${props.submissionId}/video-analysis`)
    
    if (result.status === 'completed') {
      analysisData.value = result
      stopAutoRefresh()
      emit('analyzed', result.analysis)
    } else if (result.status === 'failed') {
      analysisData.value = result
      stopAutoRefresh()
    } else if (result.status === 'not_analyzed') {
      analysisData.value = result
      stopAutoRefresh()
    } else if (result.status === 'processing') {
      analysisData.value = result
      if (props.autoRefresh) {
        startAutoRefresh()
      }
    }
  } catch (error) {
    console.error('获取视频分析失败', error)
    analysisData.value = null
  } finally {
    loading.value = false
  }
}

// 触发分析
async function handleTriggerAnalysis() {
  triggering.value = true
  try {
    await api.post(`/video-analysis/submissions/${props.submissionId}/analyze-video`)
    ElMessage.success('视频分析已启动，请稍后刷新查看结果')
    analysisData.value = { status: 'processing' }
    if (props.autoRefresh) {
      startAutoRefresh()
    }
  } catch (error: any) {
    ElMessage.error(error.message || '启动分析失败')
  } finally {
    triggering.value = false
  }
}

// 重新分析
async function handleReanalyze() {
  triggering.value = true
  try {
    await api.post(`/video-analysis/submissions/${props.submissionId}/analyze-video`)
    ElMessage.success('视频重新分析已启动')
    analysisData.value = { status: 'processing' }
    if (props.autoRefresh) {
      startAutoRefresh()
    }
  } catch (error: any) {
    ElMessage.error(error.message || '重新分析失败')
  } finally {
    triggering.value = false
  }
}

// 自动刷新
function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = window.setInterval(() => {
    fetchAnalysis()
  }, 5000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 格式化时长
function formatDuration(seconds: number): string {
  if (!seconds) return '0分0秒'
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${minutes}分${secs}秒`
}

// 获取得分等级样式
function getScoreClass(score: number): string {
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'good'
  if (score >= 70) return 'fair'
  return 'poor'
}

// 获取进度条颜色
function getProgressColor(score: number): string {
  if (score >= 90) return '#67c23a'
  if (score >= 80) return '#409eff'
  if (score >= 70) return '#e6a23c'
  return '#f56c6c'
}

// 监听 submissionId 变化
watch(() => props.submissionId, (newId) => {
  if (newId) {
    stopAutoRefresh()
    analysisData.value = null
    fetchAnalysis()
  }
}, { immediate: false })

onMounted(() => {
  if (props.submissionId) {
    fetchAnalysis()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})

// 暴露方法供父组件调用
defineExpose({
  refresh: fetchAnalysis,
  triggerAnalysis: handleTriggerAnalysis,
})
</script>

<style scoped>
.video-analysis-card {
  padding: 16px;
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

.gesture-comment {
  font-size: 11px;
  color: #909399;
  margin-top: 6px;
  line-height: 1.4;
}

.highlights-section,
.improvements-section {
  padding: 10px;
  border-radius: 6px;
  background: #fafafa;
}

.token-usage-info {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px dashed #dcdfe6;
}
</style>
