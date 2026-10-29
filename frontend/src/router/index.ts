import { createRouter, createWebHistory, type RouteRecordRaw, type NavigationGuardNext, type RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Layouts
const MainLayout = () => import('@/layouts/MainLayout.vue')

// Views - lazy load
const Login = () => import('@/views/auth/Login.vue')
const ChangePassword = () => import('@/views/auth/ChangePassword.vue')

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: ChangePassword,
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Home',
        beforeEnter: () => {
          const authStore = useAuthStore()
          switch (authStore.userRole) {
            case 'admin':      return '/admin/dashboard'
            case 'instructor': return '/instructor/dashboard'
            case 'student':    return '/student/dashboard'
            default:           return '/login'
          }
        },
        component: () => import('@/views/auth/Login.vue'), // placeholder, beforeEnter always redirects
      },
      // Admin Routes
      {
        path: 'admin/teaching-tips',
        name: 'AdminTeachingTips',
        component: () => import('@/views/admin/TeachingTipManagement.vue'),
        meta: { roles: ['admin'], title: '试讲技巧视频' }
      },
      {
        path: 'admin/trial-videos',
        name: 'AdminTrialVideos',
        component: () => import('@/views/admin/TrialVideoManagement.vue'),
        meta: { roles: ['admin'], title: '试讲视频管理' }
      },
      {
        path: 'admin/textbooks',
        name: 'AdminTextbooks',
        component: () => import('@/views/admin/TextbookManagement.vue'),
        meta: { roles: ['admin'], title: '教材与图片素材' }
      },
      {
        path: 'admin/dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/instructors',
        name: 'AdminInstructors',
        component: () => import('@/views/admin/InstructorManagement.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/students',
        name: 'AdminStudents',
        component: () => import('@/views/admin/StudentManagement.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/notices',
        name: 'AdminNotices',
        component: () => import('@/views/admin/NoticeManagement.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/semesters',
        name: 'AdminSemesters',
        component: () => import('@/views/admin/SemesterManagement.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/assignments',
        name: 'AdminAssignments',
        component: () => import('@/views/admin/AssignmentManagement.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/monitor',
        name: 'AdminMonitor',
        component: () => import('@/views/admin/GlobalMonitor.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'admin/admins',
        name: 'AdminManagement',
        component: () => import('@/views/admin/AdminManagement.vue'),
        meta: { roles: ['admin'], requireSuperAdmin: true }
      },
      {
        path: 'admin/settings',
        name: 'SystemSettings',
        component: () => import('@/views/admin/SystemSettings.vue'),
        meta: { roles: ['admin'], requireSuperAdmin: true }
      },
      {
        path: 'admin/grades',
        name: 'AdminStudentGrades',
        component: () => import('@/views/admin/StudentGrades.vue'),
        meta: { roles: ['admin', 'instructor'], title: '试讲成绩' }
      },
      {
        path: 'admin/ai-ops',
        name: 'AdminAIOperations',
        component: () => import('@/views/admin/AIOperations.vue'),
        meta: { roles: ['admin'], title: 'AI 运营看板' }
      },
      {
        path: 'admin/ai-models',
        name: 'AdminAIModelManagement',
        component: () => import('@/views/admin/AIModelManagement.vue'),
        meta: { roles: ['admin'], title: 'AI 模型管理' }
      },
      {
        path: 'admin/materials',
        name: 'AdminMaterials',
        component: () => import('@/views/admin/MaterialManagement.vue'),
        meta: { roles: ['admin'], title: '试讲材料' }
      },
      {
        path: 'admin/export',
        name: 'AdminDataExport',
        component: () => import('@/views/admin/DataExport.vue'),
        meta: { roles: ['admin'], title: '数据导出' }
      },
      {
        path: 'admin/data-screen',
        name: 'DataScreen',
        component: () => import('@/views/admin/DataScreen.vue'),
        meta: { roles: ['admin'], title: '数据大屏' }
      },
      {
        path: 'admin/ai-alerts',
        name: 'AdminAIAlerts',
        component: () => import('@/views/admin/AIAlerts.vue'),
        meta: { roles: ['admin'], title: 'AI 预警中心' }
      },
      {
        path: 'admin/logs',
        name: 'SystemLogs',
        component: () => import('@/views/admin/SystemLogs.vue'),
        meta: { roles: ['admin'], title: '系统日志' }
      },

      // Instructor Routes
      {
        path: 'instructor/trial-videos',
        name: 'InstructorTrialVideos',
        component: () => import('@/views/instructor/TrialVideos.vue'),
        meta: { roles: ['instructor'], title: '学生自主试讲' }
      },
      {
        path: 'instructor/dashboard',
        name: 'InstructorDashboard',
        component: () => import('@/views/instructor/Dashboard.vue'),
        meta: { roles: ['instructor'] }
      },
      {
        path: 'instructor/tasks',
        name: 'InstructorTasks',
        component: () => import('@/views/instructor/TaskManagement.vue'),
        meta: { roles: ['instructor'] }
      },
      {
        path: 'instructor/reviews',
        name: 'InstructorReviews',
        component: () => import('@/views/instructor/SubmissionReview.vue'),
        meta: { roles: ['instructor'] }
      },
      {
        path: 'instructor/student-profiles',
        name: 'InstructorStudentProfiles',
        component: () => import('@/views/instructor/StudentProfiles.vue'),
        meta: { roles: ['instructor'], title: '学生画像' }
      },
      {
        path: 'instructor/rubrics',
        name: 'InstructorRubrics',
        component: () => import('@/views/instructor/RubricConfig.vue'),
        meta: { roles: ['instructor'], title: '评分规则' }
      },
      {
        path: 'instructor/class-insights',
        name: 'InstructorClassInsights',
        component: () => import('@/views/instructor/ClassInsights.vue'),
        meta: { roles: ['instructor'], title: 'AI 班级洞察' }
      },

      // Student Routes
      {
        path: 'student/trial-learning',
        name: 'TrialLearning',
        component: () => import('@/views/student/TrialLearning.vue'),
        meta: { roles: ['student'], title: '试讲学习' }
      },
      {
        path: 'student/dashboard',
        name: 'StudentDashboard',
        component: () => import('@/views/student/Dashboard.vue'),
        meta: { roles: ['student'] }
      },
      {
        path: 'student/tasks',
        name: 'StudentTasks',
        component: () => import('@/views/student/TaskList.vue'),
        meta: { roles: ['student'] }
      },
      {
        path: 'student/task-board',
        name: 'TaskBoard',
        component: () => import('@/views/student/TaskBoard.vue'),
        meta: { roles: ['student'], title: '任务看板' }
      },
      {
        path: 'student/my-submissions',
        name: 'StudentSubmissions',
        component: () => import('@/views/student/MySubmissions.vue'),
        meta: { roles: ['student'] }
      },
      {
        path: 'student/my-grades',
        name: 'MyGrades',
        component: () => import('@/views/student/MyGrades.vue'),
        meta: { roles: ['student'], title: '我的成绩' }
      },
      {
        path: 'student/messages',
        name: 'StudentMessages',
        component: () => import('@/views/student/Messages.vue'),
        meta: { roles: ['student'] }
      },
      {
        path: 'student/ai-assistant',
        name: 'AIAssistant',
        component: () => import('@/views/student/AIAssistant.vue'),
        meta: { roles: ['student'], title: 'AI 备课助手' }
      },
      {
        path: 'student/ai-generator',
        name: 'AIGenerator',
        component: () => import('@/views/student/AIGenerator.vue'),
        meta: { roles: ['student'], title: 'AI 教案生成' }
      },
      {
        path: 'student/my-profile',
        name: 'StudentProfile',
        component: () => import('@/views/student/MyProfile.vue'),
        meta: { roles: ['student'], title: '成长画像' }
      },
      {
        path: 'student/realtime-eval',
        name: 'RealtimeEval',
        component: () => import('@/views/student/RealtimeEval.vue'),
        meta: { roles: ['student'], title: 'AI 实时评估' }
      },
      {
        path: 'student/learning-path',
        name: 'LearningPath',
        component: () => import('@/views/student/LearningPath.vue'),
        meta: { roles: ['student'], title: 'AI 学习路径' }
      },
      {
        path: 'student/practice-history',
        name: 'PracticeHistory',
        component: () => import('@/views/student/PracticeHistory.vue'),
        meta: { roles: ['student'], title: '练习记录' }
      },
      {
        path: 'student/resources',
        name: 'ResourceCenter',
        component: () => import('@/views/student/ResourceCenter.vue'),
        meta: { roles: ['student'], title: '资源中心' }
      },
      {
        path: 'student/ai-report/:submissionId',
        name: 'StudentAIReport',
        component: () => import('@/views/student/AIReport.vue'),
        meta: { roles: ['student'], title: 'AI 多模态诊断' }
      },
      {
        path: 'instructor/ai-report/:submissionId',
        name: 'InstructorAIReport',
        component: () => import('@/views/student/AIReport.vue'),
        meta: { roles: ['instructor'], title: 'AI 多模态诊断' }
      },
      // Shared
      {
        path: 'messages',
        name: 'Messages',
        component: () => import('@/views/student/Messages.vue'), // Reusing component for now
        meta: { roles: ['instructor', 'student'] }
      },
      {
        path: 'chat',
        name: 'ChatRoom',
        component: () => import('@/views/ChatRoom.vue'),
        meta: { roles: ['instructor', 'student'], title: '师生联系' }
      },
      {
        path: 'help',
        name: 'HelpCenter',
        component: () => import('@/views/HelpCenter.vue'),
        meta: { roles: ['admin', 'instructor', 'student'], title: '帮助中心' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Global Navigation Guard
router.beforeEach((to: RouteLocationNormalized, from: RouteLocationNormalized, next: NavigationGuardNext) => {
  const authStore = useAuthStore()
  const isAuthenticated = authStore.isAuthenticated
  const isDefaultPassword = authStore.isDefaultPassword

  // Helper: role-based dashboard path
  const dashboardPath = () => {
    switch (authStore.userRole) {
      case 'admin':      return '/admin/dashboard'
      case 'instructor': return '/instructor/dashboard'
      case 'student':    return '/student/dashboard'
      default:           return '/login'
    }
  }

  // 1. Public routes
  if (to.meta.public) {
    if (isAuthenticated) {
      return next(dashboardPath())
    }
    return next()
  }

  // 2. Check authentication
  if (!isAuthenticated) {
    return next('/login')
  }

  // 3. Force password change
  if (isDefaultPassword) {
    if (to.name !== 'ChangePassword') {
      return next('/change-password')
    }
    return next()
  }

  // Prevent accessing change-password if not default password
  if (to.name === 'ChangePassword' && !isDefaultPassword) {
    return next(dashboardPath())
  }

  // 4. Check roles
  if (to.meta.roles) {
    const roles = to.meta.roles as string[]
    if (!roles.includes(authStore.userRole || '')) {
      return next(dashboardPath())
    }
  }

  next()
})

export default router
