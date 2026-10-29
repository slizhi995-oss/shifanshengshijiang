<script setup lang="ts">
/**
 * 作业统计卡片组件
 * 展示学生或教师的作业统计概览
 */
import { computed } from 'vue'
import { 
  Document, Check, Clock, Close, TrendCharts, 
  ArrowUp, ArrowDown, Timer
} from '@element-plus/icons-vue'

interface Stats {
  total: number
  submitted: number
  pending: number
  approved: number
  rejected: number
  avgScore?: number
  avgScoreTrend?: number
  onTimeRate?: number
}

const props = withDefaults(defineProps<{
  stats: Stats
  role?: 'student' | 'instructor'
  loading?: boolean
}>(), {
  role: 'student',
  loading: false
})

const cards = computed(() => {
  const isStudent = props.role === 'student'
  const s = props.stats
  
  return [
    {
      icon: Document,
      label: isStudent ? '待完成' : '待批改',
      value: s.pending,
      color: 'amber',
      highlight: s.pending > 0
    },
    {
      icon: Check,
      label: '已通过',
      value: s.approved,
      color: 'green'
    },
    {
      icon: Close,
      label: '已驳回',
      value: s.rejected,
      color: 'red',
      highlight: s.rejected > 0
    },
    {
      icon: TrendCharts,
      label: '平均分',
      value: s.avgScore?.toFixed(1) || '-',
      color: 'indigo',
      trend: s.avgScoreTrend
    }
  ]
})

// 完成率
const completionRate = computed(() => {
  if (!props.stats.total) return 0
  return Math.round((props.stats.approved / props.stats.total) * 100)
})

// 按时提交率
const onTimeRateFormatted = computed(() => {
  return props.stats.onTimeRate !== undefined 
    ? `${Math.round(props.stats.onTimeRate * 100)}%` 
    : null
})
</script>

<template>
  <div class="stats-cards" v-loading="loading">
    <div 
      v-for="card in cards" 
      :key="card.label"
      class="stat-card"
      :class="[`color-${card.color}`, { highlight: card.highlight }]"
    >
      <div class="card-icon">
        <el-icon><component :is="card.icon" /></el-icon>
      </div>
      <div class="card-content">
        <div class="card-value">
          {{ card.value }}
          <span v-if="card.trend" class="trend" :class="card.trend > 0 ? 'up' : 'down'">
            <el-icon size="12">
              <ArrowUp v-if="card.trend > 0" />
              <ArrowDown v-else />
            </el-icon>
            {{ Math.abs(card.trend).toFixed(1) }}
          </span>
        </div>
        <div class="card-label">{{ card.label }}</div>
      </div>
    </div>
    
    <!-- 完成率进度 -->
    <div class="stat-card color-purple progress-card">
      <div class="card-content">
        <div class="flex items-center justify-between mb-2">
          <span class="card-label">完成率</span>
          <span class="card-value text-lg">{{ completionRate }}%</span>
        </div>
        <el-progress 
          :percentage="completionRate" 
          :stroke-width="8"
          :show-text="false"
          :color="completionRate >= 80 ? '#10b981' : completionRate >= 50 ? '#f59e0b' : '#ef4444'"
        />
        <div v-if="onTimeRateFormatted" class="flex items-center gap-1 mt-2 text-xs text-gray-500">
          <el-icon><Timer /></el-icon>
          按时率 {{ onTimeRateFormatted }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: white;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.stat-card.highlight {
  animation: pulse-highlight 2s infinite;
}

@keyframes pulse-highlight {
  0%, 100% { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06); }
  50% { box-shadow: 0 0 20px var(--highlight-color, rgba(245, 158, 11, 0.4)); }
}

/* 颜色变体 */
.stat-card.color-amber {
  --highlight-color: rgba(245, 158, 11, 0.4);
}
.stat-card.color-amber .card-icon {
  background: #fef3c7;
  color: #d97706;
}

.stat-card.color-green .card-icon {
  background: #d1fae5;
  color: #059669;
}

.stat-card.color-red {
  --highlight-color: rgba(239, 68, 68, 0.3);
}
.stat-card.color-red .card-icon {
  background: #fee2e2;
  color: #dc2626;
}

.stat-card.color-indigo .card-icon {
  background: #cffafe;
  color: #0891b2;
}

.stat-card.color-purple {
  background: #f0fdfa;
  border-color: #ccfbf1;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.card-content {
  flex: 1;
}

.card-value {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.trend {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.trend.up {
  color: #10b981;
  background: #d1fae5;
}

.trend.down {
  color: #ef4444;
  background: #fee2e2;
}

.progress-card {
  padding: 16px 20px;
}

.progress-card .card-content {
  width: 100%;
}

@media (max-width: 640px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stat-card {
    padding: 14px 16px;
  }
  
  .card-icon {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }
  
  .card-value {
    font-size: 22px;
  }
}
</style>
</script>
