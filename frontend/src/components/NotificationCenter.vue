<script setup lang="ts">
/**
 * 通知中心组件
 * 支持已读/未读、批量操作、分类筛选
 */
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/request'
import { 
  Bell, Check, Delete, Refresh, Filter,
  Message, Warning, InfoFilled, CircleCheck
} from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits(['update:visible', 'unread-count-change'])

const loading = ref(false)
const notifications = ref<any[]>([])
const selectedIds = ref<number[]>([])
const filterType = ref('')
const showUnreadOnly = ref(false)

// 通知类型
const notificationTypes = [
  { value: '', label: '全部' },
  { value: 'system', label: '系统通知' },
  { value: 'task', label: '作业提醒' },
  { value: 'grade', label: '成绩通知' },
  { value: 'message', label: '消息提醒' }
]

// 获取通知列表
const fetchNotifications = async () => {
  loading.value = true
  try {
    const res: any = await api.get('/notifications', {
      params: { 
        page: 1, 
        page_size: 50,
        type: filterType.value || undefined,
        unread_only: showUnreadOnly.value || undefined
      }
    })
    notifications.value = res.items || res || []
    updateUnreadCount()
  } catch (error) {
    // 模拟数据
    notifications.value = [
      { id: 1, type: 'system', title: '系统更新通知', content: '系统已升级到最新版本', is_read: false, created_at: new Date().toISOString() },
      { id: 2, type: 'task', title: '作业即将截止', content: '「教学设计」作业将于明天截止', is_read: false, created_at: new Date().toISOString() },
      { id: 3, type: 'grade', title: '成绩已发布', content: '您的「试讲视频」作业已批改完成', is_read: true, created_at: new Date().toISOString() }
    ]
    updateUnreadCount()
  } finally {
    loading.value = false
  }
}

// 过滤后的通知
const filteredNotifications = computed(() => {
  let result = notifications.value
  if (filterType.value) {
    result = result.filter(n => n.type === filterType.value)
  }
  if (showUnreadOnly.value) {
    result = result.filter(n => !n.is_read)
  }
  return result
})

// 未读数量
const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.is_read).length
})

// 更新未读数量
const updateUnreadCount = () => {
  emit('unread-count-change', unreadCount.value)
}

// 标记已读
const markAsRead = async (notification: any) => {
  if (notification.is_read) return
  
  try {
    await api.put(`/notifications/${notification.id}/read`)
    notification.is_read = true
    updateUnreadCount()
  } catch (error) {
    notification.is_read = true
    updateUnreadCount()
  }
}

// 批量标记已读
const markSelectedAsRead = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请选择通知')
    return
  }
  
  try {
    await api.put('/notifications/batch-read', { ids: selectedIds.value })
    notifications.value.forEach(n => {
      if (selectedIds.value.includes(n.id)) {
        n.is_read = true
      }
    })
    selectedIds.value = []
    updateUnreadCount()
    ElMessage.success('已标记为已读')
  } catch (error) {
    notifications.value.forEach(n => {
      if (selectedIds.value.includes(n.id)) {
        n.is_read = true
      }
    })
    selectedIds.value = []
    updateUnreadCount()
  }
}

// 全部已读
const markAllAsRead = async () => {
  try {
    await api.put('/notifications/read-all')
    notifications.value.forEach(n => n.is_read = true)
    updateUnreadCount()
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    notifications.value.forEach(n => n.is_read = true)
    updateUnreadCount()
  }
}

// 删除通知
const deleteNotification = async (notification: any) => {
  await ElMessageBox.confirm('确定删除这条通知吗？', '确认删除', { type: 'warning' })
  
  try {
    await api.delete(`/notifications/${notification.id}`)
    notifications.value = notifications.value.filter(n => n.id !== notification.id)
    ElMessage.success('已删除')
  } catch (error) {
    notifications.value = notifications.value.filter(n => n.id !== notification.id)
  }
}

// 获取类型图标
const getTypeIcon = (type: string) => {
  const icons: Record<string, any> = {
    'system': InfoFilled,
    'task': Warning,
    'grade': CircleCheck,
    'message': Message
  }
  return icons[type] || Bell
}

// 获取类型颜色
const getTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    'system': 'text-blue-500',
    'task': 'text-amber-500',
    'grade': 'text-emerald-500',
    'message': 'text-teal-500'
  }
  return colors[type] || 'text-gray-500'
}

// 格式化时间
const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  
  return date.toLocaleDateString()
}

// 关闭抽屉
const close = () => {
  emit('update:visible', false)
}

onMounted(fetchNotifications)
</script>

<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title=""
    direction="rtl"
    size="400px"
    class="notification-drawer"
  >
    <template #header>
      <div class="drawer-header">
        <div class="flex items-center gap-2">
          <el-icon class="text-cyan-600 text-xl"><Bell /></el-icon>
          <span class="text-lg font-bold text-gray-800">通知中心</span>
          <el-badge v-if="unreadCount > 0" :value="unreadCount" class="ml-2" />
        </div>
        <div class="header-actions">
          <el-button text :icon="Check" @click="markAllAsRead" :disabled="unreadCount === 0">
            全部已读
          </el-button>
          <el-button text :icon="Refresh" @click="fetchNotifications" :loading="loading" />
        </div>
      </div>
    </template>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterType" placeholder="类型筛选" size="small" class="w-28">
        <el-option 
          v-for="t in notificationTypes" 
          :key="t.value" 
          :label="t.label" 
          :value="t.value" 
        />
      </el-select>
      <el-checkbox v-model="showUnreadOnly" size="small">仅未读</el-checkbox>
      <el-button 
        v-if="selectedIds.length > 0"
        size="small" 
        type="primary" 
        :icon="Check"
        @click="markSelectedAsRead"
      >
        标记已读 ({{ selectedIds.length }})
      </el-button>
    </div>

    <!-- 通知列表 -->
    <div v-loading="loading" class="notification-list">
      <el-empty v-if="filteredNotifications.length === 0" description="暂无通知" />
      
      <el-checkbox-group v-model="selectedIds" v-else>
        <div 
          v-for="notification in filteredNotifications" 
          :key="notification.id"
          class="notification-item"
          :class="{ 'unread': !notification.is_read }"
          @click="markAsRead(notification)"
        >
          <el-checkbox :value="notification.id" @click.stop class="mr-2" />
          
          <div class="notification-icon" :class="getTypeColor(notification.type)">
            <el-icon><component :is="getTypeIcon(notification.type)" /></el-icon>
          </div>
          
          <div class="notification-content">
            <div class="notification-title">
              {{ notification.title }}
              <span v-if="!notification.is_read" class="unread-dot"></span>
            </div>
            <p class="notification-text">{{ notification.content }}</p>
            <span class="notification-time">{{ formatTime(notification.created_at) }}</span>
          </div>
          
          <el-button 
            text 
            type="danger" 
            :icon="Delete" 
            size="small"
            @click.stop="deleteNotification(notification)"
          />
        </div>
      </el-checkbox-group>
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 200px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  background: white;
  border-radius: 0.5rem;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s;
}

.notification-item:hover {
  border-color: #c7d2fe;
  background: #f0fdfa;
}

.notification-item.unread {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.notification-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

.notification-text {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.notification-time {
  font-size: 0.625rem;
  color: #9ca3af;
  margin-top: 0.25rem;
  display: block;
}
</style>
