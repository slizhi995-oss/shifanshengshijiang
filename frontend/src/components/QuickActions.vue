<script setup lang="ts">
/**
 * 快捷操作浮动按钮
 * 提供常用功能的快速入口
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { 
  Plus, Edit, Document, VideoCamera, 
  ChatDotRound, Bell, User, Setting,
  Upload, Search, TrendCharts
} from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const isExpanded = ref(false)

// 根据角色获取快捷操作
const actions = computed(() => {
  const role = authStore.userRole
  
  if (role === 'student') {
    return [
      { icon: Upload, label: '提交作业', path: '/student/tasks', color: 'bg-blue-500' },
      { icon: TrendCharts, label: '查看成绩', path: '/student/my-grades', color: 'bg-emerald-500' },
      { icon: ChatDotRound, label: 'AI 助手', path: '/student/ai-assistant', color: 'bg-teal-500' },
      { icon: User, label: '成长画像', path: '/student/my-profile', color: 'bg-amber-500' }
    ]
  }
  
  if (role === 'instructor') {
    return [
      { icon: Edit, label: '批改作业', path: '/instructor/reviews', color: 'bg-blue-500' },
      { icon: User, label: '学生画像', path: '/instructor/student-profiles', color: 'bg-emerald-500' },
      { icon: Setting, label: '评分规则', path: '/instructor/rubrics', color: 'bg-teal-500' },
      { icon: ChatDotRound, label: '联系学生', path: '/chat', color: 'bg-amber-500' }
    ]
  }
  
  if (role === 'admin') {
    return [
      { icon: User, label: '用户管理', path: '/admin/users/students', color: 'bg-blue-500' },
      { icon: TrendCharts, label: '数据大屏', path: '/admin/data-screen', color: 'bg-emerald-500' },
      { icon: Setting, label: 'AI 运营', path: '/admin/ai-ops', color: 'bg-teal-500' },
      { icon: Document, label: '数据导出', path: '/admin/export', color: 'bg-amber-500' }
    ]
  }
  
  return []
})

// 执行操作
const handleAction = (action: any) => {
  router.push(action.path)
  isExpanded.value = false
}

// 切换展开状态
const toggle = () => {
  isExpanded.value = !isExpanded.value
}

// 关闭菜单
const close = () => {
  isExpanded.value = false
}
</script>

<template>
  <div class="fab-container" v-if="actions.length > 0">
    <!-- 遮罩层 -->
    <Transition name="fade">
      <div v-if="isExpanded" class="fab-overlay" @click="close"></div>
    </Transition>

    <!-- 快捷操作列表 -->
    <Transition name="slide-up">
      <div v-if="isExpanded" class="fab-menu">
        <div 
          v-for="(action, index) in actions" 
          :key="index"
          class="fab-item"
          :style="{ transitionDelay: `${index * 50}ms` }"
          @click="handleAction(action)"
        >
          <span class="fab-label">{{ action.label }}</span>
          <div class="fab-icon-btn" :class="action.color">
            <el-icon size="20"><component :is="action.icon" /></el-icon>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 主按钮 -->
    <button 
      class="fab-main"
      :class="{ 'is-expanded': isExpanded }"
      @click="toggle"
    >
      <el-icon size="24" class="fab-main-icon">
        <Plus />
      </el-icon>
    </button>
  </div>
</template>

<style scoped>
.fab-container {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.fab-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: -1;
}

.fab-menu {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.fab-item {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  opacity: 0;
  transform: translateY(20px);
  animation: slideIn 0.3s ease forwards;
}

@keyframes slideIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fab-label {
  background: white;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  white-space: nowrap;
}

.fab-icon-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s;
}

.fab-icon-btn:hover {
  transform: scale(1.1);
}

.fab-main {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: #0891b2;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(8, 145, 178, 0.4);
  transition: all 0.3s ease;
}

.fab-main:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(8, 145, 178, 0.5);
}

.fab-main.is-expanded {
  background: #ef4444;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
}

.fab-main.is-expanded .fab-main-icon {
  transform: rotate(45deg);
}

.fab-main-icon {
  transition: transform 0.3s ease;
}

/* 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* 响应式 */
@media (max-width: 640px) {
  .fab-container {
    right: 16px;
    bottom: 16px;
  }
  
  .fab-main {
    width: 48px;
    height: 48px;
  }
  
  .fab-icon-btn {
    width: 40px;
    height: 40px;
  }
  
  .fab-label {
    font-size: 12px;
    padding: 6px 12px;
  }
}
</style>
