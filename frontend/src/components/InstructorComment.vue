<script setup lang="ts">
/**
 * 导师评语卡片组件
 * 展示导师对学生的评价和建议
 */
import { computed } from 'vue'
import { 
  User, Star, StarFilled, TrendCharts, 
  ChatLineRound, Medal, Trophy
} from '@element-plus/icons-vue'

const props = defineProps<{
  instructor: {
    name: string
    title?: string
    avatar?: string
  }
  comment: string
  rating?: number  // 1-5星评分
  tags?: string[]  // 标签
  date?: string
  highlights?: string[]  // 亮点
  suggestions?: string[] // 建议
}>()

// 默认头像
const avatarUrl = computed(() => {
  if (props.instructor.avatar) return props.instructor.avatar
  const name = props.instructor.name || 'T'
  return `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(name)}&backgroundColor=6366f1`
})

// 星星数组
const stars = computed(() => {
  const rating = props.rating || 0
  return Array(5).fill(0).map((_, i) => i < rating)
})

// 格式化日期
const formatDate = (dateStr?: string) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN', { 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  })
}
</script>

<template>
  <div class="instructor-comment-card">
    <!-- 导师信息 -->
    <div class="instructor-header">
      <div class="instructor-info">
        <el-avatar :size="56" :src="avatarUrl" class="instructor-avatar" />
        <div class="instructor-details">
          <h4 class="instructor-name">
            {{ instructor.name }}
            <span v-if="instructor.title" class="instructor-title">{{ instructor.title }}</span>
          </h4>
          <div v-if="rating" class="rating-stars">
            <el-icon 
              v-for="(filled, index) in stars" 
              :key="index"
              :class="filled ? 'text-amber-400' : 'text-gray-300'"
            >
              <StarFilled v-if="filled" />
              <Star v-else />
            </el-icon>
            <span class="rating-text">{{ rating }}.0</span>
          </div>
        </div>
      </div>
      <div v-if="date" class="comment-date">
        {{ formatDate(date) }}
      </div>
    </div>

    <!-- 主要评语 -->
    <div class="comment-content">
      <el-icon class="quote-icon"><ChatLineRound /></el-icon>
      <p class="comment-text">{{ comment }}</p>
    </div>

    <!-- 标签 -->
    <div v-if="tags && tags.length > 0" class="comment-tags">
      <el-tag 
        v-for="tag in tags" 
        :key="tag" 
        size="small" 
        effect="plain"
        class="tag-item"
      >
        {{ tag }}
      </el-tag>
    </div>

    <!-- 亮点和建议 -->
    <div v-if="(highlights && highlights.length) || (suggestions && suggestions.length)" class="feedback-section">
      <!-- 亮点 -->
      <div v-if="highlights && highlights.length > 0" class="feedback-block highlights">
        <div class="feedback-title">
          <el-icon class="text-emerald-500"><Trophy /></el-icon>
          <span>表现亮点</span>
        </div>
        <ul class="feedback-list">
          <li v-for="(item, index) in highlights" :key="index">{{ item }}</li>
        </ul>
      </div>

      <!-- 建议 -->
      <div v-if="suggestions && suggestions.length > 0" class="feedback-block suggestions">
        <div class="feedback-title">
          <el-icon class="text-blue-500"><TrendCharts /></el-icon>
          <span>改进建议</span>
        </div>
        <ul class="feedback-list">
          <li v-for="(item, index) in suggestions" :key="index">{{ item }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.instructor-comment-card {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

.instructor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.instructor-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.instructor-avatar {
  border: 3px solid #cffafe;
}

.instructor-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.instructor-name {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.instructor-title {
  font-size: 0.75rem;
  font-weight: 400;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
}

.rating-stars {
  display: flex;
  align-items: center;
  gap: 2px;
}

.rating-text {
  font-size: 0.75rem;
  color: #6b7280;
  margin-left: 0.5rem;
}

.comment-date {
  font-size: 0.75rem;
  color: #9ca3af;
}

.comment-content {
  position: relative;
  padding: 1rem 1.25rem;
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  border-radius: 0.75rem;
  margin-bottom: 1rem;
}

.quote-icon {
  position: absolute;
  top: -8px;
  left: 12px;
  font-size: 1.5rem;
  color: #2dd4bf;
  background: white;
  padding: 4px;
  border-radius: 50%;
}

.comment-text {
  font-size: 0.9375rem;
  line-height: 1.75;
  color: #374151;
  margin: 0;
}

.comment-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.tag-item {
  border-radius: 9999px;
}

.feedback-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}

@media (max-width: 640px) {
  .feedback-section {
    grid-template-columns: 1fr;
  }
}

.feedback-block {
  padding: 0.75rem;
  border-radius: 0.5rem;
}

.feedback-block.highlights {
  background: #ecfdf5;
}

.feedback-block.suggestions {
  background: #eff6ff;
}

.feedback-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.5rem;
}

.feedback-list {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.8125rem;
  color: #4b5563;
  line-height: 1.6;
}

.feedback-list li {
  margin-bottom: 0.25rem;
}

.feedback-list li:last-child {
  margin-bottom: 0;
}
</style>
