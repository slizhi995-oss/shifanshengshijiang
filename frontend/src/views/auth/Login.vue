<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  User, Lock, UserFilled, Reading, School, Bell, ArrowRight,
  EditPen, DataLine, Aim, Share, Guide, Coordinate, Check,
  Microphone, VideoCamera, TrendCharts, MagicStick
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/request'
import bgImage from '@/assets/s.jpg'
import ParticleBackground from '@/components/ParticleBackground.vue'

const authStore = useAuthStore()
const loading = ref(false)

// AI 核心能力指标
const aiCapabilities = [
  { icon: EditPen, label: 'AI 教案生成' },
  { icon: DataLine, label: 'AI 七维分析' },
  { icon: Aim, label: 'AI 实时评估' },
  { icon: Share, label: 'AI 知识图谱' },
  { icon: Guide, label: 'AI 学习路径' },
  { icon: Coordinate, label: 'AI 智能分配' },
]

// 核心多模态优势特性
const coreFeatures = [
  { icon: VideoCamera, title: '多模态体态与表情评测', desc: 'MediaPipe 实时骨骼追踪与教态教风识别' },
  { icon: Microphone, title: '智能语音语调声学分析', desc: '语速停顿、音域波形与口头禅即时诊断' },
  { icon: MagicStick, title: '大模型智能备课赋能', desc: '教案秒级生成、板书设计与模拟学生问答' },
  { icon: TrendCharts, title: '七维立体素养成长档案', desc: '雷达可视化全周期追踪与个性化因材施教' },
]

const forgotPasswordVisible = ref(false)
const latestNotice = ref<any>(null)

// 角色选择
const selectedRole = ref('student')
const roleOptions = [
  {
    value: 'student',
    label: '学生端',
    roleName: '试讲学生',
    icon: School,
    color: '#4f46e5',
    gradient: 'linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)',
    badge: '试讲训练'
  },
  {
    value: 'instructor',
    label: '教师端',
    roleName: '指导老师',
    icon: Reading,
    color: '#0284c7',
    gradient: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
    badge: '评审指导'
  },
  {
    value: 'admin',
    label: '管理端',
    roleName: '系统管理',
    icon: UserFilled,
    color: '#7c3aed',
    gradient: 'linear-gradient(135deg, #7c3aed 0%, #c084fc 100%)',
    badge: '全局运管'
  },
]

const currentRole = computed(() => roleOptions.find(r => r.value === selectedRole.value) || roleOptions[0])

const form = reactive({
  user_code: '',
  password: ''
})

const userCodeLabel = computed(() => {
  if (selectedRole.value === 'admin') return '管理员账号'
  if (selectedRole.value === 'instructor') return '教师工号'
  return '学生学号'
})

const userCodePlaceholder = computed(() => {
  if (selectedRole.value === 'admin') return '请输入管理员账号'
  if (selectedRole.value === 'instructor') return '请输入教师工号'
  return '请输入学生学号'
})

const rules = {
  user_code: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const formRef = ref()

const handleLogin = async () => {
  if (!selectedRole.value) {
    ElMessage.warning('请先选择登录角色')
    return
  }
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        await authStore.login(form)
      } finally {
        loading.value = false
      }
    }
  })
}

const fetchLatestNotice = async () => {
  try {
    const res = await api.get('/notices/public/latest')
    latestNotice.value = res
  } catch (error) {
    console.error('获取公告失败', error)
  }
}

onMounted(() => {
  fetchLatestNotice()
})
</script>

<template>
  <div class="login-wrapper relative w-full min-h-screen overflow-x-hidden flex items-center justify-center p-4 md:p-8">
    <!-- 背景大图层与环境氛围光晕 -->
    <div
      class="fixed inset-0 bg-cover bg-center z-0 scale-105 transition-transform duration-10000"
      :style="{ backgroundImage: `url(${bgImage})` }"
    ></div>
    <div class="fixed inset-0 bg-slate-950/75 backdrop-blur-[6px] z-0"></div>

    <!-- 动态光晕效果 -->
    <div class="fixed top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-600/25 blur-[120px] pointer-events-none z-0"></div>
    <div class="fixed bottom-[-10%] right-[-5%] w-[600px] h-[600px] rounded-full bg-cyan-500/20 blur-[140px] pointer-events-none z-0"></div>

    <!-- AI 粒子网格 -->
    <ParticleBackground
      class="fixed inset-0 z-1 pointer-events-none"
      :particle-count="55"
      :line-distance="140"
      color="147, 197, 253"
      :speed="0.35"
    />

    <!-- 主展示容器 -->
    <div class="relative z-10 w-full max-w-6xl my-auto flex flex-col lg:flex-row gap-8 lg:gap-12 items-center justify-between">
      
      <!-- 左侧：品牌形象与 AI 多模态特色 -->
      <div class="w-full lg:w-7/12 text-white flex flex-col justify-between py-4 pr-0 lg:pr-4">
        <div>
          <!-- 顶部品牌标识 -->
          <div class="flex items-center gap-3.5 mb-6">
            <div class="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md border border-white/25 flex items-center justify-center shadow-lg shadow-indigo-500/10">
              <img src="@/assets/logo.svg" alt="Logo" class="w-9 h-9" />
            </div>
            <div>
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold tracking-wider text-cyan-300 uppercase">智慧师范 · AI 创新实训</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  人工智能赛道
                </span>
              </div>
              <h3 class="text-lg font-bold text-slate-100 tracking-wide">高校师范生试讲实训平台</h3>
            </div>
          </div>

          <!-- 主标题 -->
          <h1 class="text-3xl sm:text-4xl lg:text-5xl font-extrabold leading-tight tracking-tight mb-4 text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-indigo-200">
            面向师范生试讲训练的<br />
            <span class="bg-gradient-to-r from-cyan-400 via-indigo-300 to-pink-400 bg-clip-text text-transparent">
              多模态智能赋能系统
            </span>
          </h1>

          <p class="text-slate-300 text-sm sm:text-base leading-relaxed mb-8 max-w-xl">
            深度融合计算机视觉体态识别、实时声学语音分析与大语言模型，为新时代卓越教师培养打造全流程、立体化、即时反馈的智能试讲工坊。
          </p>

          <!-- 4 大核心特色胶囊卡片 -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-8">
            <div
              v-for="(feat, idx) in coreFeatures"
              :key="idx"
              class="feature-pill flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.07] border border-white/10 backdrop-blur-md hover:bg-white/[0.12] hover:border-white/20 transition-all duration-300"
            >
              <div class="w-9 h-9 rounded-lg bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-cyan-300 flex-shrink-0 mt-0.5">
                <el-icon :size="18"><component :is="feat.icon" /></el-icon>
              </div>
              <div class="min-w-0">
                <h4 class="text-sm font-bold text-white mb-0.5 truncate">{{ feat.title }}</h4>
                <p class="text-xs text-slate-300 line-clamp-1 leading-snug">{{ feat.desc }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 最新公告卡片 -->
        <div v-if="latestNotice" class="notice-glass-card p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-indigo-950/60 to-slate-900/60 border border-indigo-400/25 backdrop-blur-xl relative overflow-hidden shadow-xl">
          <div class="absolute -right-8 -top-8 w-28 h-28 bg-indigo-500/15 rounded-full blur-2xl pointer-events-none"></div>
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2 text-indigo-300 font-bold text-sm">
              <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
              </span>
              <el-icon :size="16" class="text-amber-400"><Bell /></el-icon>
              <span>最新试讲公告</span>
            </div>
            <span class="text-xs text-slate-400 font-mono">
              {{ new Date(latestNotice.created_at).toLocaleDateString() }}
            </span>
          </div>
          <h5 class="text-sm font-semibold text-white mb-1 truncate" :title="latestNotice.title">
            {{ latestNotice.title }}
          </h5>
          <p class="text-xs text-slate-300 line-clamp-2 leading-relaxed">
            {{ String(latestNotice.content ?? '').replace(/<[^>]+>/g, '') }}
          </p>
        </div>
      </div>

      <!-- 右侧：登录卡片 -->
      <div class="w-full lg:w-5/12 max-w-md">
        <div class="login-card-container relative rounded-3xl p-6 sm:p-8 bg-white/95 backdrop-blur-2xl border border-white/70 shadow-2xl shadow-indigo-950/40">
          <!-- 顶部彩色光条 -->
          <div class="absolute top-0 left-8 right-8 h-1 rounded-b-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-indigo-600"></div>

          <!-- 欢迎标题 -->
          <div class="mb-6 pt-1">
            <h2 class="text-2xl font-bold text-slate-800 tracking-tight">欢迎登录</h2>
            <p class="text-xs sm:text-sm text-slate-500 mt-1">请选择您的身份，开始今日的试讲探索</p>
          </div>

          <!-- 角色身份选择 (分段卡片式) -->
          <div class="grid grid-cols-3 gap-2.5 mb-6">
            <div
              v-for="role in roleOptions"
              :key="role.value"
              class="role-card cursor-pointer rounded-xl p-2.5 text-center transition-all duration-200 border flex flex-col items-center justify-center relative overflow-hidden"
              :class="selectedRole === role.value ? 'bg-indigo-50/80 border-indigo-400/80 shadow-sm shadow-indigo-100' : 'bg-slate-50/70 border-slate-200/80 hover:bg-slate-100/80 hover:border-slate-300'"
              @click="selectedRole = role.value"
            >
              <div
                class="w-8 h-8 rounded-lg flex items-center justify-center mb-1.5 transition-colors"
                :style="selectedRole === role.value ? { background: role.gradient, color: '#fff' } : { background: '#e2e8f0', color: '#64748b' }"
              >
                <el-icon :size="16"><component :is="role.icon" /></el-icon>
              </div>
              <span class="text-xs font-bold text-slate-700">{{ role.roleName }}</span>
              <span class="text-[10px] text-slate-400 scale-90">{{ role.badge }}</span>

              <!-- 选中角标 -->
              <div v-if="selectedRole === role.value" class="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-indigo-600 text-white flex items-center justify-center scale-75">
                <el-icon :size="10"><Check /></el-icon>
              </div>
            </div>
          </div>

          <!-- 登录表单 -->
          <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" class="login-form">
            <el-form-item prop="user_code" class="mb-4">
              <template #label>
                <span class="text-xs font-semibold text-slate-600">{{ userCodeLabel }}</span>
              </template>
              <el-input
                v-model="form.user_code"
                :placeholder="userCodePlaceholder"
                :prefix-icon="User"
                clearable
                class="custom-input-field"
              />
            </el-form-item>

            <el-form-item prop="password" class="mb-6">
              <template #label>
                <div class="flex justify-between items-center w-full">
                  <span class="text-xs font-semibold text-slate-600">登录密码</span>
                  <el-button
                    type="primary"
                    link
                    size="small"
                    class="!text-xs !text-indigo-600 hover:!text-indigo-700"
                    @click="forgotPasswordVisible = true"
                    tabindex="-1"
                  >
                    找回密码
                  </el-button>
                </div>
              </template>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
                class="custom-input-field"
                @keyup.enter="handleLogin"
              />
            </el-form-item>

            <el-form-item class="mb-2">
              <el-button
                type="primary"
                class="login-submit-btn w-full !h-12 !text-base !font-bold !rounded-xl !border-none text-white shadow-lg shadow-indigo-500/25 transition-all"
                :loading="loading"
                :style="{ background: currentRole?.gradient }"
                @click="handleLogin"
              >
                立即登录系统
              </el-button>
            </el-form-item>
          </el-form>

          <!-- AI 能力展示带 (无限平滑滚动) -->
          <div class="ai-capabilities-box mt-6 pt-5 border-t border-slate-100">
            <div class="flex items-center justify-center gap-2 mb-3">
              <span class="w-8 h-px bg-slate-200"></span>
              <span class="text-[11px] font-semibold text-slate-400 tracking-wider">AI 智能引擎全流程驱动</span>
              <span class="w-8 h-px bg-slate-200"></span>
            </div>
            <div class="capabilities-viewport">
              <div class="capabilities-track">
                <div v-for="cap in aiCapabilities" :key="cap.label" class="cap-pill">
                  <el-icon :size="13" class="text-indigo-500"><component :is="cap.icon" /></el-icon>
                  <span>{{ cap.label }}</span>
                </div>
                <!-- 循环复本实现平滑跑马灯 -->
                <div v-for="cap in aiCapabilities" :key="cap.label + '-clone'" class="cap-pill">
                  <el-icon :size="13" class="text-indigo-500"><component :is="cap.icon" /></el-icon>
                  <span>{{ cap.label }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 text-center text-[11px] text-slate-400">
            建议使用 Google Chrome、Edge 或现代浏览器以获得最佳多模态视觉体验
          </div>
        </div>
      </div>
    </div>

    <!-- 找回密码弹窗 -->
    <el-dialog v-model="forgotPasswordVisible" title="找回密码指引" width="420px" align-center class="rounded-2xl">
      <div class="space-y-3.5 py-1">
        <div class="flex items-start gap-3 p-3.5 bg-indigo-50/70 rounded-xl border border-indigo-100">
          <div class="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center flex-shrink-0">
            <el-icon><School /></el-icon>
          </div>
          <div>
            <h4 class="font-bold text-slate-800 text-xs mb-0.5">试讲学生</h4>
            <p class="text-xs text-slate-600 leading-relaxed">请联系您的<strong>指导老师</strong>或<strong>学院管理员</strong>，老师可在后台一键重置您的登录密码。</p>
          </div>
        </div>
        <div class="flex items-start gap-3 p-3.5 bg-cyan-50/70 rounded-xl border border-cyan-100">
          <div class="w-8 h-8 rounded-lg bg-cyan-100 text-cyan-600 flex items-center justify-center flex-shrink-0">
            <el-icon><Reading /></el-icon>
          </div>
          <div>
            <h4 class="font-bold text-slate-800 text-xs mb-0.5">指导老师</h4>
            <p class="text-xs text-slate-600 leading-relaxed">请联系<strong>系统管理员</strong>，由管理员在后台控制面板协助修改重置。</p>
          </div>
        </div>
        <div class="text-center text-xs text-slate-400 mt-3 pt-2 border-t border-slate-100">
          管理员支持邮箱：<a href="mailto:admin@cwnu.edu.cn" class="text-indigo-600 font-medium hover:underline">admin@cwnu.edu.cn</a>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-card-container {
  box-shadow: 0 25px 60px -15px rgba(15, 23, 42, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.4);
}

.login-submit-btn:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
}

.login-submit-btn:active {
  transform: translateY(0);
}

/* 跑马灯效果 */
.capabilities-viewport {
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, black 12%, black 88%, transparent);
  -webkit-mask-image: linear-gradient(to right, transparent, black 12%, black 88%, transparent);
}

.capabilities-track {
  display: flex;
  gap: 8px;
  animation: cap-scroll 18s linear infinite;
  width: max-content;
}

.capabilities-track:hover {
  animation-play-state: paused;
}

@keyframes cap-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.cap-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  background: #f1f5f9;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.cap-pill:hover {
  background: #e0e7ff;
  color: #4338ca;
}
</style>
