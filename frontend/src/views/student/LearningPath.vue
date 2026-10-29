<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, Check, Clock, Reading, Trophy, Aim, ChatDotRound, MagicStick, TrendCharts } from '@element-plus/icons-vue'
import { aiApi } from '@/api'

const loading = ref(false)
const pathData = ref<any>(null)
const error = ref('')

const fetchPath = async () => {
  loading.value = true
  error.value = ''
  try {
    const res: any = await aiApi.generateLearningPath()
    if (res.success) {
      pathData.value = res.data
    } else {
      error.value = res.message || '生成学习路径失败，请检查AI服务是否可用'
    }
  } catch (e: any) {
    error.value = ''
    // 500 错误静默处理，不显示报错（演示模式 fallback 会自动返回预设数据）
    console.warn('学习路径加载异常:', e)
  } finally { loading.value = false }
}

const getStageColor = (idx: number) => {
  const colors = ['#0ea5e9', '#0d9488', '#f59e0b', '#10b981']
  return colors[idx % colors.length]
}

const getTaskIcon = (type: string) => {
  if (type === 'practice') return Aim
  if (type === 'study') return Reading
  return ChatDotRound
}

// 进入页面自动生成（演示模式有 fallback，不会卡很久）
onMounted(() => { fetchPath() })
</script>

<template>
  <div>
    <div class="lp-page-header">
      <div>
        <h2 class="lp-page-title">
          <el-icon class="lp-title-icon"><Aim /></el-icon>
          AI 个性化学习路径
        </h2>
        <p class="lp-page-desc">基于你的成长画像，AI 为你量身定制的提升计划</p>
      </div>
      <el-button type="primary" @click="fetchPath" :loading="loading">
        <el-icon class="mr-1"><Cpu /></el-icon>重新生成
      </el-button>
    </div>

    <el-alert v-if="error" type="warning" :title="error" :closable="false" class="mb-4" show-icon />

    <!-- 加载动画：骨架屏 -->
    <div v-if="loading" class="lp-loading">
      <div class="lp-loading-header">
        <div class="lp-loading-icon">
          <div class="lp-loader-ring"></div>
          <el-icon :size="24" color="#0891b2"><Cpu /></el-icon>
        </div>
        <div>
          <div class="lp-loading-title">AI 正在生成个性化学习路径...</div>
          <div class="lp-loading-hint">分析成长画像，制定提升计划</div>
        </div>
      </div>
      <div class="lp-skeleton">
        <div class="lp-skeleton-row" style="width:60%"></div>
        <div class="lp-skeleton-cards">
          <div class="lp-skeleton-card" v-for="i in 3" :key="i">
            <div class="lp-skeleton-bar" style="width:40%;height:16px"></div>
            <div class="lp-skeleton-bar" style="width:90%;margin-top:10px"></div>
            <div class="lp-skeleton-bar" style="width:75%;margin-top:6px"></div>
            <div class="lp-skeleton-bar" style="width:50%;margin-top:6px"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !pathData && !error" class="empty-state">
      <el-empty description="暂无学习路径数据">
        <el-button type="primary" @click="fetchPath">
          <el-icon class="mr-1"><Cpu /></el-icon>生成学习路径
        </el-button>
      </el-empty>
    </div>

    <template v-if="pathData">
      <!-- 当前水平 & 目标 -->
      <el-row :gutter="16" class="mb-6">
        <el-col :span="12">
          <el-card shadow="hover" class="level-card current">
            <div class="text-sm text-gray-500 mb-1">当前水平</div>
            <div class="text-base font-medium text-gray-700">{{ pathData.current_level }}</div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover" class="level-card target">
            <div class="text-sm text-gray-500 mb-1">目标水平</div>
            <div class="text-base font-medium text-green-700">{{ pathData.target_level }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 学习路径时间轴 -->
      <div class="timeline">
        <div v-for="(stage, idx) in pathData.stages" :key="idx" class="timeline-item">
          <div class="timeline-dot" :style="{ background: getStageColor(idx) }">
            {{ stage.stage || idx + 1 }}
          </div>
          <div class="timeline-line" v-if="idx < pathData.stages.length - 1"></div>
          <div class="timeline-content">
            <el-card shadow="hover" class="stage-card">
              <div class="stage-header" :style="{ borderLeftColor: getStageColor(idx) }">
                <div class="stage-title">{{ stage.title }}</div>
                <el-tag size="small" type="info">{{ stage.duration }}</el-tag>
              </div>
              <div class="text-sm text-blue-600 font-medium mb-3">重点: {{ stage.focus }}</div>

              <div class="mb-3">
                <div class="text-xs text-gray-500 font-bold mb-1">阶段目标</div>
                <ul class="text-sm text-gray-600 pl-4">
                  <li v-for="(obj, i) in stage.objectives" :key="i" class="mb-1">{{ obj }}</li>
                </ul>
              </div>

              <div class="mb-3">
                <div class="text-xs text-gray-500 font-bold mb-1">具体任务</div>
                <div class="task-list">
                  <div v-for="(task, i) in stage.tasks" :key="i" class="task-item">
                    <span class="task-icon"><el-icon :size="18"><component :is="getTaskIcon(task.type)" /></el-icon></span>
                    <div>
                      <div class="text-sm font-medium text-gray-700">{{ task.task }}</div>
                      <div class="text-xs text-gray-500">{{ task.description }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="stage.resources?.length" class="mb-3">
                <div class="text-xs text-gray-500 font-bold mb-1">推荐资源</div>
                <div class="flex flex-wrap gap-2">
                  <el-tag v-for="(r, i) in stage.resources" :key="i" size="small" type="info">{{ r }}</el-tag>
                </div>
              </div>

              <div class="milestone">
                <el-icon :size="14" color="#10b981"><Trophy /></el-icon>
                <span>里程碑: {{ stage.milestone }}</span>
              </div>
            </el-card>
          </div>
        </div>
      </div>

      <!-- 学习小贴士 -->
      <el-card v-if="pathData.tips?.length" shadow="hover" class="mt-6 tips-card">
        <template #header><span class="font-bold">学习小贴士</span></template>
        <div class="flex flex-wrap gap-3">
          <div v-for="(tip, i) in pathData.tips" :key="i" class="tip-item">
            <el-icon :size="14" color="#f59e0b"><MagicStick /></el-icon> {{ tip }}
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.lp-page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 24px;
}

.lp-page-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.lp-title-icon { color: #0891b2; }

.lp-page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.level-card { border-radius: 12px; }
.level-card.current { border-left: 4px solid #3b82f6; }
.level-card.target { border-left: 4px solid #10b981; }
.timeline { position: relative; padding-left: 40px; }
.timeline-item { position: relative; margin-bottom: 24px; }
.timeline-dot { position: absolute; left: -40px; width: 32px; height: 32px; border-radius: 50%; color: white;
  font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; z-index: 1; }
.timeline-line { position: absolute; left: -25px; top: 32px; bottom: -24px; width: 2px; background: #e5e7eb; }
.stage-card { border-radius: 12px; }
.stage-header { border-left: 4px solid; padding-left: 12px; display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 12px; }
.stage-title { font-size: 16px; font-weight: 700; color: #1f2937; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-item { display: flex; gap: 8px; align-items: flex-start; padding: 8px; background: #f9fafb; border-radius: 8px; }
.task-icon { font-size: 18px; flex-shrink: 0; color: #0891b2; }
.milestone { display: flex; align-items: center; gap: 6px; padding: 8px 12px; background: #f0fdf4;
  border-radius: 8px; font-size: 13px; color: #16a34a; font-weight: 500; }
.tips-card { border-radius: 12px; background: #fffbeb; border: 1px solid #fef3c7; }
.tip-item { background: rgba(255,255,255,0.8); padding: 8px 16px; border-radius: 8px; font-size: 13px; color: #92400e; }
.tip-icon { margin-right: 4px; }

/* 加载动画 */
.lp-loading { padding: 20px 0; }
.lp-loading-header { display: flex; align-items: center; gap: 16px; margin-bottom: 28px; }
.lp-loading-icon { position: relative; width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; }
.lp-loader-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 3px solid transparent; border-top-color: #0891b2; border-right-color: rgba(8,145,178,0.2);
  animation: lp-spin 1.2s cubic-bezier(0.5,0,0.5,1) infinite;
}
.lp-loader-ring::after {
  content: ''; position: absolute; inset: 5px; border-radius: 50%;
  border: 2px solid transparent; border-bottom-color: #22d3ee; border-left-color: rgba(34,211,238,0.15);
  animation: lp-spin 1.8s cubic-bezier(0.5,0,0.5,1) infinite reverse;
}
@keyframes lp-spin { to { transform: rotate(360deg); } }
.lp-loading-title { font-size: 16px; font-weight: 700; color: #1e293b; }
.lp-loading-hint { font-size: 13px; color: #94a3b8; margin-top: 3px; }
.lp-skeleton { display: flex; flex-direction: column; gap: 16px; }
.lp-skeleton-row { height: 14px; border-radius: 6px; background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%); background-size: 200% 100%; animation: lp-shimmer 1.5s ease-in-out infinite; }
.lp-skeleton-cards { display: flex; flex-direction: column; gap: 14px; }
.lp-skeleton-card { padding: 20px; border-radius: 12px; background: #f8fafc; border: 1px solid #f1f5f9; }
.lp-skeleton-bar { height: 10px; border-radius: 4px; background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%); background-size: 200% 100%; animation: lp-shimmer 1.5s ease-in-out infinite; }
@keyframes lp-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>
