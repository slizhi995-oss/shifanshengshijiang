<script setup lang="ts">
/**
 * 成就徽章组件
 * 展示学生获得的成就和徽章
 */
import { computed } from 'vue'
import { Trophy, Star, Medal, Timer, Lightning, TrendCharts } from '@element-plus/icons-vue'

interface Badge {
  id: string
  name: string
  description: string
  icon: string
  color: string
  earned: boolean
  earnedAt?: string
  progress?: number
}

const props = withDefaults(defineProps<{
  badges: Badge[]
  showProgress?: boolean
  compact?: boolean
}>(), {
  showProgress: true,
  compact: false
})

const emit = defineEmits<{
  (e: 'click', badge: Badge): void
}>()

// 图标映射
const iconMap: Record<string, any> = {
  trophy: Trophy,
  star: Star,
  medal: Medal,
  timer: Timer,
  lightning: Lightning,
  trend: TrendCharts
}

// 颜色映射
const colorMap: Record<string, { bg: string; text: string; glow: string }> = {
  gold: { bg: '#f59e0b', text: '#78350f', glow: 'rgba(245, 158, 11, 0.3)' },
  silver: { bg: '#9ca3af', text: '#374151', glow: 'rgba(107, 114, 128, 0.25)' },
  bronze: { bg: '#ea580c', text: '#7c2d12', glow: 'rgba(234, 88, 12, 0.25)' },
  blue: { bg: '#3b82f6', text: '#1e3a8a', glow: 'rgba(59, 130, 246, 0.3)' },
  green: { bg: '#22c55e', text: '#14532d', glow: 'rgba(34, 197, 94, 0.3)' },
  purple: { bg: '#14b8a6', text: '#134e4a', glow: 'rgba(20, 184, 166, 0.3)' }
}

// 已获得徽章
const earnedBadges = computed(() => props.badges.filter(b => b.earned))

// 未获得徽章
const lockedBadges = computed(() => props.badges.filter(b => !b.earned))

// 获取颜色样式
const getColors = (color: string) => colorMap[color] || colorMap.blue

// 格式化日期
const formatDate = (date?: string) => {
  if (!date) return ''
  return new Date(date).toLocaleDateString('zh-CN')
}
</script>

<template>
  <div class="badges-container" :class="{ compact }">
    <!-- 已获得徽章 -->
    <div v-if="earnedBadges.length" class="badges-section">
      <h4 v-if="!compact" class="section-title">
        <el-icon><Trophy /></el-icon>
        已获得成就
        <el-tag type="success" size="small" effect="plain">{{ earnedBadges.length }}</el-tag>
      </h4>
      
      <div class="badges-grid">
        <div 
          v-for="badge in earnedBadges" 
          :key="badge.id"
          class="badge-item earned"
          :style="{ '--glow': getColors(badge.color).glow }"
          @click="emit('click', badge)"
        >
          <div 
            class="badge-icon"
            :style="{ background: getColors(badge.color).bg }"
          >
            <el-icon :style="{ color: getColors(badge.color).text }">
              <component :is="iconMap[badge.icon] || Star" />
            </el-icon>
          </div>
          <div class="badge-info">
            <span class="badge-name">{{ badge.name }}</span>
            <span v-if="!compact" class="badge-desc">{{ badge.description }}</span>
            <span v-if="badge.earnedAt" class="badge-date">
              {{ formatDate(badge.earnedAt) }} 获得
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 未获得徽章 -->
    <div v-if="lockedBadges.length && showProgress" class="badges-section locked-section">
      <h4 v-if="!compact" class="section-title text-gray-500">
        <el-icon><Star /></el-icon>
        待解锁成就
      </h4>
      
      <div class="badges-grid">
        <div 
          v-for="badge in lockedBadges" 
          :key="badge.id"
          class="badge-item locked"
          @click="emit('click', badge)"
        >
          <div class="badge-icon">
            <el-icon><component :is="iconMap[badge.icon] || Star" /></el-icon>
          </div>
          <div class="badge-info">
            <span class="badge-name">{{ badge.name }}</span>
            <span v-if="!compact" class="badge-desc">{{ badge.description }}</span>
            <div v-if="badge.progress !== undefined" class="badge-progress">
              <el-progress 
                :percentage="badge.progress" 
                :stroke-width="4"
                :show-text="false"
              />
              <span class="progress-text">{{ badge.progress }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 空状态 -->
    <div v-if="!badges.length" class="empty-state">
      <el-empty description="暂无成就徽章" :image-size="60" />
    </div>
  </div>
</template>

<style scoped>
.badges-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.badges-container.compact {
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin: 0 0 16px;
}

.compact .section-title {
  display: none;
}

.badges-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.compact .badges-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* 徽章项 */
.badge-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  background: white;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.compact .badge-item {
  flex-direction: column;
  align-items: center;
  padding: 12px;
  min-width: 80px;
  text-align: center;
}

.badge-item.earned {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.badge-item.earned:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px var(--glow, rgba(0, 0, 0, 0.15));
}

.badge-item.locked {
  background: #f8fafc;
  opacity: 0.7;
}

.badge-item.locked:hover {
  opacity: 1;
  background: #f1f5f9;
}

/* 徽章图标 */
.badge-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.compact .badge-icon {
  width: 44px;
  height: 44px;
  font-size: 20px;
}

.badge-item.locked .badge-icon {
  background: #e2e8f0;
  color: #94a3b8;
}

.badge-item.earned .badge-icon {
  animation: shine 3s ease-in-out infinite;
}

@keyframes shine {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.1); }
}

/* 徽章信息 */
.badge-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.badge-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 14px;
}

.badge-item.locked .badge-name {
  color: #64748b;
}

.badge-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}

.compact .badge-desc {
  display: none;
}

.badge-date {
  font-size: 11px;
  color: #94a3b8;
}

.compact .badge-date {
  display: none;
}

/* 进度 */
.badge-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.badge-progress .el-progress {
  flex: 1;
}

.progress-text {
  font-size: 11px;
  color: #94a3b8;
  min-width: 32px;
}

/* 未获得区域 */
.locked-section {
  padding-top: 24px;
  border-top: 1px dashed #e2e8f0;
}

.compact .locked-section {
  padding-top: 12px;
}

.empty-state {
  padding: 32px;
  text-align: center;
}

@media (max-width: 640px) {
  .badges-grid {
    grid-template-columns: 1fr;
  }
}
</style>
</script>
