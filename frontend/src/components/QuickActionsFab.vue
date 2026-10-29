<script setup lang="ts">
/**
 * 快速操作浮动面板组件
 * 提供常用操作的快捷入口
 */
import { ref, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  HomeFilled, Document, VideoCamera, DataAnalysis,
  ChatDotRound, Bell, Setting, Plus, User, TrendCharts, Cpu
} from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()

const visible = ref(false)
const isExpanded = ref(false)

// 注入 Copilot 面板控制（由 MainLayout provide）
const toggleCopilot = inject<(() => void) | null>('toggleCopilot', null)

// 根据角色获取快速操作项
const quickActions = computed(() => {
  const role = authStore.user?.role

  if (role === 'student') {
    return [
      { icon: Cpu, label: 'AI 助手', action: 'copilot', color: '#0d9488', isAI: true },
      { icon: Plus, label: '提交作业', route: '/student/my-submissions', color: '#0891b2' },
      { icon: Document, label: 'AI 备课', route: '/student/ai-assistant', color: '#10b981' },
      { icon: TrendCharts, label: '成长画像', route: '/student/my-profile', color: '#f59e0b' },
      { icon: ChatDotRound, label: '联系老师', route: '/chat', color: '#ec4899' },
    ]
  }

  if (role === 'instructor') {
    return [
      { icon: Cpu, label: 'AI 助手', action: 'copilot', color: '#0d9488', isAI: true },
      { icon: Document, label: '作业批改', route: '/instructor/reviews', color: '#0891b2' },
      { icon: Plus, label: '发布任务', route: '/instructor/tasks', color: '#10b981' },
      { icon: User, label: '学生画像', route: '/instructor/student-profiles', color: '#f59e0b' },
      { icon: ChatDotRound, label: '学生消息', route: '/chat', color: '#ec4899' },
    ]
  }

  if (role === 'admin' || role === 'super_admin') {
    return [
      { icon: Cpu, label: 'AI 助手', action: 'copilot', color: '#0d9488', isAI: true },
      { icon: User, label: '用户管理', route: '/admin/users/students', color: '#0891b2' },
      { icon: DataAnalysis, label: 'AI 运营', route: '/admin/ai-ops', color: '#10b981' },
      { icon: TrendCharts, label: '数据大屏', route: '/admin/data-screen', color: '#f59e0b' },
      { icon: Setting, label: '系统设置', route: '/admin/settings', color: '#ec4899' },
    ]
  }

  return []
})

const handleAction = (action: any) => {
  if (action.action === 'copilot' && toggleCopilot) {
    toggleCopilot()
  } else if (action.route) {
    router.push(action.route)
  }
  isExpanded.value = false
}

const togglePanel = () => {
  isExpanded.value = !isExpanded.value
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fab">
      <div class="quick-action-fab" v-show="quickActions.length > 0">
        <!-- 展开后的操作项 -->
        <Transition name="actions">
          <div v-show="isExpanded" class="action-list">
            <div
              v-for="(action, index) in quickActions"
              :key="action.label"
              class="action-item"
              :style="{ '--delay': `${(quickActions.length - index - 1) * 0.05}s` }"
              @click="handleAction(action)"
            >
              <div class="action-btn" :style="{ '--accent': action.color }">
                <el-icon :size="18"><component :is="action.icon" /></el-icon>
                <span class="action-text">{{ action.label }}</span>
              </div>
            </div>
          </div>
        </Transition>

        <!-- FAB 主按钮 -->
        <div 
          class="fab-trigger"
          :class="{ active: isExpanded }"
          @click="togglePanel"
          :title="isExpanded ? '收起' : '快捷操作'"
        >
          <el-icon class="trigger-icon"><Plus /></el-icon>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.quick-action-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

/* FAB 触发按钮 */
.fab-trigger {
  width: 50px;
  height: 50px;
  border-radius: 16px;
  background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
  box-shadow: 0 8px 24px -4px rgba(79, 70, 229, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.fab-trigger:hover {
  transform: translateY(-2px) scale(1.04);
  box-shadow: 0 12px 28px -4px rgba(79, 70, 229, 0.55);
  filter: brightness(1.08);
}

.fab-trigger.active {
  border-radius: 16px;
  background: #0f172a;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
}

.fab-trigger.active .trigger-icon {
  transform: rotate(45deg);
}

.trigger-icon {
  font-size: 22px;
  color: #fff;
  transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 操作列表 */
.action-list {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 8px;
  min-width: 145px;
}

.action-item {
  cursor: pointer;
  animation: slideIn 0.25s ease-out var(--delay) backwards;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.1);
  color: var(--accent, #334155);
  transition: all 0.22s ease;
  white-space: nowrap;
  font-weight: 600;
  font-size: 13px;
}

.action-btn:hover {
  background: #ffffff;
  border-color: var(--accent, #94a3b8);
  box-shadow: 0 8px 20px -2px rgba(15, 23, 42, 0.16);
  transform: translateX(-3px);
}

.action-text {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

/* 过渡动画 */
.fab-enter-active,
.fab-leave-active {
  transition: all 0.3s ease;
}

.fab-enter-from,
.fab-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

.actions-enter-active,
.actions-leave-active {
  transition: all 0.25s ease;
}

.actions-enter-from,
.actions-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

/* 响应式 */
@media (max-width: 768px) {
  .quick-action-fab {
    right: 16px;
    bottom: 16px;
  }

  .fab-trigger {
    width: 44px;
    height: 44px;
    border-radius: 12px;
  }

  .trigger-icon {
    font-size: 20px;
  }

  .action-btn {
    padding: 6px 12px;
    font-size: 12px;
  }
}
</style>
