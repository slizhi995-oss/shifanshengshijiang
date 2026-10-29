<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  ChatDotRound, Document, Refresh, Close, Loading, 
  CircleCheck, Warning, Star, TrendCharts, Upload, 
  Delete, Plus, MoreFilled, User, Setting,
  Menu, ArrowLeft, ArrowRight, UploadFilled,
  Service, QuestionFilled, Sunny, Trophy,
  Reading, DataAnalysis, ChatLineRound, Lightning,
  Connection, Search, Aim, MagicStick, CopyDocument, Download, Cpu,
  FolderOpened, Collection, Top
} from '@element-plus/icons-vue'
import api from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { aiApi, handleStreamResponse, BUILTIN_TEMPLATES, type PracticeReport } from '@/api/ai'
import { aiModelApi, type AIModelConfig } from '@/api/aiModels'
import { useAIGeneratorStore } from '@/stores/aiGenerator'
import { storeToRefs } from 'pinia'
import LessonWordPreview from '@/components/LessonWordPreview.vue'
import LessonMatchedResources from '@/components/LessonMatchedResources.vue'
import { subjectOptions, stagesForSubject } from '@/constants/textbooks'

// ==================== 类型定义 ====================

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  isError?: boolean
  timestamp: number
}

interface ChatSession {
  id: string
  title: string
  updatedAt: number
  messages: ChatMessage[]
  settings: {
    grade: string
    personality: string
    lessonPlanText: string
    source: 'submission' | 'upload'
    filename: string
    modelId?: number | null
    teachingMethod?: string
    studentCount?: string
    focusArea?: string
    interactionStyle?: string
    difficultyLevel?: string
  }
  report?: PracticeReport
}

// ==================== 状态定义 ====================

const authStore = useAuthStore()
const currentMode = ref<'chat' | 'generator'>('chat')

// --- Generator Store ---
const genStore = useAIGeneratorStore()
const wordPreview = ref<InstanceType<typeof LessonWordPreview>>()
const wordReady = ref(false)
const { 
  generating: genGenerating, 
  generatedContent: genContent, 
  records: genRecords, 
  currentRecordId: genRecordId, 
  selectedTemplate: genTemplate, 
  customTemplateFile: genCustomFile,
  form: genForm, 
  sortedRecords: genSortedRecords, 
  canGenerate: genCanGenerate,
  generationHint: genGenerationHint,
  currentGenerationInfo: genInfo
} = storeToRefs(genStore)
const genCurrentRecord = computed(() => genRecords.value.find(record => record.id === genRecordId.value))
const saveGenDocument = (id: string) => {
  if (genRecordId.value) genStore.setWordDocument(genRecordId.value, id)
}

// 模拟进度条
const genProgress = ref(0)
let progressTimer: any = null

watch(genGenerating, (val) => {
  if (val) {
    genProgress.value = 0
    progressTimer = setInterval(() => {
      if (genProgress.value < 95) {
        // 前期快，后期慢
        const step = genProgress.value < 30 ? 5 : genProgress.value < 70 ? 2 : 0.5
        genProgress.value = Math.min(95, genProgress.value + step)
      }
    }, 200)
  } else {
    genProgress.value = 100
    if (progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }
  }
})

// --- Chat State ---
const aiEnabled = ref(true)
const aiLoading = ref(false)

// 侧边栏状态
const showSidebar = ref(true)
const showSettings = ref(false)
const showHistory = ref(true)

// 教案选择状态
const submissions = ref<any[]>([])
const loadingSubmissions = ref(false)
const parsingFile = ref(false)

// Chat Settings
const currentSettings = ref({
  submissionId: null as number | null,
  grade: '小学四年级',
  personality: 'normal',
  lessonPlanText: '',
  source: 'submission' as 'submission' | 'upload',
  filename: '',
  modelId: null as number | null,
  teachingMethod: 'lecture',
  studentCount: 'medium',
  focusArea: 'comprehensive',
  interactionStyle: 'guided',
  difficultyLevel: 'intermediate'
})

const availableModels = ref<AIModelConfig[]>([])

// 会话状态
const sessions = ref<ChatSession[]>([])
const currentSessionId = ref<string | null>(null)
const userInput = ref('')
const isGenerating = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// 报告状态
const showReport = ref(false)
const generatingReport = ref(false)

// 课堂模拟增强: 实时教学评分
interface TeachingEvalScore {
  knowledge: number
  guidance: number
  adaptability: number
  control: number
  tip: string
}
const evalScores = ref<TeachingEvalScore>({
  knowledge: 0,
  guidance: 0,
  adaptability: 0,
  control: 0,
  tip: '',
})
const evalHistory = ref<TeachingEvalScore[]>([])
const showReplay = ref(false)
const replayIndex = ref(0)
const replayPlaying = ref(false)
let replayTimer: ReturnType<typeof setInterval> | null = null

// 虚拟教室当前发言者
const activeSpeaker = ref('')

// --- Options ---
const generatorStages = computed(() => stagesForSubject(genForm.value.subject))

const gradeOptions = [
  '小学一年级', '小学二年级', '小学三年级', 
  '小学四年级', '小学五年级', '小学六年级',
  '初中一年级', '初中二年级', '初中三年级',
  '高中一年级', '高中二年级', '高中三年级'
]

const durationOptions = [10, 15, 20, 25, 30, 35, 40, 45]

const personalityOptions = [
  { label: '好奇宝宝', value: 'curious', desc: '爱问"为什么"，追根究底', icon: QuestionFilled },
  { label: '普通学生', value: 'normal', desc: '正常学习，配合度高', icon: Sunny },
  { label: '学霸挑战', value: 'challenging', desc: '思维活跃，问题刁钻', icon: Trophy },
  { label: '模拟课堂', value: 'classroom_simulation', desc: '多角色模拟真实课堂场景', icon: Service },
]

const teachingMethodOptions = [
  { label: '讲授法', value: 'lecture', desc: '系统讲解知识点' },
  { label: '讨论法', value: 'discussion', desc: '引导学生互动讨论' },
  { label: '探究式', value: 'inquiry', desc: '问题驱动自主探究' },
  { label: '翻转课堂', value: 'flipped', desc: '学生主导课堂活动' },
]

const studentCountOptions = [
  { label: '小班 (5-10人)', value: 'small' },
  { label: '中班 (20-30人)', value: 'medium' },
  { label: '大班 (40+人)', value: 'large' },
]

const focusAreaOptions = [
  { label: '知识传授', value: 'knowledge' },
  { label: '能力培养', value: 'ability' },
  { label: '素质教育', value: 'quality' },
  { label: '综合发展', value: 'comprehensive' },
]

const interactionStyleOptions = [
  { label: '引导式', value: 'guided', desc: 'AI逐步引导教学过程' },
  { label: '自由式', value: 'free', desc: '自由对话，灵活应变' },
  { label: '问答式', value: 'qa', desc: '以提问回答为主' },
]

const difficultyLevelOptions = [
  { label: '基础', value: 'basic' },
  { label: '进阶', value: 'intermediate' },
  { label: '挑战', value: 'advanced' },
]

const showAdvancedConfig = ref(false)

const scenePresets = [
  { name: '新手入门', desc: '适合初次练习', config: { grade: '小学三年级', personality: 'normal', teachingMethod: 'lecture', studentCount: 'small', focusArea: 'knowledge', interactionStyle: 'guided', difficultyLevel: 'basic' } },
  { name: '课堂挑战', desc: '高难度模拟', config: { grade: '高中一年级', personality: 'challenging', teachingMethod: 'inquiry', studentCount: 'large', focusArea: 'ability', interactionStyle: 'free', difficultyLevel: 'advanced' } },
  { name: '互动研讨', desc: '注重讨论互动', config: { grade: '初中二年级', personality: 'curious', teachingMethod: 'discussion', studentCount: 'medium', focusArea: 'comprehensive', interactionStyle: 'qa', difficultyLevel: 'intermediate' } },
  { name: '模拟公开课', desc: '多角色真实课堂', config: { grade: '小学四年级', personality: 'classroom_simulation', teachingMethod: 'lecture', studentCount: 'large', focusArea: 'comprehensive', interactionStyle: 'guided', difficultyLevel: 'intermediate' } },
]

const applyPreset = (preset: typeof scenePresets[0]) => {
  Object.assign(currentSettings.value, preset.config)
}

// Generator Quick Templates
const quickTemplates = [
  { subject: '语文', grade: '小学四年级', topic: '草原', icon: Reading },
  { subject: '数学', grade: '初中二年级', topic: '一元二次方程', icon: DataAnalysis },
  { subject: '英语', grade: '初中一年级', topic: 'My Family', icon: ChatLineRound },
  { subject: '物理', grade: '高中一年级', topic: '牛顿第一定律', icon: Lightning },
]

// Generator Template Icons
const templateIcons: Record<string, any> = {
  default: Document,
  interactive: Connection,
  inquiry: Search,
  custom: UploadFilled
}

// ==================== 计算属性 ====================

const currentSession = computed(() => {
  return sessions.value.find(s => s.id === currentSessionId.value)
})

const sessionMessages = computed(() => currentSession.value?.messages ?? [])

const lastSessionMessage = computed(() => {
  return sessionMessages.value[sessionMessages.value.length - 1]
})

const sortedSessions = computed(() => {
  return [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt)
})

const canStartChat = computed(() => {
  if (currentSettings.value.source === 'submission') {
    return currentSettings.value.submissionId !== null
  }
  return currentSettings.value.lessonPlanText.length > 0
})

const messageCount = computed(() => {
  if (!currentSession.value) return 0
  return currentSession.value.messages.filter(m => m.role === 'user').length
})

const currentTemplateLabel = computed(() => {
  const tpl = BUILTIN_TEMPLATES.find(t => t.value === genTemplate.value)
  return tpl ? tpl.label : '经典教案'
})

// ==================== 核心逻辑 ====================

onMounted(() => {
  checkAIStatus()
  fetchModels() // Fetch models
  fetchMySubmissions()
  loadSessionsFromLocal()
  genStore.initialize() // Init Generator Store
})

const fetchModels = async () => {
  try {
    const res: any = await aiModelApi.getAvailableModels('text')
    if (res.success) {
      availableModels.value = res.data?.items || res.items || []
      // Set default
      const def = availableModels.value.find(m => m.is_default) || availableModels.value[0]
      if (def) {
          currentSettings.value.modelId = def.id
          if (!genForm.value.modelId) genForm.value.modelId = def.id
      }
    }
  } catch(e) { console.error('Failed to load models', e) }
}

const checkAIStatus = async () => {
  try {
    const status = await aiApi.getStatus()
    aiEnabled.value = status.enabled
  } catch {
    aiEnabled.value = false
  }
}

const fetchMySubmissions = async () => {
  loadingSubmissions.value = true
  try {
    const res: any = await api.get('/submissions/my')
    submissions.value = (res || []).filter((s: any) => s.lesson_plan_path)
  } finally {
    loadingSubmissions.value = false
  }
}

const loadSessionsFromLocal = () => {
  const localData = localStorage.getItem(`chat_sessions_${authStore.user?.id}`)
  if (localData) {
    try {
      sessions.value = JSON.parse(localData)
    } catch (e) {
      console.error('加载历史会话失败', e)
    }
  }
}

watch(sessions, () => {
  saveSessionsToLocal()
}, { deep: true })

const showConfigDialog = ref(false)

const switchMode = (mode: 'chat' | 'generator') => {
  currentMode.value = mode
}

const goToWelcome = () => {
  currentMode.value = 'chat'
  currentSessionId.value = null
  showSettings.value = true
}

const handleCreateNew = () => {
  goToWelcome()
}

const startPracticeFromDialog = () => {
  showConfigDialog.value = false
  startPractice()
}

const quickStartGen = (tpl: { subject: string; grade: string; topic: string; icon: any }) => {
  switchMode('generator')
  useQuickTemplate(tpl)
}

const createChatSession = () => {
  currentSessionId.value = null
  currentSettings.value = {
    submissionId: null,
    grade: '小学四年级',
    personality: 'normal',
    lessonPlanText: '',
    source: 'submission',
    filename: '',
    modelId: availableModels.value.find(m => m.is_default)?.id || (availableModels.value[0]?.id || null),
    teachingMethod: 'lecture',
    studentCount: 'medium',
    focusArea: 'comprehensive',
    interactionStyle: 'guided',
    difficultyLevel: 'intermediate'
  }
  showSettings.value = true
}

const deleteSession = (id: string, e: Event) => {
  e.stopPropagation()
  const index = sessions.value.findIndex(s => s.id === id)
  if (index > -1) {
    sessions.value.splice(index, 1)
    if (currentSessionId.value === id) {
      currentSessionId.value = null
      showSettings.value = true
    }
    ElMessage.success('会话已删除')
  }
}

const selectSession = (id: string) => {
  currentSessionId.value = id
  showSettings.value = false
  nextTick(scrollToBottom)
}

const createGenSession = () => {
  genStore.createNew()
  genStore.generatedContent = ''
}

const selectGenRecord = (record: any) => {
  genStore.selectRecord(record)
}

const deleteGenRecord = (id: string, e: Event) => {
  e.stopPropagation()
  genStore.deleteRecord(id)
}

const useQuickTemplate = (template: typeof quickTemplates[0]) => {
  genStore.updateForm({
    subject: template.subject,
    grade: template.grade,
    topic: template.topic,
  })
}

const handleGenTemplateUpload = async (file: any) => {
  if (!file.raw) return
  const rawFile = file.raw
  const isPDF = rawFile.type === 'application/pdf'
  const isWord = rawFile.type.includes('word') || rawFile.name.endsWith('.docx') || rawFile.name.endsWith('.doc')
  
  if (!isPDF && !isWord) {
    ElMessage.error('仅支持 PDF 和 Word 文档')
    return
  }
  
  try {
    const res = await aiApi.parseFile(rawFile)
    if (res.success) {
      genStore.setCustomTemplate(res.data.content, res.data.filename)
      ElMessage.success('模板解析成功')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '模板解析失败')
  }
}

const generateLessonPlan = async () => {
  const success = await genStore.generateLessonPlan()
}

const copyGenContent = () => wordPreview.value?.copy()
const downloadGenContent = () => wordPreview.value?.download()

const handleSubmissionChange = (val: number) => {
  const sub = submissions.value.find(s => s.id === val)
  if (sub) {
    currentSettings.value.source = 'submission'
    currentSettings.value.filename = sub.task?.title || sub.lesson_plan_name
  }
}

const handleFileUpload = async (file: any) => {
  if (!file.raw) return
  const rawFile = file.raw
  const isPDF = rawFile.type === 'application/pdf'
  const isWord = rawFile.type.includes('word') || rawFile.name.endsWith('.docx') || rawFile.name.endsWith('.doc')
  
  if (!isPDF && !isWord) {
    ElMessage.error('仅支持 PDF 和 Word 文档')
    return
  }
  parsingFile.value = true
  try {
    const res = await aiApi.parseFile(rawFile)
    if (res.success) {
      currentSettings.value.source = 'upload'
      currentSettings.value.lessonPlanText = res.data.content
      currentSettings.value.filename = res.data.filename
      currentSettings.value.submissionId = null
      ElMessage.success('解析成功')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '文件解析失败')
  } finally {
    parsingFile.value = false
  }
}

const startPractice = async () => {
  if (currentSettings.value.source === 'submission' && currentSettings.value.submissionId) {
    aiLoading.value = true
    try {
      const res = await aiApi.startAssistant({
        submission_id: currentSettings.value.submissionId,
        grade: currentSettings.value.grade,
        personality: currentSettings.value.personality as any,
        model_id: currentSettings.value.modelId
      })
      if (res.success) {
        initSession(res.data.message, res.data.lesson_plan_text)
      }
    } catch (error: any) {
      ElMessage.error(error.message || '启动失败')
    } finally {
      aiLoading.value = false
    }
  } else if (currentSettings.value.lessonPlanText) {
    aiLoading.value = true
    try {
      const res = await aiApi.startAssistant({
        lesson_plan_text: currentSettings.value.lessonPlanText,
        grade: currentSettings.value.grade,
        personality: currentSettings.value.personality as any,
        model_id: currentSettings.value.modelId
      })
      if (res.success) {
        initSession(res.data.message, currentSettings.value.lessonPlanText)
      }
    } catch (error: any) {
      ElMessage.error(error.message || '启动失败')
    } finally {
      aiLoading.value = false
    }
  } else {
    ElMessage.warning('请先选择教案或上传文件')
  }
}

const initSession = (firstMessage: string, text: string) => {
  const newSession: ChatSession = {
    id: Date.now().toString(),
    title: currentSettings.value.filename || '未命名练习',
    updatedAt: Date.now(),
    settings: { ...currentSettings.value, lessonPlanText: text },
    messages: [
      {
        id: Date.now().toString(),
        role: 'assistant',
        content: firstMessage,
        timestamp: Date.now()
      }
    ]
  }
  
  sessions.value.unshift(newSession)
  currentSessionId.value = newSession.id
  showSettings.value = false
  nextTick(scrollToBottom)
}

const sendMessage = async () => {
  const content = userInput.value.trim()
  if (!content || isGenerating.value || !currentSession.value) return
  
  const session = currentSession.value
  
  session.messages.push({
    id: Date.now().toString(),
    role: 'user',
    content,
    timestamp: Date.now()
  })
  
  session.updatedAt = Date.now()
  userInput.value = ''
  await scrollToBottom()
  
  isGenerating.value = true
  const aiMsgId = (Date.now() + 1).toString()
  
  session.messages.push({
    id: aiMsgId,
    role: 'assistant',
    content: '',
    timestamp: Date.now()
  })
  
  // 3s 首字节兜底：若 3 秒内未收到任何流式 chunk，自动改用预置回复，避免 UI 卡死
  const abortController = new AbortController()
  let firstChunkReceived = false
  let usedFallback = false
  const firstByteTimer = setTimeout(() => {
    if (!firstChunkReceived) {
      usedFallback = true
      try { abortController.abort() } catch {}
      const aiMsg = session.messages.find(m => m.id === aiMsgId)
      if (aiMsg) {
        // 根据用户问题匹配一个学生口吻的预置回复
        const lower = (content || '').toLowerCase()
        let reply = '老师，我大概理解您的意思了。能不能再举一个生活中的例子帮我理解？这样我会记得更牢。'
        if (lower.includes('为什么') || lower.includes('怎么')) {
          reply = '老师，您讲的我有点没听明白。能不能用更简单的方式再讲一遍？最好能配合一个具体的例子。'
        } else if (lower.includes('题') || lower.includes('练习')) {
          reply = '好的老师！我来试着回答这道题：根据刚才学的方法，应该是先……然后……请老师看看我的思路对不对。'
        } else if (lower.includes('总结') || lower.includes('回顾')) {
          reply = '今天我学到了：核心概念是什么，关键方法有哪些，还有需要注意的地方。我觉得最有趣的是您举的那个例子，让我印象很深。'
        }
        aiMsg.content = reply
        scrollToBottom()
      }
    }
  }, 3000)

  try {
    const token = authStore.token
    const history = session.messages.slice(0, -2).slice(-10).map(m => ({
      role: m.role,
      content: m.content
    })) as any
    
    const response = await fetch('/api/v1/ai/assistant/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        message: content,
        lesson_plan_text: session.settings.lessonPlanText,
        grade: session.settings.grade,
        personality: session.settings.personality,
        conversation_history: history,
        stream: true,
        model_id: session.settings.modelId
      }),
      signal: abortController.signal,
    })

    if (!response.ok) throw new Error('网络请求失败')

    const aiMsg = session.messages.find(m => m.id === aiMsgId)

    await handleStreamResponse(response, (chunk) => {
      if (usedFallback) return // 已经用了 fallback，忽略后到的真实数据
      if (!firstChunkReceived) {
        firstChunkReceived = true
        clearTimeout(firstByteTimer)
      }
      if (aiMsg) {
        aiMsg.content += chunk
        scrollToBottom()
      }
    })
    
    // 解析 [EVAL] 标签
    const aiMsgFinal = session.messages.find(m => m.id === aiMsgId)
    if (aiMsgFinal && isClassroomSimulation.value) {
      const { cleaned, eval: evalData } = parseEvalFromMessage(aiMsgFinal.content)
      aiMsgFinal.content = cleaned
      if (evalData) {
        evalScores.value = evalData
        evalHistory.value.push(evalData)
      }
      detectSpeaker(cleaned)
    }

  } catch (error) {
    // 如果是 3s 兜底主动 abort，catch 会被触发，但 aiMsg 已经被 fallback 填好，不要追加错误标记
    if (!usedFallback) {
      console.error(error)
      const aiMsg = session.messages.find(m => m.id === aiMsgId)
      if (aiMsg) {
        aiMsg.content += '\n\n[网络错误，请重试]'
        aiMsg.isError = true
      }
    }
  } finally {
    clearTimeout(firstByteTimer)
    isGenerating.value = false
    nextTick(() => inputRef.value?.focus())
  }
}

const generateReport = async () => {
  if (!currentSession.value) return
  if (messageCount.value < 2) {
    ElMessage.warning('对话内容太少，请多聊几句')
    return
  }
  
  generatingReport.value = true
  try {
    const history = currentSession.value.messages.map(m => ({
      role: m.role,
      content: m.content
    })) as any
    
    const res = await aiApi.generateReport(history, currentSession.value.settings.modelId)
    if (res.success) {
      currentSession.value.report = res.data
      showReport.value = true
    }
  } catch (error: any) {
    ElMessage.error('生成报告失败')
  } finally {
    generatingReport.value = false
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const formatTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`
}

const formatDate = (ts: number) => {
  const d = new Date(ts)
  const today = new Date()
  if (d.getDate() === today.getDate() && d.getMonth() === today.getMonth()) {
    return formatTime(ts)
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}

// 课堂模拟角色配色
// 注意：角色名（小明/小红/小刚/小美/课堂状态/管理建议）与
// 后端 ai_prompts.py 中 CLASSROOM_SIMULATION_PROMPT 的输出格式一致
// 若需增减角色或重命名，须同步修改后端 Prompt 和前端此配置
const classroomRoles: Record<string, { color: string; bg: string; emoji: string; label: string }> = {
  '小明': { color: '#2563eb', bg: '#eff6ff', emoji: '', label: '学霸' },
  '小红': { color: '#dc2626', bg: '#fef2f2', emoji: '', label: '积极' },
  '小刚': { color: '#f59e0b', bg: '#fffbeb', emoji: '', label: '调皮' },
  '小美': { color: '#0d9488', bg: '#ecfeff', emoji: '', label: '内向' },
  '课堂状态': { color: '#059669', bg: '#ecfdf5', emoji: '', label: '' },
  '管理建议': { color: '#0891b2', bg: '#ecfeff', emoji: '', label: '' },
}

const isClassroomSimulation = computed(() => {
  return currentSession.value?.settings?.personality === 'classroom_simulation'
})

// HTML 转义，防止 XSS
const escapeHtml = (str: string): string => {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const renderMarkdown = (text: string) => {
  if (!text) return ''
  
  // 先转义 HTML，防止 XSS
  let html = escapeHtml(text)
  
  html = html
    .replace(/【学生】/g, '')
    .replace(/【建议】/g, '\n&gt; **教学建议**：')
  
  // 课堂模拟模式下，渲染多角色标记
  if (isClassroomSimulation.value) {
    for (const [name, style] of Object.entries(classroomRoles)) {
      const regex = new RegExp(`【${name}】`, 'g')
      const tag = style.label 
        ? `<span class="role-tag" style="background:${style.bg};color:${style.color};border:1px solid ${style.color}20"><span class="role-emoji">${style.emoji}</span><span class="role-name">${name}</span><span class="role-label">${style.label}</span></span>`
        : `<span class="role-tag role-tag-info" style="background:${style.bg};color:${style.color};border:1px solid ${style.color}20"><span class="role-emoji">${style.emoji}</span><span class="role-name">${name}</span></span>`
      html = html.replace(regex, `<br>${tag}`)
    }
  }
  
  // Code blocks (转义后反引号仍保留原样)
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>')
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>')
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>')
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>')
  // blockquote: 转义后 > 变成 &gt;
  html = html.replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>')
  html = html.replace(/^\* (.*$)/gim, '<li>$1</li>')
  html = html.replace(/^- (.*$)/gim, '<li>$1</li>')
  html = html.replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
  html = html.replace(/\n/g, '<br>')
  
  return html
}

// 解析 [EVAL]...[/EVAL] 标签
const parseEvalFromMessage = (content: string): { cleaned: string; eval: TeachingEvalScore | null } => {
  const evalRegex = /\[EVAL\]([\s\S]*?)\[\/EVAL\]/
  const match = content.match(evalRegex)
  if (!match) return { cleaned: content, eval: null }

  const cleaned = content.replace(evalRegex, '').trim()
  try {
    const evalData = JSON.parse(match[1].trim())
    return {
      cleaned,
      eval: {
        knowledge: evalData.knowledge ?? 0,
        guidance: evalData.guidance ?? 0,
        adaptability: evalData.adaptability ?? 0,
        control: evalData.control ?? 0,
        tip: evalData.tip ?? '',
      }
    }
  } catch {
    return { cleaned, eval: null }
  }
}

// 检测当前发言者
const detectSpeaker = (content: string) => {
  const names = ['小明', '小红', '小刚', '小美']
  for (const name of names) {
    if (content.includes(`【${name}】`)) {
      activeSpeaker.value = name
    }
  }
}

// 模拟回放
const startReplay = () => {
  if (!currentSession.value) return
  showReplay.value = true
  replayIndex.value = 0
  replayPlaying.value = true
  replayTimer = setInterval(() => {
    if (!currentSession.value) return
    if (replayIndex.value < currentSession.value.messages.length - 1) {
      replayIndex.value++
    } else {
      stopReplay()
    }
  }, 2000)
}

const stopReplay = () => {
  replayPlaying.value = false
  if (replayTimer) {
    clearInterval(replayTimer)
    replayTimer = null
  }
}

const replayMessages = computed(() => {
  if (!currentSession.value) return []
  return currentSession.value.messages.slice(0, replayIndex.value + 1)
})

// 获取某条消息对应的 eval (按消息索引)
const getEvalForReplayMsg = (idx: number): TeachingEvalScore | null => {
  if (idx < evalHistory.value.length) return evalHistory.value[idx]
  return null
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const saveSessionsToLocal = () => {
  if (authStore.user?.id) {
    localStorage.setItem(`chat_sessions_${authStore.user?.id}`, JSON.stringify(sessions.value))
  }
}

// ==================== 语音输入 ====================

const isRecording = ref(false)
const speechSupported = ref(false)
let recognition: any = null

// 检查浏览器语音识别支持
const initSpeechRecognition = () => {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SpeechRecognition) {
    speechSupported.value = false
    return
  }
  speechSupported.value = true
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = false
  recognition.interimResults = true

  recognition.onresult = (event: any) => {
    let transcript = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript
    }
    userInput.value = transcript
  }

  recognition.onend = () => {
    isRecording.value = false
    // 识别结束后如果有内容自动发送
    if (userInput.value.trim()) {
      sendMessage()
    }
  }

  recognition.onerror = (event: any) => {
    isRecording.value = false
    if (event.error === 'not-allowed') {
      ElMessage.warning('请允许浏览器使用麦克风')
    } else if (event.error !== 'aborted') {
      ElMessage.error('语音识别出错，请重试')
    }
  }
}

const toggleVoiceInput = () => {
  if (!speechSupported.value) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用 Chrome')
    return
  }
  if (isRecording.value) {
    recognition?.stop()
    isRecording.value = false
  } else {
    userInput.value = ''
    isRecording.value = true
    recognition?.start()
  }
}

onMounted(() => {
  // 原有逻辑已在上方 onMounted 中
  initSpeechRecognition()
})
</script>

<template>
  <div class="ai-chat-layout">
    <!-- 左侧侧边栏 -->
    <div class="sidebar" :class="{ 'collapsed': !showSidebar }">
      <div class="sidebar-header">
        <div class="sidebar-brand" v-if="showSidebar">
          <el-icon :size="18"><Cpu /></el-icon>
          <span>AI 备课工作台</span>
        </div>
        <el-button class="new-chat-btn" @click="handleCreateNew">
          <el-icon><Plus /></el-icon>
          <span v-if="showSidebar">新建</span>
        </el-button>
      </div>
      
      <div class="history-list" v-if="showSidebar">
        <div class="list-title">历史记录</div>
        <div v-if="sortedSessions.length === 0 && genSortedRecords.length === 0" class="empty-history">
          暂无记录
        </div>
        <div 
          v-for="session in sortedSessions" 
          :key="session.id"
          class="history-item"
          :class="{ active: currentMode === 'chat' && currentSessionId === session.id }"
          @click="switchMode('chat'); selectSession(session.id)"
        >
          <div class="item-content">
            <div class="item-row"><el-tag size="small" type="info" class="item-type-tag">试讲</el-tag><span class="item-title">{{ session.title }}</span></div>
            <span class="item-date">{{ formatDate(session.updatedAt) }}</span>
          </div>
          <el-button class="delete-btn" link type="danger" @click="(e: Event) => deleteSession(session.id, e)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <div 
          v-for="record in genSortedRecords" 
          :key="record.id"
          class="history-item"
          :class="{ active: currentMode === 'generator' && genRecordId === record.id }"
          @click="switchMode('generator'); selectGenRecord(record)"
        >
          <div class="item-content">
            <div class="item-row"><el-tag size="small" type="success" class="item-type-tag">教案</el-tag><span class="item-title">{{ record.title }}</span></div>
            <span class="item-date">{{ formatDate(record.createdAt) }}</span>
          </div>
          <el-button class="delete-btn" link type="danger" @click="(e: Event) => deleteGenRecord(record.id, e)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主区域 -->
    <div class="main-area">
      <!-- 顶部导航 -->
      <div class="chat-navbar">
        <div class="nav-left">
          <el-button text @click="showSidebar = !showSidebar">
            <el-icon>
              <Menu v-if="!showSidebar" />
              <ArrowLeft v-else />
            </el-icon>
          </el-button>
          <div class="session-info">
            <span class="title" v-if="currentMode === 'chat' && currentSession">{{ currentSession.title }}</span>
            <span class="title" v-else-if="currentMode === 'generator' && (genContent || genGenerating)">{{ genInfo?.topic || genForm.topic || '教案生成' }}</span>
            <span class="title" v-else>AI 备课工作台</span>
            <div class="nav-tags" v-if="currentMode === 'chat' && currentSession">
              <el-tag size="small" effect="plain">{{ currentSession.settings.grade }}</el-tag>
              <el-tag size="small" type="warning" effect="dark" v-if="isClassroomSimulation">多角色模拟</el-tag>
            </div>
          </div>
        </div>
        
        <div class="nav-right">
          <el-button v-if="currentMode === 'chat' && currentSession && isClassroomSimulation && sessionMessages.length > 2" @click="startReplay">
            ▶ 模拟回放
          </el-button>
          <el-button v-if="currentMode === 'chat' && currentSession" @click="generateReport" :loading="generatingReport">
            <el-icon class="mr-1"><TrendCharts /></el-icon> 生成报告
          </el-button>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="content-wrapper">
        
        <!-- MODE: CHAT -->
        <template v-if="currentMode === 'chat'">
          <!-- Unified Welcome -->
          <div v-if="!currentSessionId || showSettings" class="welcome-container">
            <div class="welcome-inner">
              <div class="welcome-header">
                <div class="welcome-logo"><el-icon :size="28"><Cpu /></el-icon></div>
                <h2>AI 备课工作台</h2>
                <p>为师范生打造的智能备课助手，帮你生成教案、模拟试讲</p>
              </div>

              <!-- 两个工作流入口 -->
              <div class="action-cards">
                <div class="action-card" @click="switchMode('generator')">
                  <div class="action-icon" style="background:#ecfdf5;color:#10b981"><el-icon :size="22"><MagicStick /></el-icon></div>
                  <div class="action-info">
                    <div class="action-title">生成教案</div>
                    <div class="action-desc">AI 帮你快速生成专业教案，支持多种模板和自定义</div>
                  </div>
                  <el-icon class="action-arrow"><ArrowRight /></el-icon>
                </div>
                <div class="action-card" @click="showConfigDialog = true">
                  <div class="action-icon" style="background:#ecfeff;color:#0891b2"><el-icon :size="22"><ChatDotRound /></el-icon></div>
                  <div class="action-info">
                    <div class="action-title">模拟试讲</div>
                    <div class="action-desc">AI 模拟学生提问互动，帮你练习课堂教学技能</div>
                  </div>
                  <el-icon class="action-arrow"><ArrowRight /></el-icon>
                </div>
              </div>

              <!-- 快速开始 -->
              <div class="quick-starts">
                <div class="quick-starts-label">快速开始</div>
                <div class="quick-starts-list">
                  <div v-for="tpl in quickTemplates" :key="tpl.topic" class="quick-start-chip" @click="quickStartGen(tpl)">
                    <el-icon><component :is="tpl.icon" /></el-icon>
                    <span>{{ tpl.topic }} · {{ tpl.subject }}</span>
                  </div>
                </div>
              </div>

              <!-- 场景预设 -->
              <div class="quick-starts">
                <div class="quick-starts-label">试讲场景</div>
                <div class="preset-grid">
                  <div v-for="preset in scenePresets" :key="preset.name" class="preset-card" @click="applyPreset(preset); showConfigDialog = true">
                    <div class="preset-name">{{ preset.name }}</div>
                    <div class="preset-desc">{{ preset.desc }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Interface -->
          <div v-else class="chat-and-eval-wrapper">
            <!-- 虚拟教室头像栏 (课堂模拟模式) -->
            <div v-if="isClassroomSimulation" class="virtual-classroom-bar">
              <div class="vcb-label">虚拟教室</div>
              <div class="vcb-students">
                <div
                  v-for="(style, name) in classroomRoles"
                  :key="name"
                  v-show="style.label"
                  class="vcb-student"
                  :class="{ active: activeSpeaker === name }"
                  :style="{ borderColor: activeSpeaker === name ? style.color : 'transparent' }"
                >
                  <div class="vcb-avatar" :style="{ background: style.bg }">
                    <span class="vcb-emoji">{{ style.emoji }}</span>
                    <span v-if="activeSpeaker === name" class="vcb-hand">✋</span>
                  </div>
                  <div class="vcb-name" :style="{ color: style.color }">{{ name }}</div>
                  <div class="vcb-trait">{{ style.label }}</div>
                </div>
              </div>
            </div>

            <div class="chat-eval-layout">
              <div class="chat-container" ref="chatContainer">
                <div class="chat-messages">
              <div 
                v-for="msg in sessionMessages" 
                :key="msg.id"
                class="message-row"
                :class="msg.role"
              >
                <div class="avatar">
                  <div class="avatar-img" :class="msg.role">
                    <el-icon v-if="msg.role === 'assistant'"><Service /></el-icon>
                    <el-icon v-else><User /></el-icon>
                  </div>
                </div>
                <div class="bubble-wrapper">
                  <div class="bubble">
                    <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                    <div class="typing-cursor" v-if="lastSessionMessage && msg.id === lastSessionMessage.id && isGenerating && msg.role === 'assistant'"></div>
                  </div>
                  <span class="time">{{ formatTime(msg.timestamp) }}</span>
                </div>
              </div>
              
              <div class="message-row assistant" v-if="isGenerating && lastSessionMessage?.role === 'user'">
                 <div class="avatar">
                   <div class="avatar-img assistant">
                     <el-icon><Service /></el-icon>
                   </div>
                 </div>
                 <div class="bubble-wrapper">
                   <div class="bubble thinking-bubble">
                     <div class="thinking-header">
                       <el-icon class="thinking-brain" :size="20"><Cpu /></el-icon>
                       <span class="thinking-text">AI 正在思考</span>
                     </div>
                     <div class="thinking-bar">
                       <div class="thinking-fill"></div>
                     </div>
                   </div>
                 </div>
              </div>
            </div>
          </div>

          <!-- 实时教学评分面板 (课堂模拟模式) -->
          <div v-if="isClassroomSimulation && evalScores.knowledge > 0" class="eval-sidebar">
            <div class="eval-title">
              <span></span> AI 教学评分 <span class="eval-live">实时</span>
            </div>
            <div class="eval-grid">
              <div class="eval-item">
                <div class="eval-item-label">知识准确性</div>
                <el-progress :percentage="evalScores.knowledge" :stroke-width="10" :color="evalScores.knowledge >= 80 ? '#10b981' : '#f59e0b'" />
                <div class="eval-item-val">{{ evalScores.knowledge }}/100</div>
              </div>
              <div class="eval-item">
                <div class="eval-item-label">引导能力</div>
                <el-progress :percentage="evalScores.guidance" :stroke-width="10" :color="evalScores.guidance >= 80 ? '#10b981' : '#f59e0b'" />
                <div class="eval-item-val">{{ evalScores.guidance }}/100</div>
              </div>
              <div class="eval-item">
                <div class="eval-item-label">应变能力</div>
                <el-progress :percentage="evalScores.adaptability" :stroke-width="10" :color="evalScores.adaptability >= 80 ? '#10b981' : '#f59e0b'" />
                <div class="eval-item-val">{{ evalScores.adaptability }}/100</div>
              </div>
              <div class="eval-item">
                <div class="eval-item-label">课堂把控</div>
                <el-progress :percentage="evalScores.control" :stroke-width="10" :color="evalScores.control >= 80 ? '#10b981' : '#f59e0b'" />
                <div class="eval-item-val">{{ evalScores.control }}/100</div>
              </div>
            </div>
            <div v-if="evalScores.tip" class="eval-tip">
              <span class="eval-tip-icon"></span>
              <span>{{ evalScores.tip }}</span>
            </div>
          </div>
        </div>
      </div>

          <!-- Input Area -->
          <div class="input-area" v-if="currentSessionId && !showSettings">
            <!-- 录音状态指示 -->
            <div v-if="isRecording" class="voice-indicator">
              <div class="voice-waves">
                <span class="wave w1"></span>
                <span class="wave w2"></span>
                <span class="wave w3"></span>
                <span class="wave w4"></span>
                <span class="wave w5"></span>
              </div>
              <span class="voice-text">正在聆听...</span>
              <el-button size="small" type="danger" round @click="toggleVoiceInput">停止</el-button>
            </div>
            <div class="input-wrapper">
              <textarea 
                ref="inputRef"
                v-model="userInput" 
                placeholder="输入你的回答..."
                @keydown="handleKeydown"
                rows="1"
              ></textarea>
              <!-- 语音输入按钮 -->
              <el-button 
                v-if="speechSupported" 
                circle 
                :type="isRecording ? 'danger' : 'default'"
                :class="{ 'voice-btn-active': isRecording }"
                @click="toggleVoiceInput"
                class="voice-btn"
              >
                <span class="voice-icon"></span>
              </el-button>
              <el-button type="primary" circle @click="sendMessage" :disabled="!userInput.trim() || isGenerating">
                <el-icon><component :is="isGenerating ? 'Loading' : 'Top'" /></el-icon>
              </el-button>
            </div>
            <div class="input-tip">按 Enter 发送，Shift + Enter 换行{{ speechSupported ? '，点击麦克风语音输入' : '' }}</div>
          </div>
        </template>

        <!-- MODE: GENERATOR -->
        <template v-else>
          <!-- Generator Result -->
          <div v-if="genContent || genGenerating" class="result-view" ref="contentRef">
            <div class="result-toolbar">
              <div class="info">
                <el-button @click="createGenSession" circle :disabled="genGenerating">
                  <el-icon><MagicStick /></el-icon>
                </el-button>
                <div class="meta-group">
                  <span class="title">{{ genForm.topic || '未命名教案' }}</span>
                  <span class="meta">{{ genForm.subject }} · {{ genForm.grade }} · {{ currentTemplateLabel }}</span>
                </div>
              </div>
              <div class="actions" v-if="!genGenerating && genContent">
                <el-button @click="copyGenContent" :disabled="!wordReady">
                  <el-icon class="mr-1"><CopyDocument /></el-icon>
                  复制
                </el-button>
                <el-button type="primary" @click="downloadGenContent" :disabled="!wordReady">
                  <el-icon class="mr-1"><Download /></el-icon>
                  下载 Word
                </el-button>
              </div>
            </div>

            <!-- Generating State -->
            <div class="loading-state" v-if="genGenerating">
              <el-progress type="dashboard" :percentage="Math.floor(genProgress)" :width="120" />
              <h3>正在生成教案...</h3>
              <p>{{ genInfo?.subject || genForm.subject }} · {{ genInfo?.grade || genForm.grade }} · {{ genInfo?.topic || genForm.topic }}</p>
              <p class="hint">AI 正在根据你的要求撰写教案，请稍候</p>
            </div>

            <!-- Result -->
            <div class="result-content" v-else>
              <LessonWordPreview ref="wordPreview" flow :content="genContent" :title="genForm.topic || '教案'"
                :lesson-id="genCurrentRecord?.lessonId" :document-id="genCurrentRecord?.documentId"
                @ready="wordReady = $event" @document-created="saveGenDocument" />
              <LessonMatchedResources v-if="genCurrentRecord?.resourceLessonId || genCurrentRecord?.lessonId"
                :key="genCurrentRecord.id" :resource-lesson-id="genCurrentRecord.resourceLessonId" :lesson-id="genCurrentRecord.lessonId" />
            </div>
          </div>

          <!-- Generator Form - Clean Single Column -->
          <div v-else class="gen-form-view">
            <div class="gen-form-inner">
              <div class="nb-ws-header">
                <h2>AI 教案生成</h2>
                <p>填写课题信息，AI 将智能生成专业教案</p>
              </div>

              <!-- Quick Fill Chips -->
              <div class="gen-inline-section">
                <span class="gen-inline-label">快捷填充</span>
                <div class="gen-chip-row">
                  <span v-for="tpl in quickTemplates" :key="tpl.topic" class="scenario-chip" @click="useQuickTemplate(tpl)">
                    <el-icon><component :is="tpl.icon" /></el-icon> {{ tpl.topic }}
                  </span>
                </div>
              </div>

              <!-- Config Grid -->
              <div class="cfg-grid" style="margin-bottom:20px">
                <div class="cfg-item">
                  <div class="cfg-label">科目</div>
                  <el-select v-model="genForm.subject" placeholder="选择科目" class="w-full">
                    <el-option v-for="sub in subjectOptions" :key="sub" :value="sub" :label="sub" />
                  </el-select>
                </div>
                <div class="cfg-item">
                  <div class="cfg-label">学段</div>
                  <el-select v-model="genForm.grade" placeholder="选择学段" class="w-full">
                    <el-option v-for="g in generatorStages" :key="g" :value="g" :label="g" />
                  </el-select>
                </div>
                <div class="cfg-item">
                  <div class="cfg-label">时长</div>
                  <el-select v-model="genForm.duration" class="w-full">
                    <el-option v-for="d in durationOptions" :key="d" :value="d" :label="`${d}分钟`" />
                  </el-select>
                </div>
              </div>

              <!-- Topic -->
              <div class="nb-field">
                <div class="cfg-label">课题名称</div>
                <el-input v-model="genForm.topic" placeholder="例如：草原、三角形内角和" size="large" />
              </div>

              <!-- Key Points -->
              <div class="nb-points">
                <div class="nb-point-col">
                  <div class="cfg-label">教学重点（可选）</div>
                  <el-input v-model="genForm.key_point" type="textarea" :rows="2" placeholder="输入教学重点" />
                </div>
                <div class="nb-point-col">
                  <div class="cfg-label">教学难点（可选）</div>
                  <el-input v-model="genForm.difficulty" type="textarea" :rows="2" placeholder="输入教学难点" />
                </div>
              </div>

              <!-- Template + Model Row -->
              <div class="gen-inline-section">
                <span class="gen-inline-label">教案模板</span>
                <div class="gen-chip-row">
                  <span v-for="tpl in BUILTIN_TEMPLATES" :key="tpl.value" class="scenario-chip" :class="{ active: genTemplate === tpl.value }" @click="genStore.setTemplate(tpl.value)">
                    {{ tpl.label }}
                  </span>
                </div>
              </div>

              <!-- Upload custom template (only when custom selected) -->
              <div v-if="genTemplate === 'custom'" class="gen-upload-row">
                <el-upload drag action="#" :auto-upload="false" :show-file-list="false" :on-change="handleGenTemplateUpload" class="upload-area">
                  <div v-if="!genCustomFile" style="padding:12px;text-align:center;color:#64748b;font-size:13px">
                    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                    <div>上传自定义模板</div>
                  </div>
                  <div v-else class="file-info">
                    <el-icon><Document /></el-icon>
                    <span>{{ genCustomFile }}</span>
                    <el-tag size="small" type="success">已解析</el-tag>
                  </div>
                </el-upload>
              </div>

              <!-- AI Model (compact) -->
              <div class="gen-inline-section">
                <span class="gen-inline-label">AI 模型</span>
                <el-select v-model="genForm.modelId" placeholder="自动选择" style="width:200px">
                  <el-option v-for="model in availableModels" :key="model.id" :label="model.name" :value="model.id">
                    <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
                      <span>{{ model.name }}</span>
                      <span style="color:var(--el-text-color-secondary);font-size:12px">{{ model.provider }}</span>
                    </div>
                  </el-option>
                </el-select>
              </div>

              <!-- Generate -->
              <p v-if="genGenerationHint" role="status" style="color:#64748b;font-size:13px">{{ genGenerationHint }}</p>
              <el-button type="primary" size="large" :loading="genGenerating" :disabled="!genCanGenerate" @click="generateLessonPlan" class="nb-generate-btn">
                <el-icon class="mr-1" v-if="!genGenerating"><MagicStick /></el-icon>
                {{ genGenerating ? '正在生成...' : '生成教案' }}
              </el-button>
            </div>
          </div>
        </template>

      </div>
    </div>

    <!-- 模拟回放弹窗 -->
    <el-dialog v-model="showReplay" title="课堂模拟回放" width="700px" @close="stopReplay">
      <div class="replay-container">
        <div class="replay-messages">
          <div
            v-for="(msg, idx) in replayMessages"
            :key="msg.id"
            class="replay-msg"
            :class="msg.role"
          >
            <div class="replay-role">{{ msg.role === 'user' ? '👩‍🏫 教师' : '🎒 学生' }}</div>
            <div class="replay-content" v-html="renderMarkdown(parseEvalFromMessage(msg.content).cleaned)"></div>
            <div v-if="msg.role === 'assistant' && getEvalForReplayMsg(idx)" class="replay-eval-badge">
              评分: {{ Math.round(((getEvalForReplayMsg(idx)?.knowledge || 0) + (getEvalForReplayMsg(idx)?.guidance || 0) + (getEvalForReplayMsg(idx)?.adaptability || 0) + (getEvalForReplayMsg(idx)?.control || 0)) / 4) }}
            </div>
          </div>
        </div>
        <div class="replay-progress">
          <el-progress :percentage="currentSession ? Math.round((replayIndex / Math.max(1, currentSession.messages.length - 1)) * 100) : 0" :stroke-width="6" />
          <div class="replay-controls">
            <el-button size="small" :type="replayPlaying ? 'danger' : 'primary'" @click="replayPlaying ? stopReplay() : startReplay()">
              {{ replayPlaying ? '暂停' : '播放' }}
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 报告弹窗 -->
    <el-dialog v-model="showReport" title="练习报告" width="600px" custom-class="report-dialog">
      <div v-if="currentSession?.report" class="report-content">
        <div class="report-score" :class="currentSession.report.response_quality">
          <div class="score-label">整体表现</div>
          <div class="score-val">{{ currentSession.report.response_quality === 'excellent' ? '优秀' : currentSession.report.response_quality === 'good' ? '良好' : '需改进' }}</div>
        </div>
        <div class="report-summary">{{ currentSession.report.overall_comment }}</div>
        
        <div class="report-section" v-if="currentSession.report.strengths.length">
          <h4>✅ 亮点</h4>
          <ul><li v-for="s in currentSession.report.strengths" :key="s">{{ s }}</li></ul>
        </div>
        
        <div class="report-section" v-if="currentSession.report.suggestions.length">
          <h4>建议</h4>
          <ul><li v-for="s in currentSession.report.suggestions" :key="s">{{ s }}</li></ul>
        </div>
      </div>
    </el-dialog>

    <!-- 试讲配置弹窗 -->
    <el-dialog v-model="showConfigDialog" title="模拟试讲配置" width="640px" :close-on-click-modal="false">
      <div class="config-dialog-body">
        <!-- 教案来源 -->
        <div class="cfg-section">
          <div class="cfg-title">教案来源</div>
          <div class="source-tabs">
            <button class="source-tab" :class="{ active: currentSettings.source === 'submission' }" @click="currentSettings.source = 'submission'">
              <el-icon><Document /></el-icon> 已提交作业
            </button>
            <button class="source-tab" :class="{ active: currentSettings.source === 'upload' }" @click="currentSettings.source = 'upload'">
              <el-icon><Upload /></el-icon> 上传文件
            </button>
          </div>
          <div v-if="currentSettings.source === 'submission'" class="cfg-field">
            <el-select v-model="currentSettings.submissionId" placeholder="选择教案" class="w-full" size="large" @change="handleSubmissionChange">
              <el-option v-for="sub in submissions" :key="sub.id" :label="sub.task?.title || sub.lesson_plan_name" :value="sub.id" />
            </el-select>
          </div>
          <div v-else class="cfg-field">
            <el-upload class="upload-area" drag action="#" :auto-upload="false" :show-file-list="false" :on-change="handleFileUpload">
              <el-icon class="el-icon--upload" v-if="!currentSettings.filename"><upload-filled /></el-icon>
              <div class="el-upload__text" v-if="!currentSettings.filename">拖拽或点击上传 PDF / Word</div>
              <div class="file-info" v-else>
                <el-icon><Document /></el-icon>
                <span>{{ currentSettings.filename }}</span>
                <el-tag size="small" type="success">已解析</el-tag>
              </div>
            </el-upload>
          </div>
        </div>
        <!-- 场景配置 -->
        <div class="cfg-section">
          <div class="cfg-title">场景配置</div>
          <div class="cfg-grid">
            <div class="cfg-item">
              <div class="cfg-label">模拟年级</div>
              <el-select v-model="currentSettings.grade" class="w-full">
                <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">学生性格</div>
              <el-select v-model="currentSettings.personality" class="w-full">
                <el-option v-for="p in personalityOptions" :key="p.value" :label="p.label" :value="p.value">
                  <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
                    <span>{{ p.label }}</span>
                    <span style="color:var(--el-text-color-secondary);font-size:12px">{{ p.desc }}</span>
                  </div>
                </el-option>
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">教学方法</div>
              <el-select v-model="currentSettings.teachingMethod" class="w-full">
                <el-option v-for="m in teachingMethodOptions" :key="m.value" :label="m.label" :value="m.value" />
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">班级规模</div>
              <el-select v-model="currentSettings.studentCount" class="w-full">
                <el-option v-for="s in studentCountOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">教学重点</div>
              <el-select v-model="currentSettings.focusArea" class="w-full">
                <el-option v-for="f in focusAreaOptions" :key="f.value" :label="f.label" :value="f.value" />
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">AI 模型</div>
              <el-select v-model="currentSettings.modelId" placeholder="自动选择" class="w-full">
                <el-option v-for="model in availableModels" :key="model.id" :label="model.name" :value="model.id" />
              </el-select>
            </div>
          </div>
        </div>
        <!-- 高级配置 -->
        <div class="adv-toggle" @click="showAdvancedConfig = !showAdvancedConfig">
          <el-icon><Setting /></el-icon>
          <span>高级配置</span>
          <el-icon class="adv-arrow" :class="{ open: showAdvancedConfig }"><ArrowRight /></el-icon>
        </div>
        <div v-show="showAdvancedConfig" class="adv-config">
          <div class="cfg-grid">
            <div class="cfg-item">
              <div class="cfg-label">互动方式</div>
              <el-select v-model="currentSettings.interactionStyle" class="w-full">
                <el-option v-for="s in interactionStyleOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </div>
            <div class="cfg-item">
              <div class="cfg-label">难度级别</div>
              <el-select v-model="currentSettings.difficultyLevel" class="w-full">
                <el-option v-for="d in difficultyLevelOptions" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showConfigDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!canStartChat" :loading="aiLoading" @click="startPracticeFromDialog">
          开始试讲
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ai-chat-layout {
  display: flex;
  height: calc(100vh - 84px);
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  border: 1px solid #f3f4f6;
  margin: -12px;
}

/* Sidebar */
.sidebar {
  width: 260px;
  background: #f8fafc;
  border-right: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 64px;
  overflow: hidden;
}

.sidebar.collapsed .sidebar-header {
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.sidebar.collapsed .new-chat-btn {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 10px;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-brand .el-icon {
  color: #0891b2;
  flex-shrink: 0;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.item-type-tag {
  flex-shrink: 0;
  font-size: 10px !important;
  padding: 0 6px !important;
  height: 18px !important;
  line-height: 18px !important;
}

.new-chat-btn {
  width: 100%;
  background: #0891b2;
  border: none;
  color: white;
  height: 44px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 2px 4px rgba(8, 145, 178, 0.15);
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background: #0e7490;
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(8, 145, 178, 0.2);
}

/* History List */
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 12px 16px;
}

/* ... (keep existing history styles) ... */

/* Generator Form View (single column) */
.gen-form-view {
  flex: 1;
  overflow-y: auto;
  padding: 32px 24px;
  background: #f8fafc;
  display: flex;
  justify-content: center;
}

.gen-form-inner {
  width: 100%;
  max-width: 640px;
  background: white;
  border-radius: 16px;
  padding: 28px 32px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  align-self: flex-start;
}

.gen-inline-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.gen-inline-label {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  white-space: nowrap;
}

.gen-chip-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.gen-upload-row {
  margin-bottom: 16px;
}

/* Scenario chips (shared) */
.scenario-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 14px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.scenario-chip:hover {
  border-color: #10b981;
  color: #10b981;
  background: #f0fdf4;
}

.scenario-chip.active {
  border-color: #10b981;
  color: white;
  background: #10b981;
}

.nb-ws-header {
  margin-bottom: 24px;
}

.nb-ws-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px;
}

.nb-ws-header p {
  color: #94a3b8;
  font-size: 14px;
  margin: 0;
}

.nb-field {
  margin-bottom: 20px;
}

.nb-points {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.nb-point-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nb-generate-btn {
  width: 100%;
  height: 48px;
  background: #10b981;
  border: none;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px;
  box-shadow: 0 4px 6px rgba(16, 185, 129, 0.15);
  transition: all 0.2s;
}

.nb-generate-btn:hover {
  background: #059669;
  transform: translateY(-1px);
  box-shadow: 0 6px 8px rgba(16, 185, 129, 0.2);
}

/* Config Dialog */
.config-dialog-body {
  max-height: 60vh;
  overflow-y: auto;
  padding: 0 4px;
}

.config-dialog-body .cfg-grid {
  grid-template-columns: 1fr 1fr;
}

/* Keep old utility classes */
.flex-1 { flex: 1; }
.w-100 { width: 140px; }

/* Result View */
.result-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;
}

.result-toolbar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: #ffffff;
  border-bottom: 1px solid #f1f5f9;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
  z-index: 10;
}

.result-toolbar .info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.meta-group {
  display: flex;
  flex-direction: column;
}

.meta-group .title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.meta-group .meta {
  font-size: 12px;
  color: #64748b;
}

.result-toolbar .actions {
  display: flex;
  gap: 12px;
}

.result-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  width: 100%;
}

.result-content .markdown-body {
  max-width: 800px;
  margin: 0 auto;
}

/* Loading State */
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #fff;
}

.loading-state h3 {
  font-size: 22px;
  color: #1e293b;
  margin: 24px 0 12px;
  font-weight: 700;
}

.loading-state p {
  color: #64748b;
  margin: 0;
  font-size: 16px;
}

.loading-state .hint {
  margin-top: 8px;
  font-size: 14px;
  color: #94a3b8;
}

/* Common Styles */
.w-full { width: 100%; }
.mt-3 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }


.list-title {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 12px;
  padding-left: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.empty-history {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 32px 0;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 2px;
  border: 1px solid transparent;
  color: #334155;
}

.history-item:hover {
  background: #ffffff;
  border-color: #e2e8f0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.history-item.active {
  background: #ecfeff;
  border-color: #cffafe;
  color: #0891b2;
}

.item-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  margin-right: 8px;
}

.item-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-date {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.delete-btn {
  display: none;
  padding: 6px;
  height: auto;
  color: #ef4444;
}

.history-item:hover .delete-btn {
  display: inline-flex;
}

.delete-btn:hover {
  background: #fee2e2;
  border-radius: 4px;
}

/* Main Area */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  overflow: hidden;
}

.chat-navbar {
  height: 56px;
  min-height: 56px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background: white;
  z-index: 10;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-info .title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  background: #ffffff;
}

/* Welcome Container */
.welcome-container {
  flex: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 24px;
  overflow-y: auto;
  background: #f8fafc;
}

.welcome-inner {
  width: 100%;
  max-width: 600px;
  margin-top: auto;
  margin-bottom: auto;
  padding: 0 16px;
}

/* Action Cards */
.action-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 28px;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s ease;
}

.action-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.07);
  transform: translateY(-3px);
}

.action-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-info {
  flex: 1;
}

.action-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 3px;
}

.action-desc {
  font-size: 13px;
  color: #94a3b8;
}

.action-arrow {
  color: #cbd5e1;
  font-size: 16px;
  flex-shrink: 0;
}

/* Quick Starts */
.quick-starts {
  margin-bottom: 20px;
}

.quick-starts-label {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 10px;
}

.quick-starts-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-start-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: white;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-start-chip:hover {
  border-color: #10b981;
  color: #10b981;
  background: #f0fdf4;
}

.quick-start-chip .el-icon {
  font-size: 14px;
}

.welcome-header {
  text-align: center;
  margin-bottom: 28px;
}

.welcome-logo {
  width: 52px;
  height: 52px;
  background: #ecfeff;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  color: #0891b2;
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.12);
}

.welcome-header h2 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #0f172a;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.welcome-header p {
  margin: 0;
  color: #94a3b8;
  font-size: 14px;
  line-height: 1.5;
}

/* Config Sections */
.cfg-section {
  margin-bottom: 20px;
}

.cfg-title {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cfg-field {
  margin-top: 10px;
}

/* Source Tabs */
.source-tabs {
  display: flex;
  gap: 8px;
}

.source-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.source-tab:hover {
  border-color: #0891b2;
  color: #0891b2;
  background: #ecfeff;
}

.source-tab.active {
  border-color: #0891b2;
  color: #0891b2;
  background: #ecfeff;
  box-shadow: 0 0 0 1px #0891b2;
}

/* Config Grid */
.cfg-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}

.cfg-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cfg-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

/* Advanced Config Toggle */
.adv-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  margin-bottom: 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  transition: color 0.2s;
  user-select: none;
}

.adv-toggle:hover {
  color: #0891b2;
}

.adv-arrow {
  margin-left: auto;
  font-size: 12px;
  transition: transform 0.2s;
}

.adv-arrow.open {
  transform: rotate(90deg);
}

.adv-config {
  margin-bottom: 16px;
  padding: 12px 0;
}

/* Scene Presets */
.preset-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.preset-card {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.preset-card:hover {
  border-color: #0891b2;
  background: #ecfeff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.08);
}

.preset-name {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 2px;
}

.preset-card:hover .preset-name {
  color: #0891b2;
}

.preset-desc {
  font-size: 11px;
  color: #94a3b8;
}

/* Upload Area */
.upload-area {
  width: 100%;
}
.upload-area :deep(.el-upload-dragger) {
  padding: 24px;
  border-radius: 10px;
  border: 2px dashed #e2e8f0;
  background: #f8fafc;
  transition: all 0.2s;
}
.upload-area :deep(.el-upload-dragger:hover) {
  border-color: #0891b2;
  background: #ecfeff;
}

.file-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #334155;
}

.start-btn {
  width: 100%;
  background: #0891b2;
  border: none;
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px;
  transition: all 0.2s;
  box-shadow: 0 4px 6px rgba(8, 145, 178, 0.15);
}

.start-btn:hover {
  background: #0e7490;
  transform: translateY(-1px);
  box-shadow: 0 6px 8px rgba(8, 145, 178, 0.25);
}

/* Chat Messages */
.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  scroll-behavior: smooth;
  background: #ffffff;
}

.chat-messages {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 20px;
}

.message-row {
  display: flex;
  gap: 16px;
  margin-bottom: 32px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
}

.avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.avatar-img.assistant {
  background: #f0fdf4;
  color: #16a34a;
}

.avatar-img.user {
  background: #eff6ff;
  color: #3b82f6;
}

.bubble-wrapper {
  max-width: 80%;
  display: flex;
  flex-direction: column;
}

.message-row.user .bubble-wrapper {
  align-items: flex-end;
}

.bubble {
  background: #f8fafc;
  padding: 16px 20px;
  border-radius: 16px;
  border-top-left-radius: 4px;
  font-size: 15px;
  line-height: 1.7;
  color: #1e293b;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  border: 1px solid #f1f5f9;
}

.message-row.user .bubble {
  background: #1e293b;
  color: white;
  border-radius: 16px;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);
  border: none;
}

.time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
}

/* Typing indicator */
.typing-cursor {
  display: inline-block;
  width: 6px;
  height: 14px;
  background: #0891b2;
  margin-left: 4px;
  vertical-align: middle;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* AI Thinking animation */
.thinking-bubble {
  background: #ecfeff !important;
  border-color: #cffafe !important;
  padding: 16px 20px !important;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.thinking-brain {
  font-size: 18px;
  animation: brain-bob 1.5s ease-in-out infinite;
}

@keyframes brain-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

.thinking-text {
  font-size: 13px;
  font-weight: 600;
  color: #0891b2;
  animation: think-fade 1.5s infinite;
}

@keyframes think-fade {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.thinking-bar {
  height: 4px;
  background: #cffafe;
  border-radius: 4px;
  overflow: hidden;
}

.thinking-fill {
  height: 100%;
  width: 30%;
  background: #0891b2;
  border-radius: 4px;
  animation: thinking-slide 1.5s ease-in-out infinite;
}

@keyframes thinking-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

/* Message fade-in animation */
.message-row {
  animation: msg-fade-in 0.3s ease-out;
}

@keyframes msg-fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* AI Powered tag */
.ai-powered-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 5px 14px;
  background: #cffafe;
  border-radius: 16px;
  font-size: 11px;
  font-weight: 600;
  color: #0891b2;
}

.powered-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
  animation: p-blink 2s infinite;
}

@keyframes p-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Code block styles */
.markdown-body :deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(.inline-code) {
  background: #f1f5f9;
  color: #0891b2;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.message-row.user .markdown-body :deep(.inline-code) {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

/* Input Area */
.input-area {
  padding: 24px;
  background: white;
  border-top: 1px solid #f1f5f9;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  position: relative;
  background: #f8fafc;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 8px;
  display: flex;
  align-items: flex-end;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.input-wrapper:focus-within {
  border-color: #0891b2;
  box-shadow: 0 0 0 3px rgba(8, 145, 178, 0.1);
  background: white;
}

.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  padding: 12px 16px;
  font-size: 15px;
  color: #1e293b;
  resize: none;
  outline: none;
  max-height: 120px;
  line-height: 1.5;
}

.input-wrapper textarea::placeholder {
  color: #94a3b8;
}

.input-wrapper .el-button {
  margin: 4px;
  height: 36px;
  width: 36px;
  flex-shrink: 0;
}

.input-tip {
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 12px;
}

/* Report Styles */
.report-content {
  padding: 8px;
}

.report-score {
  text-align: center;
  padding: 24px;
  border-radius: 16px;
  margin-bottom: 24px;
}

.report-score.excellent { background: #f0fdf4; color: #166534; }
.report-score.good { background: #eff6ff; color: #1e40af; }
.report-score.poor { background: #fef2f2; color: #991b1b; }

.score-label {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.8;
  margin-bottom: 8px;
}

.score-val {
  font-size: 28px;
  font-weight: 800;
}

.report-summary {
  font-size: 15px;
  line-height: 1.6;
  color: #334155;
  margin-bottom: 24px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #f1f5f9;
}

.report-section {
  margin-bottom: 24px;
}

.report-section h4 {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.report-section ul {
  padding-left: 20px;
}

.report-section li {
  margin-bottom: 8px;
  color: #475569;
  line-height: 1.5;
}

/* Markdown styling within messages */
.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid #e2e8f0;
  padding-left: 12px;
  color: #64748b;
  margin: 12px 0;
}

.message-row.user .markdown-body :deep(blockquote) {
  border-left-color: rgba(255,255,255,0.3);
  color: rgba(255,255,255,0.9);
}

/* 语音输入 */
.voice-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  margin-bottom: 12px;
  animation: voice-fade-in 0.3s ease;
}

@keyframes voice-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.voice-waves {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 24px;
}

.wave {
  width: 3px;
  background: #ef4444;
  border-radius: 3px;
  animation: wave-bounce 1s ease-in-out infinite;
}

.w1 { height: 8px; animation-delay: 0s; }
.w2 { height: 16px; animation-delay: 0.1s; }
.w3 { height: 24px; animation-delay: 0.2s; }
.w4 { height: 16px; animation-delay: 0.3s; }
.w5 { height: 8px; animation-delay: 0.4s; }

@keyframes wave-bounce {
  0%, 100% { transform: scaleY(0.4); }
  50% { transform: scaleY(1); }
}

.voice-text {
  font-size: 13px;
  font-weight: 600;
  color: #dc2626;
}

.voice-btn {
  margin: 4px;
  height: 36px;
  width: 36px;
  flex-shrink: 0;
}

.voice-btn-active {
  animation: voice-pulse 1.5s infinite;
}

@keyframes voice-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}

.voice-icon {
  font-size: 16px;
}

.w-full { width: 100%; }
.mt-3 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }

/* Nav tags */
.nav-tags {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* Classroom simulation role tags */
.markdown-body :deep(.role-tag) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  margin: 4px 0;
  line-height: 1.8;
}

.markdown-body :deep(.role-tag-info) {
  padding: 4px 12px;
  border-radius: 8px;
  margin-top: 8px;
}

.markdown-body :deep(.role-emoji) {
  font-size: 14px;
}

.markdown-body :deep(.role-name) {
  font-weight: 700;
}

.markdown-body :deep(.role-label) {
  font-size: 11px;
  opacity: 0.7;
  margin-left: 2px;
}

/* ==================== Chat + Eval Layout ==================== */
.chat-and-eval-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-eval-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.chat-eval-layout .chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  scroll-behavior: smooth;
  background: #ffffff;
}

/* ==================== Virtual Classroom Bar ==================== */
.virtual-classroom-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  background: #ecfeff;
  border-bottom: 1px solid #d1fae5;
  flex-shrink: 0;
}

.vcb-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  white-space: nowrap;
}

.vcb-students {
  display: flex;
  gap: 20px;
}

.vcb-student {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px;
  border-radius: 12px;
  border: 2px solid transparent;
  transition: all 0.3s;
}

.vcb-student.active {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.vcb-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.vcb-emoji {
  font-size: 22px;
}

.vcb-hand {
  position: absolute;
  top: -6px;
  right: -6px;
  font-size: 14px;
  animation: hand-wave 1s ease-in-out infinite;
}

@keyframes hand-wave {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(20deg); }
  50% { transform: rotate(-10deg); }
  75% { transform: rotate(15deg); }
}

.vcb-name {
  font-size: 12px;
  font-weight: 700;
}

.vcb-trait {
  font-size: 10px;
  color: #94a3b8;
}

/* ==================== Eval Sidebar ==================== */
.eval-sidebar {
  width: 260px;
  border-left: 1px solid #f1f5f9;
  padding: 20px;
  overflow-y: auto;
  flex-shrink: 0;
  background: #fafbfc;
}

.eval-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 20px;
}

.eval-live {
  font-size: 10px;
  font-weight: 600;
  color: #10b981;
  background: #ecfdf5;
  padding: 2px 8px;
  border-radius: 8px;
  margin-left: auto;
  animation: eval-pulse 2s infinite;
}

@keyframes eval-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.eval-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.eval-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eval-item-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.eval-item-val {
  font-size: 11px;
  font-weight: 700;
  color: #334155;
  text-align: right;
}

.eval-tip {
  margin-top: 20px;
  padding: 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  font-size: 12px;
  color: #92400e;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  line-height: 1.5;
}

.eval-tip-icon {
  font-size: 16px;
  flex-shrink: 0;
}

/* ==================== Replay ==================== */
.replay-container {
  max-height: 500px;
  display: flex;
  flex-direction: column;
}

.replay-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  max-height: 400px;
}

.replay-msg {
  padding: 10px 16px;
  margin-bottom: 8px;
  border-radius: 10px;
  animation: replay-fade 0.5s ease;
}

.replay-msg.user {
  background: #eff6ff;
  border-left: 3px solid #3b82f6;
}

.replay-msg.assistant {
  background: #f0fdf4;
  border-left: 3px solid #10b981;
}

.replay-role {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
  color: #64748b;
}

.replay-content {
  font-size: 14px;
  color: #334155;
  line-height: 1.6;
}

.replay-eval-badge {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 10px;
  background: #cffafe;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #0891b2;
}

@keyframes replay-fade {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.replay-progress {
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  margin-top: 12px;
}

.replay-controls {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

/* (personality cards removed - now using dropdown) */
</style>
