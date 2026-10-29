<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, provide } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter, useRoute } from 'vue-router'
import api from '@/utils/request'
import { videoDate } from '@/api/trialVideos'
import QuickActionsFab from '@/components/QuickActionsFab.vue'
import GlobalAICopilot from '@/components/GlobalAICopilot.vue'
import {
  Menu as IconMenu,
  User,
  UserFilled,
  Files,
  Setting,
  Monitor,
  DataLine,
  ChatDotRound,
  Fold,
  Expand,
  SwitchButton,
  Bell,
  Notification,
  Paperclip,
  Tools,
  TrendCharts,
  MagicStick,
  Cpu,
  Lock,
  ArrowRight,
  Download,
  Calendar,
  QuestionFilled,
  Document,
  VideoCamera,
  Warning,
  Key
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const isCollapse = ref(false)
const isMobile = ref(false)

// 系统设置 — 网站名称（sidebar 展示用短名，后端若返回则覆盖）
const siteName = ref('智教领航')
const fetchSiteSettings = async () => {
  try {
    const res: any = await api.get('/system/public-settings')
    if (res?.site_name) siteName.value = res.site_name
  } catch {
    // 静默失败，保持默认名称
  }
}

// AI Copilot 面板控制
const copilotRef = ref<InstanceType<typeof GlobalAICopilot> | null>(null)
provide('toggleCopilot', () => copilotRef.value?.togglePanel())

// AI 服务状态
const aiOnline = ref<boolean | null>(null)
const checkAIStatus = async () => {
  try {
    const res: any = await api.get('/ai/status')
    aiOnline.value = res?.enabled ?? false
  } catch {
    aiOnline.value = false
  }
}
let aiStatusTimer: any = null

// 未读聊天消息数
const chatUnreadCount = ref(0)

const checkMobile = () => {
  const mobile = window.innerWidth < 768
  if (mobile !== isMobile.value) {
    isMobile.value = mobile
    // 切换模式时，如果是移动端则默认收起，桌面端默认展开
    isCollapse.value = mobile
  }
}

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

const closeSidebar = () => {
  if (isMobile.value) {
    isCollapse.value = true
  }
}

const sidebarWidth = computed(() => {
  if (isMobile.value) return '240px'
  return isCollapse.value ? '64px' : '240px'
})

const sidebarClass = computed(() => {
  const base = 'bg-slate-900 text-slate-300 transition-all duration-300 flex flex-col h-full border-r border-slate-800 shadow-2xl relative z-30'
  if (isMobile.value) {
    return `${base} fixed top-0 left-0 z-50 shadow-2xl ${isCollapse.value ? '-translate-x-full' : 'translate-x-0'}`
  }
  return base
})

const handleLogout = () => {
  ElMessageBox.confirm(
    '确定要退出登录吗？',
    '退出确认',
    {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(() => {
    authStore.logout()
  }).catch(() => {
    // 用户取消退出
  })
}

// 跳转到修改密码页面
const goToChangePassword = () => {
  router.push('/change-password')
}

// 处理用户下拉菜单命令
const handleUserCommand = (command: string) => {
  switch (command) {
    case 'change-password':
      goToChangePassword()
      break
    case 'help':
      router.push('/help')
      break
    case 'logout':
      handleLogout()
      break
  }
}

const handleMenuSelect = (index: string) => {
  router.push(index)
  if (isMobile.value) {
    closeSidebar()
  }
}

const activeMenu = computed(() => route.path)

// 获取未读聊天消息数
const fetchChatUnreadCount = async () => {
  try {
    const res: any = await api.get('/chat/contacts')
    
    // 按user_id去重，同一个联系人只统计一次未读数
    const unreadMap = new Map<number, number>()
    res.forEach((contact: any) => {
      const userId = contact.user_id
      const count = contact.unread_count || 0
      // 如果已存在，取最大值（避免重复计算）
      if (unreadMap.has(userId)) {
        unreadMap.set(userId, Math.max(unreadMap.get(userId)!, count))
      } else {
        unreadMap.set(userId, count)
      }
    })
    
    // 累加所有联系人的未读数
    chatUnreadCount.value = Array.from(unreadMap.values()).reduce((sum, count) => sum + count, 0)
  } catch (error) {
    // 静默失败
  }
}

// 定时刷新未读聊天消息数
let chatUnreadTimer: any = null
const startChatUnreadRefresh = () => {
  fetchChatUnreadCount()
  chatUnreadTimer = setInterval(() => {
    fetchChatUnreadCount()
  }, 5000) // 每5秒刷新一次
}

const stopChatUnreadRefresh = () => {
  if (chatUnreadTimer) {
    clearInterval(chatUnreadTimer)
    chatUnreadTimer = null
  }
}

// 根据当前路由计算哪些子菜单应默认展开
const defaultOpenedSubmenus = computed(() => {
  const opened: string[] = []
  if (route.path.includes('/admin/semesters') ||
      route.path.includes('/admin/instructors') ||
      route.path.includes('/admin/students')) {
    opened.push('trial-settings')
  }
  if (route.path.includes('/admin/assignments')) {
    opened.push('trial-assignment')
  }
  return opened
})

// 管理员菜单 — 学院级管理员结构
const adminMenus = computed(() => {
  const menus: any[] = [
    { index: '/admin/dashboard', icon: DataLine, title: '概览' },
    { index: '/admin/notices', icon: Notification, title: '通知公告' },
    {
      index: 'trial-settings',
      icon: Setting,
      title: '试讲设置',
      children: [
        { index: '/admin/semesters', title: '试讲周期' },
        { index: '/admin/instructors', title: '指导老师' },
        { index: '/admin/students', title: '试讲学生' },
      ]
    },
    {
      index: 'trial-assignment',
      icon: Calendar,
      title: '试讲分配',
      children: [
        { index: '/admin/assignments', title: 'AI 智能分配', isAI: true },
        { index: '/admin/assignments', title: '手工分配' },
      ]
    },
    { index: '/admin/monitor', icon: Monitor, title: '试讲进展' },
    { index: '/admin/grades', icon: TrendCharts, title: '试讲成绩' },
    { index: '/admin/materials', icon: Files, title: '试讲材料' },
    { index: '/admin/trial-videos', icon: VideoCamera, title: '试讲视频管理' },
    { index: '/admin/teaching-tips', icon: VideoCamera, title: '试讲技巧视频' },
    { index: '/admin/textbooks', icon: Files, title: '教材与图片素材' },
    { index: '/admin/export', icon: Download, title: '数据导出' },
    { index: '/admin/ai-models', icon: Key, title: 'AI 模型管理', isAI: true },
    { index: '/admin/ai-ops', icon: Cpu, title: 'AI 运营看板', isAI: true },
    { index: '/admin/data-screen', icon: DataLine, title: '数据大屏', isAI: true },
    { index: '/admin/ai-alerts', icon: Warning, title: 'AI 预警中心', isAI: true },
  ]

  if (authStore.user?.is_super_admin) {
    menus.push({ type: 'divider', index: '__super_divider__' })
    menus.push({ index: '/admin/admins', icon: UserFilled, title: '管理员管理' })
    menus.push({ index: '/admin/settings', icon: Tools, title: '系统设置' })
    menus.push({ index: '/admin/logs', icon: Document, title: '系统日志' })
  }

  return menus
})

const menus = computed(() => {
  const role = authStore.userRole
  if (role === 'instructor') {
    return [
      { index: '/instructor/dashboard', icon: DataLine, title: '试讲概览' },
      { index: '/instructor/reviews', icon: Cpu, title: 'AI 评审助手', isAI: true },
      { index: '/instructor/class-insights', icon: DataLine, title: 'AI 试讲分析', isAI: true },
      { index: '/instructor/student-profiles', icon: User, title: 'AI 成长档案', isAI: true },
      { index: '/instructor/tasks', icon: Files, title: '试讲任务' },
      { index: '/instructor/trial-videos', icon: VideoCamera, title: '学生自主试讲' },
      { index: '/instructor/rubrics', icon: Setting, title: '评分细则' },
      { index: '/admin/grades', icon: TrendCharts, title: '试讲成绩' },
      { index: '/chat', icon: ChatDotRound, title: '联系学员' },
    ]
  } else if (role === 'student') {
    return [
      { index: '/student/dashboard', icon: DataLine, title: 'AI 学习中心' },
      { index: '/student/realtime-eval', icon: VideoCamera, title: 'AI 实时评估', isAI: true },
      { index: '/student/trial-learning', icon: VideoCamera, title: '试讲学习' },
      { index: '/student/ai-assistant', icon: Cpu, title: 'AI 备课助手', isAI: true },
      { index: '/student/ai-generator', icon: MagicStick, title: 'AI 教案生成', isAI: true },
      { index: '/student/learning-path', icon: TrendCharts, title: 'AI 学习路径', isAI: true },
      { index: '/student/my-profile', icon: DataLine, title: '成长画像', isAI: true },
      { index: '/student/task-board', icon: Calendar, title: '任务看板' },
      { index: '/student/my-submissions', icon: IconMenu, title: '我的提交' },
      { index: '/student/my-grades', icon: TrendCharts, title: '我的成绩' },
      { index: '/student/practice-history', icon: ChatDotRound, title: '练习记录' },
      { index: '/student/resources', icon: Document, title: 'AI 资源中心', isAI: true },
      { index: '/chat', icon: ChatDotRound, title: '联系导师' },
    ]
  }
  return []
})

// 用户角色标签
const userRoleLabel = computed(() => {
  const role = authStore.userRole
  if (role === 'student') return '学生'
  if (role === 'instructor') return '教师'
  if (role === 'admin') {
    // 区分超级管理员和普通管理员
    return authStore.user?.is_super_admin ? '超级管理员' : '管理员'
  }
  return '未知'
})

// 学校/学院名称显示
const schoolName = computed(() => {
  // 优先显示用户所在学院
  if (authStore.user?.college) {
    return authStore.user.college
  }
  // 如果没有学院信息，显示默认学校名称
  return '高校师范'
})

// System notice states
const showNoticeDialog = ref(false)
const latestNotice = ref<any | null>(null)
const noticeLoading = ref(false)
const showMarquee = ref(false)
const allNotices = ref<any[]>([])

// Notification drawer for users
const notificationDrawerVisible = ref(false)
const notificationLoading = ref(false)
const notifications = ref<any[]>([])
const noticeUnreadCount = ref(0)
const commentUnreadCount = ref(0)
const unreadCount = computed(() => noticeUnreadCount.value + commentUnreadCount.value)
const notificationCategory = ref('notice')
const categoryUnreadCount = computed(() => notificationCategory.value === 'notice' ? noticeUnreadCount.value : commentUnreadCount.value)
const notificationError = ref('')
const notificationFilter = ref<string>('all') // all, unread, read
const notificationPage = ref(1)
const notificationTotal = ref(0)
const notificationPageSize = 10
let notificationRequest = 0
let notificationTimer: ReturnType<typeof setInterval> | undefined

const fetchUnreadCount = async () => {
  const results = await Promise.allSettled([
    api.get('/notices/user/unread-count'),
    authStore.userRole === 'student' ? api.get('/notifications/unread-count', { params: { type: 'comment' } }) : Promise.resolve(null),
  ])
  const noticeResult: any = results[0]
  const commentResult: any = results[1]
  if (noticeResult.status === 'fulfilled') noticeUnreadCount.value = noticeResult.value.unread_count || 0
  if (commentResult.status === 'fulfilled') commentUnreadCount.value = commentResult.value?.data?.count || 0
}

const fetchLatestNotice = async () => {
  try {
    noticeLoading.value = true
    const res: any = await api.get('/notices/public/latest')
    latestNotice.value = res || null
    
    if (res && authStore.userRole !== 'admin') {
      // Check display_type to determine how to show the notice
      const displayType = res.display_type || 'dialog'
      if (displayType === 'dialog' || displayType === 'both') {
        showNoticeDialog.value = true
      }
      if (displayType === 'marquee' || displayType === 'both') {
        showMarquee.value = true
      }
    }
  } finally {
    noticeLoading.value = false
  }
}

const fetchNotifications = async () => {
  const request = ++notificationRequest
  const category = notificationCategory.value
  try {
    notificationLoading.value = true
    notificationError.value = ''
    const params: any = { 
      page: notificationPage.value, 
      page_size: notificationPageSize 
    }
    if (notificationFilter.value === 'unread') {
      params.is_read = false
    } else if (notificationFilter.value === 'read') {
      params.is_read = true
    }
    if (category === 'comment') params.type = 'comment'
    const res: any = await api.get(category === 'notice' ? '/notices/user/list' : '/notifications', { params })
    if (request !== notificationRequest) return
    const result = category === 'notice' ? res : res.data
    notifications.value = result.items || []
    notificationTotal.value = result.total || 0
  } catch {
    if (request === notificationRequest) notificationError.value = '消息加载失败，请重试'
  } finally {
    if (request === notificationRequest) notificationLoading.value = false
  }
}

const openNotificationDrawer = () => {
  notificationCategory.value = 'notice'
  notificationFilter.value = 'all'
  notifications.value = []
  notificationDrawerVisible.value = true
  notificationPage.value = 1
  fetchNotifications()
  fetchUnreadCount()
}

const handleFilterChange = () => {
  notifications.value = []
  notificationPage.value = 1
  fetchNotifications()
}

const handleNotificationPageChange = (page: number) => {
  notificationPage.value = page
  fetchNotifications()
}

const viewNotice = async (notice: any) => {
  if (notificationCategory.value === 'comment') {
    if (!notice.is_read) {
      try {
        await api.put(`/notifications/${notice.id}/read`)
        notice.is_read = true
        void fetchUnreadCount()
      } catch { return }
    }
    notificationDrawerVisible.value = false
    if (notice.link) {
      const target = router.resolve(notice.link)
      await router.push({ path: target.path, query: { ...target.query, opened: String(Date.now()) } })
    }
    return
  }
  // 标记为已读
  if (!notice.is_read) {
    try {
      await api.post(`/notices/user/read/${notice.id}`)
      notice.is_read = true
      fetchUnreadCount()
    } catch (error) {
      // Ignore
    }
  }
  latestNotice.value = notice
  showNoticeDialog.value = true
}

const markAllAsRead = async () => {
  try {
    if (notificationCategory.value === 'comment') await api.put('/notifications/read-all', null, { params: { type: 'comment' } })
    else await api.post('/notices/user/read-all')
    await fetchUnreadCount()
    await fetchNotifications()
  } catch (error) {
    // Ignore
  }
}

const closeMarquee = () => {
  showMarquee.value = false
}

// 去除 HTML 标签获取纯文本
const stripHtml = (html: string): string => {
  if (!html) return ''
  return html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
}

// 获取跑马灯显示的纯文本
const getMarqueeText = (notice: any): string => {
  if (!notice) return ''
  return stripHtml(notice.content)
}

// 解析附件列表
const getAttachments = (notice: any): { name: string; url: string }[] => {
  if (!notice?.attachment_path) return []
  try {
    return JSON.parse(notice.attachment_path)
  } catch {
    return []
  }
}

const userAvatar = computed(() => {
  if (authStore.user?.avatar) return authStore.user.avatar
  const seed = authStore.user?.user_code || 'default'
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=b6e3f4,c0aede,d1d4f9`
})


// 监听路由变化，实时刷新未读数
watch(() => route.path, () => {
  if (authStore.user) {
    fetchChatUnreadCount()
  }
})

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  fetchSiteSettings()
  if (authStore.userRole && authStore.userRole !== 'admin') {
    fetchLatestNotice()
    fetchUnreadCount()
    notificationTimer = setInterval(async () => {
      const previousCount = unreadCount.value
      await fetchUnreadCount()
      if (notificationDrawerVisible.value && previousCount !== unreadCount.value) void fetchNotifications()
    }, 15000)
  }
  // 启动聊天未读消息刷新
  if (authStore.user) {
    startChatUnreadRefresh()
  }
  // AI 状态检测
  checkAIStatus()
  aiStatusTimer = setInterval(checkAIStatus, 60000) // 每60秒检测一次
})

onUnmounted(() => {
  notificationRequest++
  if (notificationTimer) clearInterval(notificationTimer)
  stopChatUnreadRefresh()
  if (aiStatusTimer) clearInterval(aiStatusTimer)
})

</script>

<template>
  <div class="common-layout h-screen flex flex-col relative">
    <!-- Mobile Overlay -->
    <div 
      v-if="isMobile && !isCollapse" 
      class="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm transition-opacity"
      @click="closeSidebar"
    ></div>

    <!-- Marquee Notice Banner -->
    <div 
      v-if="showMarquee && latestNotice && authStore.userRole !== 'admin'" 
      class="marquee-banner bg-amber-500 text-white py-2 px-4 flex items-center justify-between"
    >
      <div class="marquee-content flex-1 overflow-hidden">
        <div class="marquee-text flex items-center">
          <el-icon class="mr-2"><Bell /></el-icon>
          <span class="font-medium mr-2">{{ latestNotice.title }}:</span>
          <span>{{ getMarqueeText(latestNotice) }}</span>
        </div>
      </div>
      <el-button 
        text 
        class="text-white ml-4" 
        @click="closeMarquee"
      >
        关闭
      </el-button>
    </div>

    <div class="flex flex-1 overflow-hidden">
      <!-- Sidebar -->
      <el-aside :width="sidebarWidth" :class="sidebarClass">
        <div class="h-16 flex items-center px-4 border-b border-slate-800/80 bg-slate-950/40 justify-between flex-shrink-0">
          <div class="flex items-center min-w-0 gap-3">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/30 flex items-center justify-center flex-shrink-0">
              <img src="@/assets/logo.svg" alt="Logo" class="w-5 h-5 filter brightness-0 invert" />
            </div>
            <div v-if="!isCollapse || isMobile" class="flex flex-col min-w-0 leading-tight">
              <span class="font-extrabold text-base tracking-tight truncate text-white">{{ siteName }}</span>
              <span class="text-[10px] text-cyan-400 font-bold tracking-wider uppercase">多模态试讲实训</span>
            </div>
          </div>
        </div>
        
        <!-- Admin Menu with Submenu Support -->
        <el-menu
          v-if="authStore.userRole === 'admin'"
          :default-active="activeMenu"
          :default-openeds="defaultOpenedSubmenus"
          class="el-menu-vertical dark-menu border-none bg-transparent flex-1 overflow-y-auto py-2"
          :collapse="!isMobile && isCollapse"
          background-color="transparent"
          text-color="#94a3b8"
          active-text-color="#ffffff"
          @select="handleMenuSelect"
        >
          <template v-for="menu in adminMenus" :key="menu.index">
            <!-- 分组分割线 -->
            <div v-if="menu.type === 'divider'" class="ai-group-divider" :class="{ 'collapsed': !isMobile && isCollapse }">
              <template v-if="!isCollapse || isMobile">
                <span class="divider-line"></span>
                <span class="divider-label">系统管理</span>
                <span class="divider-line"></span>
              </template>
              <span v-else class="divider-dot"></span>
            </div>
            <!-- Submenu -->
            <el-sub-menu v-else-if="menu.children" :index="menu.index">
              <template #title>
                <el-icon><component :is="menu.icon" /></el-icon>
                <span>{{ menu.title }}</span>
              </template>
              <el-menu-item
                v-for="(child, ci) in menu.children"
                :key="child.index + '_' + ci"
                :index="child.index"
              >
                <template #title>
                  {{ child.title }}
                  <span v-if="child.isAI" class="ai-menu-badge ml-2">AI</span>
                </template>
              </el-menu-item>
            </el-sub-menu>
            <!-- Normal Menu Item -->
            <el-menu-item v-else :index="menu.index">
              <el-icon><component :is="menu.icon" /></el-icon>
              <template #title>
                <span>{{ menu.title }}</span>
                <span v-if="menu.isAI" class="ai-menu-badge">AI</span>
              </template>
            </el-menu-item>
          </template>
        </el-menu>

        <!-- Non-Admin Menu -->
        <el-menu
          v-else
          :default-active="activeMenu"
          class="el-menu-vertical dark-menu border-none bg-transparent flex-1 overflow-y-auto py-2"
          :collapse="isCollapse"
          background-color="transparent"
          text-color="#94a3b8"
          active-text-color="#ffffff"
          @select="handleMenuSelect"
        >
          <template v-for="(menu, idx) in menus" :key="menu.index">
            <!-- AI 分组分割线 -->
            <div v-if="menu.isAI && (idx === 0 || !menus[idx - 1]?.isAI)" class="ai-group-divider" :class="{ 'collapsed': isCollapse }">
              <template v-if="!isCollapse">
                <span class="divider-line"></span>
                <span class="divider-label">AI 智能</span>
                <span class="divider-line"></span>
              </template>
              <span v-else class="divider-dot"></span>
            </div>
            <el-menu-item :index="menu.index">
              <!-- 收起状态：徽章在图标右上角 -->
              <div v-if="isCollapse" class="relative flex items-center justify-center w-full h-full">
                <el-icon><component :is="menu.icon" /></el-icon>
                <div 
                  v-if="menu.index === '/chat' && chatUnreadCount > 0"
                  class="absolute top-2 right-2 flex items-center justify-center min-w-[16px] h-[16px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full border-2 border-slate-900 leading-none transform translate-x-1/2 -translate-y-1/2 shadow-sm z-10"
                >
                  {{ chatUnreadCount > 99 ? '99+' : chatUnreadCount }}
                </div>
              </div>
              <!-- 展开状态：正常显示图标 -->
              <el-icon v-else><component :is="menu.icon" /></el-icon>
              
              <template #title>
                <!-- 展开状态：徽章在文字右上角 -->
                <div v-if="!isCollapse" class="flex items-center w-full">
                  <span class="relative">
                    {{ menu.title }}
                    <div 
                      v-if="menu.index === '/chat' && chatUnreadCount > 0"
                      class="absolute -top-1 -right-3 flex items-center justify-center min-w-[16px] h-[16px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full leading-none transform translate-x-full -translate-y-1/4 shadow-sm"
                    >
                      {{ chatUnreadCount > 99 ? '99+' : chatUnreadCount }}
                    </div>
                  </span>
                  <span v-if="menu.isAI" class="ai-menu-badge ml-2">AI</span>
                </div>
                <!-- 收起状态：只显示文字（tooltip） -->
                <span v-else>{{ menu.title }}</span>
              </template>
            </el-menu-item>
          </template>
        </el-menu>

        <!-- Sidebar Bottom User Card -->
        <div v-if="!isCollapse || isMobile" class="p-3 border-t border-slate-800/80 bg-slate-950/40 flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2.5 min-w-0">
            <el-avatar :size="32" :src="userAvatar" class="border border-indigo-400/40 bg-slate-800 flex-shrink-0"></el-avatar>
            <div class="flex flex-col min-w-0 leading-tight">
              <span class="text-xs font-bold text-slate-200 truncate">{{ authStore.user?.name }}</span>
              <span class="text-[10px] text-cyan-400/80 font-mono truncate">{{ authStore.user?.user_code }}</span>
            </div>
          </div>
          <el-button text circle size="small" class="!text-slate-400 hover:!text-red-400 hover:!bg-white/10" @click="handleLogout" title="退出登录">
            <el-icon :size="16"><SwitchButton /></el-icon>
          </el-button>
        </div>
      </el-aside>

      <!-- Main Content -->
      <div class="flex-1 flex flex-col overflow-hidden min-h-0 bg-slate-50/60">
        <!-- Header -->
        <el-header class="h-16 bg-white/85 backdrop-blur-xl border-b border-slate-200/80 flex items-center justify-between px-6 shadow-xs z-10 sticky top-0">
          <div class="flex items-center">
            <el-button text @click="toggleSidebar" class="mr-3.5 hover:bg-slate-100 rounded-xl !p-2 transition-colors">
              <el-icon :size="19" class="text-slate-600">
                <Expand v-if="isCollapse" />
                <Fold v-else />
              </el-icon>
            </el-button>
            <div class="flex items-center gap-2.5">
              <div class="w-2 h-2 rounded-full bg-indigo-500 shadow-sm shadow-indigo-500/50"></div>
              <h2 class="text-base font-bold text-slate-800 tracking-tight">{{ route.meta.title || schoolName }}</h2>
              <span class="hidden sm:inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-600 border border-indigo-200/60">
                {{ userRoleLabel }}工作台
              </span>
            </div>
          </div>
          
          <div class="flex items-center space-x-3.5">
            <!-- AI 状态指示器 -->
            <el-tooltip :content="aiOnline ? 'AI 智能赋能引擎正常运行中' : aiOnline === false ? 'AI 离线（使用离线算法）' : 'AI 引擎状态检测中...'" placement="bottom">
              <div class="ai-status-indicator" :class="{ online: aiOnline, offline: aiOnline === false, checking: aiOnline === null }">
                <span class="status-dot"></span>
                <span v-if="!isMobile" class="status-text">{{ aiOnline ? 'AI 引擎在线' : aiOnline === false ? 'AI 离线' : '检测中' }}</span>
              </div>
            </el-tooltip>

            <!-- Notification Button for Non-Admin Users -->
            <el-badge 
              v-if="authStore.userRole !== 'admin'" 
              :value="unreadCount" 
              :hidden="unreadCount === 0"
              class="notification-badge"
            >
              <el-button circle plain aria-label="消息通知" class="!border-slate-200 !bg-white hover:!bg-slate-50 shadow-xs" @click="openNotificationDrawer">
                <el-icon class="text-slate-600"><Bell /></el-icon>
              </el-button>
            </el-badge>
            
            <!-- 用户头像下拉菜单 -->
            <el-dropdown trigger="hover" @command="handleUserCommand">
              <div class="flex items-center cursor-pointer hover:bg-slate-100/70 p-1 rounded-full pr-3 transition-all border border-transparent hover:border-slate-200/60">
                <div class="relative mr-2">
                  <el-avatar :size="34" :src="userAvatar" class="border-2 border-white shadow-xs bg-indigo-50"></el-avatar>
                  <span class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white"></span>
                </div>
                <div class="flex flex-col items-start leading-tight">
                  <span class="text-xs font-bold text-slate-800">{{ authStore.user?.name }}</span>
                  <span class="text-[10px] text-slate-500">{{ authStore.user?.user_code }}</span>
                </div>
                <el-icon class="ml-2 text-slate-400 text-xs"><ArrowRight class="rotate-90" /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile" disabled>
                    <div class="flex flex-col py-1">
                      <span class="font-bold text-slate-800">{{ authStore.user?.name }}</span>
                      <span class="text-xs text-slate-500">{{ authStore.user?.user_code }} · {{ userRoleLabel }}</span>
                    </div>
                  </el-dropdown-item>
                  <el-dropdown-item divided command="change-password">
                    <el-icon class="mr-2"><Lock /></el-icon>
                    修改密码
                  </el-dropdown-item>
                  <el-dropdown-item command="help">
                    <el-icon class="mr-2"><QuestionFilled /></el-icon>
                    帮助中心
                  </el-dropdown-item>
                  <el-dropdown-item command="logout" divided>
                    <el-icon class="mr-2 text-red-500"><SwitchButton /></el-icon>
                    <span class="text-red-500 font-medium">退出登录</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <!-- Content -->
        <el-main class="bg-slate-50/60 p-5 sm:p-7 overflow-y-auto">
          <router-view v-slot="{ Component }">
            <transition name="fade-transform" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>

        <!-- System Notice Dialog for non-admin users -->
        <el-dialog
          v-if="latestNotice && authStore.userRole !== 'admin'"
          v-model="showNoticeDialog"
          width="560px"
          :show-close="false"
          class="notice-dialog"
        >
          <template #header>
            <div class="notice-dialog-header">
              <div class="notice-header-icon">
                <el-icon :size="22" color="#fff"><Notification /></el-icon>
              </div>
              <div>
                <div class="text-base font-bold text-gray-800">系统公告</div>
                <div class="text-xs text-gray-400 mt-0.5">{{ new Date(latestNotice.created_at || Date.now()).toLocaleDateString('zh-CN') }}</div>
              </div>
            </div>
          </template>
          <div class="notice-dialog-body">
            <h3 class="notice-title">{{ latestNotice.title }}</h3>
            <div class="notice-html-content" v-html="latestNotice.content"></div>
            <!-- 附件列表 -->
            <div v-if="getAttachments(latestNotice).length > 0" class="notice-attachments">
              <div class="text-xs font-medium text-gray-500 mb-2">附件</div>
              <div class="space-y-1.5">
                <a
                  v-for="(att, index) in getAttachments(latestNotice)"
                  :key="index"
                  :href="att.url"
                  target="_blank"
                  class="notice-attachment-link"
                >
                  <el-icon :size="14"><Paperclip /></el-icon>
                  <span>{{ att.name }}</span>
                </a>
              </div>
            </div>
          </div>
          <template #footer>
            <el-button type="primary" size="large" round class="w-full" @click="showNoticeDialog = false">
              我已知晓
            </el-button>
          </template>
        </el-dialog>

        <!-- Notification Drawer for Users -->
        <el-drawer
          v-model="notificationDrawerVisible"
          title="消息通知"
          direction="rtl"
          size="min(400px, 100vw)"
        >
          <el-tabs v-model="notificationCategory" class="notification-categories" @tab-change="handleFilterChange">
            <el-tab-pane name="notice"><template #label><span class="notification-category-label">系统公告 <span v-if="noticeUnreadCount" class="category-count notice-count">{{ noticeUnreadCount }}</span></span></template></el-tab-pane>
            <el-tab-pane v-if="authStore.userRole === 'student'" name="comment"><template #label><span class="notification-category-label">评论 <span v-if="commentUnreadCount" class="category-count">{{ commentUnreadCount }}</span></span></template></el-tab-pane>
          </el-tabs>
          <!-- 筛选和操作栏 -->
          <div class="flex justify-between items-center mb-4">
            <el-radio-group v-model="notificationFilter" size="small" @change="handleFilterChange">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="unread">未读</el-radio-button>
              <el-radio-button value="read">已读</el-radio-button>
            </el-radio-group>
            <el-button 
              size="small" 
              type="primary" 
              link 
              @click="markAllAsRead"
              :disabled="categoryUnreadCount === 0 || notificationLoading"
            >
              一键已读
            </el-button>
          </div>
          
          <div v-loading="notificationLoading">
            <el-alert v-if="notificationError" :title="notificationError" type="warning" :closable="false"><el-button link @click="fetchNotifications">重试</el-button></el-alert>
            <div v-else-if="notifications.length === 0 && !notificationLoading" class="text-center text-gray-500 py-8">
              {{ notificationFilter === 'unread' ? '没有未读通知' : notificationFilter === 'read' ? '没有已读通知' : '暂无通知' }}
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="notice in notifications"
                :key="notice.id"
                :data-notification-id="notice.id"
                class="p-3 rounded-lg cursor-pointer hover:bg-gray-100 transition relative"
                :class="notice.is_read ? 'bg-gray-50' : 'bg-blue-50 border-l-4 border-blue-500'"
                @click="viewNotice(notice)"
              >
                <div class="flex items-start justify-between">
                  <h4 class="font-medium flex-1" :class="notice.is_read ? 'text-gray-600' : 'text-gray-800'">
                    {{ notice.title }}
                  </h4>
                  <div class="flex items-center gap-1">
                    <el-tag v-if="!notice.is_read" type="danger" size="small">未读</el-tag>
                    <el-tag v-if="notice.is_pinned" type="warning" size="small">置顶</el-tag>
                  </div>
                </div>
                <p class="text-sm text-gray-500 mt-1 line-clamp-2 notification-preview">{{ notificationCategory === 'comment' ? notice.content : stripHtml(notice.content) }}</p>
                <p class="text-xs text-gray-400 mt-2">{{ videoDate(notice.created_at) }}</p>
              </div>
            </div>
            
            <!-- 分页器 -->
            <div v-if="notificationTotal > notificationPageSize" class="mt-4 flex justify-center">
              <el-pagination
                v-model:current-page="notificationPage"
                :page-size="notificationPageSize"
                :total="notificationTotal"
                layout="prev, pager, next"
                small
                @current-change="handleNotificationPageChange"
              />
            </div>
          </div>
        </el-drawer>
      </div>
    </div>
    
    <!-- 快速操作浮动按钮 -->
    <QuickActionsFab />
    <!-- 全局 AI Copilot 浮窗 -->
    <GlobalAICopilot ref="copilotRef" />
  </div>
</template>

<style scoped>
.notification-category-label { display: inline-flex; align-items: center; gap: 6px; }
.category-count { padding: 0 6px; border-radius: 9px; background: #ecfeff; color: #0e7490; font-size: 11px; line-height: 18px; }
.notice-count { background: #fef2f2; color: #dc2626; }
.notification-preview { white-space: pre-line; overflow-wrap: anywhere; }
.el-menu-vertical:not(.el-menu--collapse) {
  width: 240px;
}

/* ==================== 现代深色高奢侧边栏菜单定制 ==================== */
:deep(.dark-menu .el-menu-item),
:deep(.dark-menu .el-sub-menu__title) {
  margin: 3px 10px !important;
  border-radius: 12px !important;
  height: 42px !important;
  line-height: 42px !important;
  font-weight: 500 !important;
  font-size: 13.5px !important;
  color: #94a3b8 !important;
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* 菜单 item hover */
:deep(.dark-menu .el-menu-item:hover),
:deep(.dark-menu .el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.08) !important;
  color: #ffffff !important;
}

:deep(.dark-menu .el-menu-item:hover .el-icon),
:deep(.dark-menu .el-sub-menu__title:hover .el-icon) {
  color: #38bdf8 !important;
}

/* 激活项 */
:deep(.dark-menu .el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(79, 70, 229, 0.35) 0%, rgba(6, 182, 212, 0.15) 100%) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  border-left: 3px solid #6366f1 !important;
  box-shadow: 0 4px 15px -3px rgba(79, 70, 229, 0.3) !important;
}

:deep(.dark-menu .el-menu-item.is-active .el-icon) {
  color: #818cf8 !important;
  filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.5));
}

/* 子菜单展开面板背景与导向线 */
:deep(.dark-menu .el-menu--inline) {
  background-color: rgba(0, 0, 0, 0.2) !important;
  padding-left: 10px !important;
  position: relative;
}

:deep(.dark-menu .el-menu--inline::before) {
  content: '';
  position: absolute;
  left: 24px;
  top: 4px;
  bottom: 8px;
  width: 1.5px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 1px;
}

:deep(.dark-menu .el-menu--inline .el-menu-item) {
  height: 38px !important;
  line-height: 38px !important;
  font-size: 13px !important;
  margin: 2px 8px !important;
}

:deep(.dark-menu .el-menu--inline .el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
}

:deep(.dark-menu .el-menu--inline .el-menu-item.is-active) {
  background: rgba(79, 70, 229, 0.3) !important;
  color: #ffffff !important;
  border-left: 3px solid #6366f1 !important;
}

/* 父级 sub-menu 激活时标题色 */
:deep(.dark-menu .el-sub-menu.is-active > .el-sub-menu__title) {
  color: #ffffff !important;
}

:deep(.dark-menu .el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  color: #818cf8 !important;
}

/* 去掉 Element 默认右侧分隔线 */
:deep(.dark-menu) {
  border-right: none !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Marquee animation */
.marquee-banner {
  z-index: 100;
}

.marquee-content {
  position: relative;
}

.marquee-text {
  animation: marquee 20s linear infinite;
  white-space: nowrap;
}

@keyframes marquee {
  0% {
    transform: translateX(100%);
  }
  100% {
    transform: translateX(-100%);
  }
}

.marquee-text:hover {
  animation-play-state: paused;
}

/* Notification badge */
.notification-badge :deep(.el-badge__content) {
  top: 2px;
  right: 12px;
}

/* Line clamp for notification content */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Notice HTML content styles */
.notice-html-content :deep(img) {
  max-width: 100%;
  height: auto;
  margin: 0.5em 0;
}

.notice-html-content :deep(p) {
  margin: 0.5em 0;
}

.notice-html-content :deep(ul),
.notice-html-content :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.notice-html-content :deep(a) {
  color: #4f46e5;
}

/* Global Scrollbar Styling */
:deep(.el-main)::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

/* 菜单徽章样式优化 */
.el-menu-item {
  position: relative;
}

/* 展开状态：徽章在文字右上角 */
.el-menu-item .inline-flex .el-badge {
  position: relative;
  top: -2px;
}

/* 收起状态：徽章在图标右上角 */
.el-menu--collapse .el-menu-item .el-badge {
  display: inline-block;
}

:deep(.el-main)::-webkit-scrollbar-track {
  background: transparent;
}

:deep(.el-main)::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 9999px;
}

:deep(.el-main)::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 用户下拉菜单样式 */
.rotate-90 {
  transform: rotate(90deg);
}

/* 下拉菜单触发区域 */
.el-dropdown {
  outline: none;
}

/* AI 菜单标签 */
.ai-menu-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1px 7px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: #fff;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.35);
  border-radius: 6px;
  line-height: 16px;
  flex-shrink: 0;
}

/* AI 分组分割线 */
.ai-group-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px 6px;
  user-select: none;
}

.ai-group-divider.collapsed {
  justify-content: center;
  padding: 12px 0 4px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: rgba(99, 102, 241, 0.2);
}

.divider-label {
  font-size: 11px;
  font-weight: 700;
  color: #6366f1;
  white-space: nowrap;
  letter-spacing: 1.5px;
}

.divider-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6366f1;
}

/* AI 状态指示器 */
.ai-status-indicator {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  cursor: default;
  transition: all 0.3s;
}

.ai-status-indicator.online {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 182, 212, 0.12) 100%);
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: #059669;
}

.ai-status-indicator.offline {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.ai-status-indicator.checking {
  background: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ai-status-indicator.online .status-dot {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
  animation: ai-pulse 2s infinite;
}

.ai-status-indicator.offline .status-dot {
  background: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
}

.ai-status-indicator.checking .status-dot {
  background: #9ca3af;
  animation: ai-pulse 1s infinite;
}

@keyframes ai-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  line-height: 1;
}

/* 系统公告弹窗 */
:deep(.notice-dialog) {
  border-radius: 20px;
  overflow: hidden;
}

:deep(.notice-dialog .el-dialog__header) {
  padding: 20px 24px 12px;
  margin: 0;
  border-bottom: 1px solid #f3f4f6;
}

:deep(.notice-dialog .el-dialog__body) {
  padding: 0;
}

:deep(.notice-dialog .el-dialog__footer) {
  padding: 16px 24px 24px;
}

.notice-dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.notice-header-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: #0891b2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.notice-dialog-body {
  padding: 20px 24px;
  max-height: 50vh;
  overflow-y: auto;
}

.notice-title {
  font-size: 17px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 14px;
  line-height: 1.4;
}

.notice-html-content {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.8;
}

.notice-attachments {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f3f4f6;
}

.notice-attachment-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f9fafb;
  color: #0891b2;
  font-size: 13px;
  text-decoration: none;
  transition: background 0.2s;
}

.notice-attachment-link:hover {
  background: #ecfeff;
}
</style>
