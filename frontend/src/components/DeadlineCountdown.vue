<script setup lang="ts">
/**
 * 任务截止日期倒计时组件
 * 显示任务距离截止还有多少时间
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Clock, Warning, CircleCheck, Timer } from '@element-plus/icons-vue'

const props = defineProps<{
  deadline: string | Date
  showLabel?: boolean
  compact?: boolean
}>()

const now = ref(new Date())
let interval: number | null = null

// 计算截止时间
const deadlineDate = computed(() => {
  return props.deadline instanceof Date 
    ? props.deadline 
    : new Date(props.deadline)
})

// 计算剩余时间
const remaining = computed(() => {
  const diff = deadlineDate.value.getTime() - now.value.getTime()
  
  if (diff <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, expired: true }
  }
  
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((diff % (1000 * 60)) / 1000)
  
  return { days, hours, minutes, seconds, expired: false }
})

// 状态判断
const status = computed(() => {
  if (remaining.value.expired) return 'expired'
  if (remaining.value.days < 1) return 'urgent'
  if (remaining.value.days < 3) return 'warning'
  return 'normal'
})

// 格式化显示
const displayText = computed(() => {
  const r = remaining.value
  
  if (r.expired) return '已截止'
  if (r.days > 0) return `${r.days}天${r.hours}小时`
  if (r.hours > 0) return `${r.hours}小时${r.minutes}分钟`
  return `${r.minutes}分${r.seconds}秒`
})

const statusClass = computed(() => {
  return {
    expired: status.value === 'expired',
    urgent: status.value === 'urgent',
    warning: status.value === 'warning',
    normal: status.value === 'normal',
    compact: props.compact
  }
})

onMounted(() => {
  interval = setInterval(() => {
    now.value = new Date()
  }, 1000) as unknown as number
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <div class="countdown" :class="statusClass">
    <template v-if="!compact">
      <el-icon class="countdown-icon">
        <CircleCheck v-if="status === 'expired'" />
        <Warning v-else-if="status === 'urgent'" />
        <Timer v-else-if="status === 'warning'" />
        <Clock v-else />
      </el-icon>
    </template>
    
    <span v-if="showLabel" class="countdown-label">
      {{ status === 'expired' ? '' : '剩余' }}
    </span>
    
    <span class="countdown-value">{{ displayText }}</span>
    
    <!-- 详细时间块（非紧凑模式） -->
    <template v-if="!compact && !remaining.expired && remaining.days < 1">
      <div class="countdown-detail">
        <div class="time-block">
          <span class="time-value">{{ String(remaining.hours).padStart(2, '0') }}</span>
          <span class="time-label">时</span>
        </div>
        <span class="time-sep">:</span>
        <div class="time-block">
          <span class="time-value">{{ String(remaining.minutes).padStart(2, '0') }}</span>
          <span class="time-label">分</span>
        </div>
        <span class="time-sep">:</span>
        <div class="time-block">
          <span class="time-value">{{ String(remaining.seconds).padStart(2, '0') }}</span>
          <span class="time-label">秒</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.countdown {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
}

.countdown.compact {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 4px;
}

/* 正常状态 */
.countdown.normal {
  background: #e0f2fe;
  color: #0369a1;
}

.countdown.normal .countdown-icon {
  color: #0ea5e9;
}

/* 警告状态 (3天内) */
.countdown.warning {
  background: #fef3c7;
  color: #b45309;
}

.countdown.warning .countdown-icon {
  color: #f59e0b;
}

/* 紧急状态 (24小时内) */
.countdown.urgent {
  background: #fee2e2;
  color: #b91c1c;
  animation: pulse 2s infinite;
}

.countdown.urgent .countdown-icon {
  color: #ef4444;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

/* 已截止 */
.countdown.expired {
  background: #f3f4f6;
  color: #6b7280;
}

.countdown.expired .countdown-icon {
  color: #9ca3af;
}

.countdown-icon {
  font-size: 16px;
}

.countdown.compact .countdown-icon {
  font-size: 14px;
}

.countdown-label {
  font-size: 12px;
  opacity: 0.8;
}

.countdown-value {
  font-weight: 600;
}

/* 详细时间块 */
.countdown-detail {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
  padding-left: 8px;
  border-left: 1px solid currentColor;
  opacity: 0.3;
}

.time-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 28px;
}

.time-value {
  font-size: 16px;
  font-weight: 700;
  font-family: 'Roboto Mono', monospace;
  line-height: 1;
}

.time-label {
  font-size: 10px;
  opacity: 0.7;
}

.time-sep {
  font-size: 16px;
  font-weight: 700;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
</script>
