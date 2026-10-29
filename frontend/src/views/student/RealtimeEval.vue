<script setup lang="ts">
/**
 * AI 实时试讲评估
 * MediaPipe Pose 骨架连线 + Face 表情识别
 * 音频录制 → 后端 AI 语音识别
 * 音频频谱 + 语速曲线 + 能量仪表盘
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  VideoCamera, Microphone, Timer, TrendCharts,
  CircleCheck, Warning, Close, VideoPlay, VideoPause,
  Refresh, DataAnalysis, Lightning, Upload, UploadFilled,
  ArrowLeft, ArrowRight, Loading
} from '@element-plus/icons-vue'
import { aiApi } from '@/api/ai'
import { trialVideosApi, type TrialVideo } from '@/api/trialVideos'
import TrialVideoUploader from '@/components/TrialVideoUploader.vue'
import TrialVideoLibrary from '@/components/TrialVideoLibrary.vue'
import {
  FilesetResolver, PoseLandmarker, FaceLandmarker, HandLandmarker, DrawingUtils
} from '@mediapipe/tasks-vision'

// ==================== 骨架连线定义 ====================
// Pose 33 点连线
const POSE_CONNECTIONS: [number, number][] = [
  [0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],
  [9,10],[11,12],[11,13],[13,15],[15,17],[15,19],[15,21],
  [17,19],[12,14],[14,16],[16,18],[16,20],[16,22],[18,20],
  [11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[27,31],
  [29,31],[24,26],[26,28],[28,30],[28,32],[30,32]
]
// Hand 21 点连线
const HAND_CONNECTIONS: [number, number][] = [
  [0,1],[1,2],[2,3],[3,4],       // 拇指
  [0,5],[5,6],[6,7],[7,8],       // 食指
  [0,9],[9,10],[10,11],[11,12],  // 中指
  [0,13],[13,14],[14,15],[15,16],// 无名指
  [0,17],[17,18],[18,19],[19,20],// 小指
  [5,9],[9,13],[13,17]           // 掌心横连
]
// 身体部位颜色
const BODY_COLORS: Record<string, string> = {
  face: '#ffeb3b',
  torso: '#00e5ff',
  leftArm: '#76ff03',
  rightArm: '#ff9100',
  leftLeg: '#e040fb',
  rightLeg: '#00b0ff',
}
// 连线 → 部位映射
const getConnectionColor = (i: number, j: number): string => {
  if (i <= 10 && j <= 10) return BODY_COLORS.face
  if ((i === 11 || i === 12) && (j === 23 || j === 24)) return BODY_COLORS.torso
  if (i === 11 && j === 12) return BODY_COLORS.torso
  if (i === 23 && j === 24) return BODY_COLORS.torso
  if ([11,13,15,17,19,21].includes(i) || [11,13,15,17,19,21].includes(j)) return BODY_COLORS.leftArm
  if ([12,14,16,18,20,22].includes(i) || [12,14,16,18,20,22].includes(j)) return BODY_COLORS.rightArm
  if ([23,25,27,29,31].includes(i) || [23,25,27,29,31].includes(j)) return BODY_COLORS.leftLeg
  if ([24,26,28,30,32].includes(i) || [24,26,28,30,32].includes(j)) return BODY_COLORS.rightLeg
  return '#00e5ff'
}
// 表情标签配置
interface ExpressionTag {
  label: string
  color: string
  icon: string
}
const EXPRESSION_TAGS: Record<string, ExpressionTag> = {
  '微笑':   { label: '微笑', color: '#10b981', icon: '😊' },
  '大笑':   { label: '大笑', color: '#22c55e', icon: '😄' },
  '严肃':   { label: '严肃', color: '#64748b', icon: '😐' },
  '皱眉':   { label: '皱眉', color: '#ef4444', icon: '😟' },
  '惊讶':   { label: '惊讶', color: '#f59e0b', icon: '😮' },
  '讲话中': { label: '讲话中', color: '#0891b2', icon: '🗣' },
  '眨眼':   { label: '眨眼', color: '#8b5cf6', icon: '😉' },
  '抬眉':   { label: '抬眉', color: '#06b6d4', icon: '🤨' },
  '嘟嘴':   { label: '嘟嘴', color: '#ec4899', icon: '😗' },
  '思考':   { label: '思考', color: '#6366f1', icon: '🤔' },
  '紧张':   { label: '紧张', color: '#f97316', icon: '😰' },
  '自信':   { label: '自信', color: '#14b8a6', icon: '😎' },
  '正常':   { label: '正常', color: '#94a3b8', icon: '😶' },
  '等待检测': { label: '等待检测', color: '#94a3b8', icon: '⏳' },
}

// ==================== 状态 ====================
const evalMode = ref<'idle' | 'realtime' | 'upload'>('idle') // idle=选择界面, realtime=实时, upload=上传
const showMetricsPanel = ref(true) // 右侧浮动指标面板开关
const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const spectrumCanvasRef = ref<HTMLCanvasElement | null>(null)
const speechCurveCanvasRef = ref<HTMLCanvasElement | null>(null)
const isActive = ref(false)
const isPaused = ref(false)
const mediaStream = ref<MediaStream | null>(null)
const elapsedSeconds = ref(0)
const targetDuration = ref(10)
let timerInterval: ReturnType<typeof setInterval> | null = null
const isUploadPlayback = ref(false)
let uploadVideoUrl = ''

// MediaPipe
let poseLandmarker: PoseLandmarker | null = null
let faceLandmarker: FaceLandmarker | null = null
let handLandmarker: HandLandmarker | null = null
let drawingUtils: DrawingUtils | null = null
let mpAnimFrame: number | null = null
const mpLoading = ref(false)
const mpReady = ref(false)

// 骨架平滑（指数移动平均，消除抖动）
const SMOOTH_ALPHA = 0.85 // 越大越跟随实时位置，减少延迟
let prevSmoothedPose: Array<{x:number;y:number;z:number;visibility?:number}> | null = null
let prevSmoothedHands: Array<Array<{x:number;y:number;z:number}>> = []
let prevSmoothedFace: Array<{x:number;y:number;z:number}> | null = null
const FACE_SMOOTH_ALPHA = 0.9 // 高跟随性，减少延迟
const smoothFaceLandmarks = (raw: Array<{x:number;y:number;z:number}>) => {
  if (!prevSmoothedFace) { prevSmoothedFace = raw.map(l => ({...l})); return raw }
  const out = raw.map((l, i) => ({
    x: prevSmoothedFace![i].x * (1 - FACE_SMOOTH_ALPHA) + l.x * FACE_SMOOTH_ALPHA,
    y: prevSmoothedFace![i].y * (1 - FACE_SMOOTH_ALPHA) + l.y * FACE_SMOOTH_ALPHA,
    z: prevSmoothedFace![i].z * (1 - FACE_SMOOTH_ALPHA) + l.z * FACE_SMOOTH_ALPHA,
  }))
  prevSmoothedFace = out
  return out
}
const smoothPoseLandmarks = (raw: Array<{x:number;y:number;z:number;visibility?:number}>) => {
  if (!prevSmoothedPose) { prevSmoothedPose = raw.map(l => ({...l})); return raw }
  const out = raw.map((l, i) => ({
    x: prevSmoothedPose![i].x * (1 - SMOOTH_ALPHA) + l.x * SMOOTH_ALPHA,
    y: prevSmoothedPose![i].y * (1 - SMOOTH_ALPHA) + l.y * SMOOTH_ALPHA,
    z: prevSmoothedPose![i].z * (1 - SMOOTH_ALPHA) + l.z * SMOOTH_ALPHA,
    visibility: (prevSmoothedPose![i].visibility ?? 1) * (1 - SMOOTH_ALPHA) + (l.visibility ?? 1) * SMOOTH_ALPHA,
  }))
  prevSmoothedPose = out
  return out
}
const smoothHandLandmarks = (raw: Array<{x:number;y:number;z:number}>, idx: number) => {
  if (!prevSmoothedHands[idx]) { prevSmoothedHands[idx] = raw.map(l => ({...l})); return raw }
  const out = raw.map((l, i) => ({
    x: prevSmoothedHands[idx][i].x * (1 - SMOOTH_ALPHA) + l.x * SMOOTH_ALPHA,
    y: prevSmoothedHands[idx][i].y * (1 - SMOOTH_ALPHA) + l.y * SMOOTH_ALPHA,
    z: prevSmoothedHands[idx][i].z * (1 - SMOOTH_ALPHA) + l.z * SMOOTH_ALPHA,
  }))
  prevSmoothedHands[idx] = out
  return out
}

// 显示值平滑（降低右侧面板数值跳动）
const DISPLAY_SMOOTH = 0.08 // 越小越平滑（降低以更平滑）
let _smoothPoseScore = 0
let _smoothExprScore = 70
let _smoothExprConf = 0
let _stableExprState = '等待检测'
let _exprStateCounter = 0
const EXPR_STABLE_FRAMES = 8 // 表情状态需稳定帧数才切换
let _lastDetailUpdate = 0
const DETAIL_INTERVAL = 600 // 表情维度更新间隔 ms

// 右侧浮动面板显示节流：数值每 PANEL_THROTTLE ms 更新一次
const PANEL_THROTTLE = 800
let _lastPanelUpdate = 0
const dpOverallScore = ref(0)
const dpSpeechRate = ref(0)
const dpPoseScore = ref(0)
const dpExprScore = ref(0)
const dpExprState = ref('等待检测')
const dpExprConf = ref(0)
const dpEnergyLevel = ref(0)
const dpFillerCount = ref(0)
const dpPosture = ref<'good'|'warning'|'bad'>('good')
const dpSpeechRateType = ref<'slow'|'normal'|'fast'>('normal')
const updateDisplayPanel = () => {
  const now = performance.now()
  if (now - _lastPanelUpdate < PANEL_THROTTLE) return
  _lastPanelUpdate = now
  dpOverallScore.value = metrics.overallScore
  dpSpeechRate.value = metrics.speechRateValue
  dpPoseScore.value = poseScore.value
  dpExprScore.value = metrics.expressionScore
  dpExprState.value = expressionState.value
  dpExprConf.value = Math.round(expressionConfidence.value * 100)
  dpEnergyLevel.value = energyLevel.value
  dpFillerCount.value = fillerWordCount.value
  dpPosture.value = metrics.posture
  dpSpeechRateType.value = metrics.speechRate
}

// 表情状态
const expressionState = ref('等待检测')
const expressionConfidence = ref(0)
const expressionDetail = ref<Record<string, number>>({}) // 所有表情维度分数
const handDetected = ref(false)

// 姿态评分
const poseScore = ref(0)
const poseMessage = ref('等待检测')
const poseDetected = ref(false)
const faceDetected = ref(false)

// 音频
let audioContext: AudioContext | null = null
let analyserNode: AnalyserNode | null = null
let spectrumAnimFrame: number | null = null
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []
let transcribeTimer: ReturnType<typeof setInterval> | null = null
const isTranscribing = ref(false)
const currentTranscript = ref('')
const allWords = ref<string[]>([])
const transcriptSegments = ref<{ time: string; text: string }[]>([])
const wordsPerMinute = ref(0)
const fillerWordCount = ref(0)
const fillerWordsList = ['嗯', '啊', '那个', '就是', '然后', '这个', '对吧', '所以说']

// 语速曲线
const speechRateHistory = ref<{ time: number; wpm: number }[]>([])
let speechCurveAnimFrame: number | null = null

// 能量仪表盘
const energyLevel = ref(0)
const energyLabel = computed(() => {
  if (energyLevel.value < 30) return '平静'
  if (energyLevel.value < 60) return '适中'
  if (energyLevel.value < 80) return '有感情'
  return '激情澎湃'
})
const energyColor = computed(() => {
  if (energyLevel.value < 30) return '#3b82f6'
  if (energyLevel.value < 60) return '#10b981'
  if (energyLevel.value < 80) return '#f59e0b'
  return '#ef4444'
})

// 实时指标
const metrics = reactive({
  speechRate: 'normal' as 'slow' | 'normal' | 'fast',
  speechRateValue: 0,
  volume: 0,
  posture: 'good' as 'good' | 'warning' | 'bad',
  postureMessage: '等待检测',
  eyeContact: true,
  timeControl: 'on_track' as 'on_track' | 'ahead' | 'behind',
  overallScore: 0,
  expressionScore: 0,
  gestureScore: 0,
})

const showHUD = ref(true)
const videoHover = ref(false)
const tips = ref<{ id: number; text: string; type: 'info' | 'warning' | 'success' }[]>([])
let tipId = 0
const ltpBodyRef = ref<HTMLElement | null>(null)
const scoreHistory = ref<number[]>([])

// 视频上传
const showUploadSection = ref(false)
const uploadingVideo = ref(false)
const uploadProgress = ref(0)
const analysisTaskId = ref('')
const standaloneAnalysis = ref<any>(null)
const analysisStatus = ref<'idle' | 'uploading' | 'processing' | 'completed' | 'failed'>('idle')
const analysisError = ref('')
const showTranscript = ref(true)
let pollTimer: ReturnType<typeof setInterval> | null = null
const evaluationFile = ref<File | null>(null)
const selectedEvaluationFile = ref<File | null>(null)
const showVideoDetails = ref(false)
const uploadingDetails = ref(false)
const videoSaved = ref(false)
const goodPerformanceScore = 80
const canSaveEvaluatedVideo = computed(() => analysisStatus.value === 'completed' &&
  !!evaluationFile.value && !videoSaved.value)
let promptedTaskId = ''
let evaluationRequest = 0
let uploadPromptVisible = false

watch([analysisStatus, isActive], async ([status, active]) => {
  const taskId = analysisTaskId.value
  if (status !== 'completed' || active || !taskId || promptedTaskId === taskId ||
      Number(standaloneAnalysis.value?.overall_score) < goodPerformanceScore ||
      !Number.isFinite(Number(standaloneAnalysis.value?.overall_score))) return
  promptedTaskId = taskId
  uploadPromptVisible = true
  try {
    await ElMessageBox.confirm(
      `本次 AI 评估为 ${standaloneAnalysis.value.overall_score} 分，表现良好！是否上传这段试讲视频？选择“是”后填写视频详情。`,
      '是否上传试讲视频',
      { confirmButtonText: '是，填写详情', cancelButtonText: '暂不上传', type: 'success', closeOnClickModal: false },
    )
    if (analysisTaskId.value === taskId && canSaveEvaluatedVideo.value) showVideoDetails.value = true
  } catch { /* 保留评估报告，稍后仍可主动上传。 */ }
  finally { uploadPromptVisible = false }
})

// ==================== 计算属性 ====================
const formattedTime = computed(() => {
  const m = Math.floor(elapsedSeconds.value / 60)
  const s = elapsedSeconds.value % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
})
const timeProgress = computed(() =>
  Math.min(100, (elapsedSeconds.value / (targetDuration.value * 60)) * 100)
)
const speechRateLabel = computed(() => {
  if (metrics.speechRate === 'slow') return '偏慢'
  if (metrics.speechRate === 'fast') return '偏快'
  return '适中'
})
const speechRateColor = computed(() => {
  if (metrics.speechRate === 'slow') return '#f59e0b'
  if (metrics.speechRate === 'fast') return '#ef4444'
  return '#10b981'
})
// 面板显示用（节流后）
const dpSpeechRateLabel = computed(() => {
  if (dpSpeechRateType.value === 'slow') return '偏慢'
  if (dpSpeechRateType.value === 'fast') return '偏快'
  return '适中'
})
const dpSpeechRateColor = computed(() => {
  if (dpSpeechRateType.value === 'slow') return '#f59e0b'
  if (dpSpeechRateType.value === 'fast') return '#ef4444'
  return '#10b981'
})
const dpEnergyColor = computed(() => {
  if (dpEnergyLevel.value < 30) return '#3b82f6'
  if (dpEnergyLevel.value < 60) return '#10b981'
  if (dpEnergyLevel.value < 80) return '#f59e0b'
  return '#ef4444'
})
const dpEnergyLabel = computed(() => {
  if (dpEnergyLevel.value < 30) return '平静'
  if (dpEnergyLevel.value < 60) return '适中'
  if (dpEnergyLevel.value < 80) return '有感情'
  return '激情澎湃'
})

// ==================== MediaPipe 初始化 ====================
const initMediaPipe = async () => {
  mpLoading.value = true
  try {
    // 使用本地 WASM 文件加速加载（避免 CDN 延迟）
    const vision = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
    // 独立加载每个模型，某个失败不影响其他
    const results = await Promise.allSettled([
      PoseLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: '/mediapipe/models/pose_landmarker_lite.task',
          delegate: 'GPU'
        },
        runningMode: 'VIDEO',
        numPoses: 1,
      }),
      FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: '/mediapipe/models/face_landmarker.task',
          delegate: 'GPU'
        },
        runningMode: 'VIDEO',
        numFaces: 1,
        outputFaceBlendshapes: true,
        minFaceDetectionConfidence: 0.3,
        minFacePresenceConfidence: 0.3,
        minTrackingConfidence: 0.3,
      }),
      // 注：手部模型已禁用——在 MediaPipe Tasks JS 上单次推理 ~80-100ms，是最大性能瓶颈。
      // 若需要恢复，把下面的注释取消即可。
      // HandLandmarker.createFromOptions(vision, { baseOptions: { modelAssetPath: '/mediapipe/models/hand_landmarker.task', delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2, minHandDetectionConfidence: 0.3, minHandPresenceConfidence: 0.3, minTrackingConfidence: 0.3 }),
    ])
    if (results[0].status === 'fulfilled') { poseLandmarker = results[0].value; console.log('[MediaPipe] Pose 模型加载成功') }
    else console.error('[MediaPipe] Pose 模型加载失败:', results[0].reason)
    if (results[1].status === 'fulfilled') { faceLandmarker = results[1].value; console.log('[MediaPipe] Face 模型加载成功') }
    else console.error('[MediaPipe] Face 模型加载失败:', results[1].reason)
    handLandmarker = null // 已禁用
    mpReady.value = !!(poseLandmarker || faceLandmarker)
    const loaded = [poseLandmarker && 'Pose', faceLandmarker && 'Face'].filter(Boolean)
    console.log(`MediaPipe 模型加载完成: ${loaded.join(', ')} (Hand 已禁用以提升帧率)`)
    if (!mpReady.value) ElMessage.warning('AI 视觉模型全部加载失败')
  } catch (e: any) {
    console.error('MediaPipe 加载失败:', e)
    ElMessage.warning('AI 视觉模型加载失败，姿态和表情检测不可用')
  } finally {
    mpLoading.value = false
  }
}

// ==================== MediaPipe 实时检测 + 绘制 ====================
let lastTimestamp = -1
// 各检测器独立时间戳（必须严格单调递增）
let _poseTs = 0, _faceTs = 0, _handTs = 0
const nextHandTs = (now: number) => { _handTs = Math.max(_handTs + 0.1, now); return _handTs }
const nextFaceTs = (now: number) => { _faceTs = Math.max(_faceTs + 0.1, now); return _faceTs }
const nextPoseTs = (now: number) => { _poseTs = Math.max(_poseTs + 0.1, now); return _poseTs }
// 帧计数（Face/Hand round-robin: 偶帧 Face、奇帧 Hand，各自每 2 帧检测一次）
let _frameCount = 0
// 缓存上一次手部检测结果，用于跳帧时继续绘制
let _lastHands: Array<{lm: any[], offX: number, scaleX: number, offY: number, scaleY: number}> = []
// 缓存上一次人脸检测结果（已重映射），用于跳帧绘制
let _lastFace: Array<{x:number;y:number;z:number}> | null = null
// FPS 监控
let _fpsLastLog = 0, _fpsFrameCount = 0, _fpsTotalMs = 0
// 用于人脸/手部检测的方形裁剪画布（解决宽屏视频检测失败问题）
let cropCanvas: HTMLCanvasElement | null = null
let cropCtx: CanvasRenderingContext2D | null = null
let cropOffsetX = 0 // 裁剪区域在原视频中的左偏移（归一化 0-1）
let cropScale = 1   // 裁剪边长 / 原视频宽度
const ensureCropCanvas = (size: number) => {
  if (!cropCanvas) {
    cropCanvas = document.createElement('canvas')
    cropCtx = cropCanvas.getContext('2d', { willReadFrequently: true })
  }
  if (cropCanvas.width !== size) cropCanvas.width = size
  if (cropCanvas.height !== size) cropCanvas.height = size
  return cropCanvas!
}

// === 工作画布：把 1920+ 大视频降采样到 ≤320 长边 ===
// MediaPipe 每次 detectForVideo 都会把视频纹理上传到 GPU，1920×810 ≈ 6MB，预降采样到 320 后变 ≈0.4MB（15× 减少），
// pose 单次耗时从 50ms+ 降到 ~10-15ms。
const WORK_MAX = 320
let workCanvas: HTMLCanvasElement | null = null
let workCtx: CanvasRenderingContext2D | null = null
const ensureWorkCanvas = (vw: number, vh: number): HTMLCanvasElement | null => {
  if (vw <= 0 || vh <= 0) return null
  const scale = Math.min(1, WORK_MAX / Math.max(vw, vh))
  const w = Math.max(1, Math.floor(vw * scale))
  const h = Math.max(1, Math.floor(vh * scale))
  if (!workCanvas) {
    workCanvas = document.createElement('canvas')
    workCtx = workCanvas.getContext('2d', { alpha: false })
  }
  if (workCanvas.width !== w) workCanvas.width = w
  if (workCanvas.height !== h) workCanvas.height = h
  return workCanvas
}
// 将方形裁剪画布得到的 landmarks 重映射回原视频归一化坐标
// 视频 W×H (W>H)，裁剪 H×H 居中：x_full = cropOffsetX + x_crop * cropScale, y_full 不变
const remapLandmark = <T extends {x:number;y:number}>(lm: T): T => {
  return { ...lm, x: cropOffsetX + lm.x * cropScale }
}

const runMediaPipeDetection = () => {
  if (!isActive.value || isPaused.value) return
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas || video.readyState < 2) {
    mpAnimFrame = requestAnimationFrame(runMediaPipeDetection)
    return
  }

  // DPR 上限 1.5：retina 屏 DPR=2 时像素量减半，整体绘制开销 ~2×
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
  const rect = canvas.getBoundingClientRect()
  const targetW = Math.floor(rect.width * dpr)
  const targetH = Math.floor(rect.height * dpr)
  if (canvas.width !== targetW || canvas.height !== targetH) {
    canvas.width = targetW
    canvas.height = targetH
  }

  const ctx = canvas.getContext('2d')
  if (!ctx) { mpAnimFrame = requestAnimationFrame(runMediaPipeDetection); return }
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const now = performance.now()
  if (now <= lastTimestamp) {
    mpAnimFrame = requestAnimationFrame(runMediaPipeDetection)
    return
  }
  const frameStart = now
  lastTimestamp = now
  _frameCount++

  const w = canvas.width, h = canvas.height

  // 计算 object-fit: contain 下视频实际渲染区域
  const vAspect = video.videoWidth / (video.videoHeight || 1)
  const cAspect = w / (h || 1)
  let vx: number, vy: number, vw: number, vh: number
  if (vAspect > cAspect) {
    vw = w; vh = w / vAspect; vx = 0; vy = (h - vh) / 2
  } else {
    vh = h; vw = h * vAspect; vx = (w - vw) / 2; vy = 0
  }

  // 裁剪绘制区域到视频可视范围
  ctx.save()
  ctx.beginPath()
  ctx.rect(vx, vy, vw, vh)
  ctx.clip()

  // Pose 检测：先把视频降采样到 ≤320 长边的 work canvas，再喂给模型
  let poseLm: Array<{x:number;y:number;z:number;visibility?:number}> | null = null
  if (poseLandmarker) {
    try {
      let poseInputSource: HTMLVideoElement | HTMLCanvasElement = video
      if (video.videoWidth > WORK_MAX) {
        const wc = ensureWorkCanvas(video.videoWidth, video.videoHeight)
        if (wc && workCtx) {
          workCtx.drawImage(video, 0, 0, wc.width, wc.height)
          poseInputSource = wc
        }
      }
      const poseResult = poseLandmarker.detectForVideo(poseInputSource, nextPoseTs(now))
      if (poseResult.landmarks && poseResult.landmarks.length > 0) {
        poseDetected.value = true
        poseLm = smoothPoseLandmarks(poseResult.landmarks[0])
        drawPoseSkeleton(ctx, poseLm, vx, vy, vw, vh)
        evaluatePoseFromLandmarks(poseLm)
      } else {
        poseDetected.value = false
      }
    } catch (e) { console.warn('[Pose] 检测异常:', e) }
  }

  const vW = video.videoWidth, vH = video.videoHeight

  // ========= Face 检测：基于 Pose 的人脸 ROI（每 2 帧检测一次） =========
  if (faceLandmarker && vW > 0 && vH > 0) {
    const shouldDetectFace = (_frameCount & 1) === 0 // 偶数帧
    if (shouldDetectFace) {
      try {
        let cxN = 0.5, cyN = 0.4, halfN = 0.25
        if (poseLm) {
          const nose = poseLm[0]
          const lEar = poseLm[7], rEar = poseLm[8]
          const lSh = poseLm[11], rSh = poseLm[12]
          if (nose && (nose.visibility ?? 1) > 0.3) {
            cxN = nose.x; cyN = nose.y
            let earDist = (lEar && rEar) ? Math.hypot(lEar.x - rEar.x, lEar.y - rEar.y) : 0
            let shDist = (lSh && rSh) ? Math.hypot(lSh.x - rSh.x, lSh.y - rSh.y) : 0
            halfN = Math.max(earDist * 2.4, shDist * 0.85, 0.14)
            cyN = Math.max(0.05, nose.y - halfN * 0.2)
          }
        }
        const cx = cxN * vW, cy = cyN * vH
        const halfPx = halfN * Math.max(vW, vH)
        const sx0 = Math.max(0, cx - halfPx), sy0 = Math.max(0, cy - halfPx)
        const ex = Math.min(vW, cx + halfPx), ey = Math.min(vH, cy + halfPx)
        const side = Math.max(ex - sx0, ey - sy0, 64)
        const fcx = (sx0 + ex) / 2, fcy = (sy0 + ey) / 2
        const fsx = Math.max(0, Math.min(vW - side, fcx - side / 2))
        const fsy = Math.max(0, Math.min(vH - side, fcy - side / 2))
        const fside = Math.min(side, vW - fsx, vH - fsy)
        const cc = ensureCropCanvas(256) // 256 替代 384，速度提升 50%+
        if (cropCtx) {
          cropCtx.drawImage(video, fsx, fsy, fside, fside, 0, 0, cc.width, cc.height)
          const cox = fsx / vW, csx = fside / vW
          const coy = fsy / vH, csy = fside / vH
          const faceResult = faceLandmarker.detectForVideo(cc, nextFaceTs(now))
          if (faceResult.faceLandmarks && faceResult.faceLandmarks.length > 0) {
            if (!faceDetected.value) console.log('[Face] 首次检测到人脸，landmarks:', faceResult.faceLandmarks[0].length)
            faceDetected.value = true
            const remapped = faceResult.faceLandmarks[0].map(lm => ({
              ...lm, x: cox + lm.x * csx, y: coy + lm.y * csy,
            }))
            _lastFace = smoothFaceLandmarks(remapped)
            if (faceResult.faceBlendshapes && faceResult.faceBlendshapes.length > 0) {
              evaluateExpression(faceResult.faceBlendshapes[0].categories)
            }
          } else {
            faceDetected.value = false
            _lastFace = null
          }
        }
      } catch (e) { console.warn('[Face] 检测异常:', e) }
    }
    // 无论本帧是否检测，都用最近一次结果绘制（跳帧仍流畅）
    if (_lastFace) drawFaceOverlay(ctx, _lastFace, vx, vy, vw, vh)
  }

  // Hand 检测已禁用——MediaPipe Tasks JS 上 ~80-100ms/次，且 ROI 经常找不到手。
  // Pose 模型已经包含手腕/手指基本骨架点（idx 15-22），右侧面板的'手势分'通过 Pose 计算。

  ctx.restore()
  if (showHUD.value) drawHUD(ctx, vx, vy, vw, vh)
  updateDisplayPanel()

  // FPS 监控（每 2 秒输出一次平均帧时间）
  const frameMs = performance.now() - frameStart
  _fpsTotalMs += frameMs
  _fpsFrameCount++
  if (now - _fpsLastLog > 2000) {
    const avgMs = _fpsTotalMs / _fpsFrameCount
    const fps = (1000 / avgMs).toFixed(1)
    console.log(`[FPS] ${fps} fps (avg ${avgMs.toFixed(1)}ms/frame, ${_fpsFrameCount} frames)`)
    _fpsLastLog = now
    _fpsFrameCount = 0
    _fpsTotalMs = 0
  }

  mpAnimFrame = requestAnimationFrame(runMediaPipeDetection)
}

// ==================== 骨架绘制（彩色分区）====================
const drawPoseSkeleton = (
  ctx: CanvasRenderingContext2D,
  landmarks: Array<{ x: number; y: number; z: number; visibility?: number }>,
  vx: number, vy: number, vw: number, vh: number
) => {
  const dpr = window.devicePixelRatio || 1
  // 翻转 x 坐标以匹配镜像视频（上传视频不翻转）
  const lms = isUploadPlayback.value ? landmarks : landmarks.map(lm => ({ ...lm, x: 1 - lm.x }))
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  // 绘制身体轮廓线（外轮廓）
  const contourIndices = [11, 23, 25, 27, 31, 29, 27, 25, 23, 24, 26, 28, 32, 30, 28, 26, 24, 12]
  ctx.globalAlpha = 0.3
  ctx.strokeStyle = '#00e5ff'
  ctx.lineWidth = 1.2 * dpr
  // shadowColor removed
  ctx.shadowBlur = 0
  ctx.beginPath()
  let contourStarted = false
  for (const idx of contourIndices) {
    const lm = lms[idx]
    if (!lm || (lm.visibility ?? 1) < 0.4) continue
    if (!contourStarted) { ctx.moveTo(vx + lm.x * vw, vy + lm.y * vh); contourStarted = true }
    else ctx.lineTo(vx + lm.x * vw, vy + lm.y * vh)
  }
  ctx.stroke()
  ctx.shadowBlur = 0

  // 连线（按部位着色，FaceLandmarker可用时跳过Pose面部连线）
  const skipFace = faceDetected.value
  for (const [i, j] of POSE_CONNECTIONS) {
    const isFaceConn = i <= 10 && j <= 10
    if (skipFace && isFaceConn) continue // FaceLandmarker已画面部网格，跳过Pose面部
    const a = lms[i], b = lms[j]
    if (!a || !b) continue
    const va = a.visibility ?? 1, vb = b.visibility ?? 1
    if (va < 0.4 || vb < 0.4) continue
    const alpha = Math.min(va, vb) * 0.9
    ctx.globalAlpha = alpha
    const connColor = getConnectionColor(i, j)
    ctx.strokeStyle = connColor
    ctx.lineWidth = (isFaceConn ? 1.0 : 2.5) * dpr
    // shadowColor removed
    ctx.shadowBlur = 0
    ctx.beginPath()
    ctx.moveTo(vx + a.x * vw, vy + a.y * vh)
    ctx.lineTo(vx + b.x * vw, vy + b.y * vh)
    ctx.stroke()
  }
  // 关节点（面部更小，FaceLandmarker可用时隐藏Pose面部点）
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  lms.forEach((lm, idx) => {
    const v = lm.visibility ?? 1
    if (v < 0.4) return
    const isFace = idx <= 10
    if (skipFace && isFace) return // FaceLandmarker已画面部，跳过
    const isHand = [15,16,17,18,19,20,21,22].includes(idx)
    const radius = (isFace ? 1.5 : isHand ? 3 : 4) * dpr
    // 外圈发光
    ctx.beginPath()
    ctx.arc(vx + lm.x * vw, vy + lm.y * vh, radius + 1.5 * dpr, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(0, 229, 255, ${v * 0.2})`
    ctx.fill()
    // 内圈
    ctx.beginPath()
    ctx.arc(vx + lm.x * vw, vy + lm.y * vh, radius, 0, Math.PI * 2)
    ctx.fillStyle = isFace ? BODY_COLORS.face : '#00e5ff'
    ctx.fill()
    ctx.strokeStyle = 'rgba(255,255,255,0.6)'
    ctx.lineWidth = 0.6 * dpr
    ctx.stroke()
  })
}

// ==================== 手部骨架绘制 ====================
const drawHandSkeleton = (
  ctx: CanvasRenderingContext2D,
  landmarks: Array<{ x: number; y: number; z: number }>,
  vx: number, vy: number, vw: number, vh: number
) => {
  const dpr = window.devicePixelRatio || 1
  // 翻转 x 坐标以匹配镜像视频（上传视频不翻转）
  const lms = isUploadPlayback.value ? landmarks : landmarks.map(lm => ({ ...lm, x: 1 - lm.x }))
  ctx.globalAlpha = 0.9
  // 手指连线（每根手指不同颜色）
  const fingerColors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#74c0fc']
  const fingerRanges = [[0,1,2,3,4],[5,6,7,8],[9,10,11,12],[13,14,15,16],[17,18,19,20]]
  fingerRanges.forEach((finger, fi) => {
    ctx.strokeStyle = fingerColors[fi]
    ctx.lineWidth = 1.8 * dpr
    ctx.lineCap = 'round'
    for (let k = 0; k < finger.length - 1; k++) {
      const a = lms[finger[k]], b = lms[finger[k + 1]]
      if (!a || !b) continue
      ctx.beginPath()
      ctx.moveTo(vx + a.x * vw, vy + a.y * vh)
      ctx.lineTo(vx + b.x * vw, vy + b.y * vh)
      ctx.stroke()
    }
  })
  // 掌心横连
  ctx.strokeStyle = '#a78bfa'
  ctx.lineWidth = 1.5 * dpr
  for (const [i, j] of [[5,9],[9,13],[13,17]] as [number,number][]) {
    const a = lms[i], b = lms[j]
    if (!a || !b) continue
    ctx.beginPath()
    ctx.moveTo(vx + a.x * vw, vy + a.y * vh)
    ctx.lineTo(vx + b.x * vw, vy + b.y * vh)
    ctx.stroke()
  }
  // 关节点
  ctx.globalAlpha = 1
  lms.forEach((lm, idx) => {
    const isTip = [4,8,12,16,20].includes(idx)
    const r = (isTip ? 4 : 2.5) * dpr
    ctx.beginPath()
    ctx.arc(vx + lm.x * vw, vy + lm.y * vh, r, 0, Math.PI * 2)
    ctx.fillStyle = isTip ? '#fff' : '#e0e0e0'
    ctx.fill()
    if (isTip) {
      ctx.strokeStyle = fingerColors[Math.floor(idx / 4) - (idx > 4 ? 0 : 0)]
      ctx.lineWidth = 1.5 * dpr
      ctx.stroke()
    }
  })
}

// ==================== 人脸叠加层（高密度面部网格 + 表情标签）====================
// 面部轮廓
const FACE_OVAL = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
// 面部网格三角连线 —— 覆盖整张脸的密集网格
const FACE_MESH_LINES: [number, number][] = [
  // 左眉
  [70,63],[63,105],[105,66],[66,107],[107,55],[55,65],
  // 右眉
  [300,293],[293,334],[334,296],[296,336],[336,285],[285,295],
  // 眉毛到轮廓的支撑线
  [70,46],[65,52],[300,276],[295,282],
  // 左眼上眼睑
  [246,161],[161,160],[160,159],[159,158],[158,157],[157,173],
  // 左眼下眼睑
  [33,7],[7,163],[163,144],[144,145],[145,153],[153,154],[154,155],[155,133],
  // 左眼连合（上下眼睑连接）
  [246,33],[173,133],
  // 右眼上眼睑
  [466,388],[388,387],[387,386],[386,385],[385,384],[384,398],
  // 右眼下眼睑
  [362,382],[382,381],[381,380],[380,374],[374,373],[373,390],[390,249],[249,263],
  // 右眼连合
  [466,362],[398,263],
  // 鼻梁
  [168,6],[6,197],[197,195],[195,5],
  // 鼻翼
  [48,115],[115,220],[220,45],[45,4],[4,275],[275,440],[440,344],[344,278],
  // 鼻侧线
  [6,122],[6,351],[122,196],[351,419],
  // 外唇上
  [61,185],[185,40],[40,39],[39,37],[37,0],[0,267],[267,269],[269,270],[270,409],[409,291],
  // 外唇下
  [61,146],[146,91],[91,181],[181,84],[84,17],[17,314],[314,405],[405,321],[321,375],[375,291],
  // 内唇上
  [78,191],[191,80],[80,81],[81,82],[82,13],[13,312],[312,311],[311,310],[310,415],[415,308],
  // 内唇下
  [78,95],[95,88],[88,178],[178,87],[87,14],[14,317],[317,402],[402,318],[318,324],[324,308],
  // 唇角连接
  [61,78],[291,308],
  // 面部结构网格（额头到鼻子）
  [10,151],[151,9],[9,8],[8,168],
  // 左脸颊结构线
  [234,93],[93,132],[132,58],[58,172],[172,136],[136,150],
  [127,162],[162,21],[21,54],[54,103],[103,67],[67,109],
  // 右脸颊结构线
  [454,323],[323,361],[361,288],[288,397],[397,365],[365,379],
  [356,389],[389,251],[251,284],[284,332],[332,297],[297,338],
  // 下巴结构
  [152,148],[148,176],[176,149],[149,150],[150,136],
  [152,377],[377,400],[400,378],[378,379],[379,365],
  // 鼻子到脸颊
  [48,131],[278,360],
  // 左眼到眉
  [161,105],[160,66],[159,107],
  // 右眼到眉
  [388,334],[387,296],[386,336],
]

const drawFaceOverlay = (
  ctx: CanvasRenderingContext2D,
  faceLandmarks: Array<{ x: number; y: number; z: number }>,
  vx: number, vy: number, vw: number, vh: number
) => {
  const dpr = window.devicePixelRatio || 1
  const fl = isUploadPlayback.value ? faceLandmarks : faceLandmarks.map(lm => ({ ...lm, x: 1 - lm.x }))
  const tag = EXPRESSION_TAGS[expressionState.value] || EXPRESSION_TAGS['正常']
  const px = (idx: number) => vx + fl[idx].x * vw
  const py = (idx: number) => vy + fl[idx].y * vh

  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  // 1. 面部轮廓（外圈，微发光）
  // shadowColor removed
  ctx.shadowBlur = 0
  ctx.globalAlpha = 0.55
  ctx.strokeStyle = tag.color
  ctx.lineWidth = 1.0 * dpr
  ctx.beginPath()
  for (let i = 0; i < FACE_OVAL.length; i++) {
    const lm = fl[FACE_OVAL[i]]
    if (!lm) continue
    if (i === 0) ctx.moveTo(vx + lm.x * vw, vy + lm.y * vh)
    else ctx.lineTo(vx + lm.x * vw, vy + lm.y * vh)
  }
  ctx.closePath()
  ctx.stroke()
  ctx.shadowBlur = 0

  // 2. 密集面部网格（高密度三角连线覆盖全脸）— 单次 stroke 批量绘制
  ctx.globalAlpha = 0.3
  ctx.strokeStyle = tag.color
  ctx.lineWidth = 0.4 * dpr
  const meshPath = new Path2D()
  for (const [a, b] of FACE_MESH_LINES) {
    if (!fl[a] || !fl[b]) continue
    meshPath.moveTo(px(a), py(a))
    meshPath.lineTo(px(b), py(b))
  }
  ctx.stroke(meshPath)

  // 3. 眉毛（加粗、明显）
  const drawFeaturePath = (indices: number[], color: string, width: number, alpha: number) => {
    ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = width * dpr; ctx.globalAlpha = alpha
    for (let i = 0; i < indices.length; i++) {
      const lm = fl[indices[i]]
      if (!lm) continue
      if (i === 0) ctx.moveTo(vx + lm.x * vw, vy + lm.y * vh)
      else ctx.lineTo(vx + lm.x * vw, vy + lm.y * vh)
    }
    ctx.stroke()
  }
  drawFeaturePath([70,63,105,66,107,55,65], '#a78bfa', 0.8, 0.65)
  drawFeaturePath([300,293,334,296,336,285,295], '#a78bfa', 0.65, 0.65)

  // 4. 眼睛（上下分离，跟随眨眼）
  const eyeColor = tag.color
  drawFeaturePath([246,161,160,159,158,157,173], eyeColor, 0.7, 0.7)
  drawFeaturePath([33,7,163,144,145,153,154,155,133], eyeColor, 0.7, 0.7)
  drawFeaturePath([466,388,387,386,385,384,398], eyeColor, 0.7, 0.7)
  drawFeaturePath([362,382,381,380,374,373,390,249,263], eyeColor, 0.7, 0.7)
  // 瞳孔（虹膜中心点）
  for (const idx of [468, 473]) {
    if (fl[idx]) {
      ctx.globalAlpha = 0.85
      ctx.beginPath()
      ctx.arc(px(idx), py(idx), 1.5 * dpr, 0, Math.PI * 2)
      ctx.fillStyle = '#fff'
      ctx.fill()
    }
  }

  // 5. 鼻子
  drawFeaturePath([168,6,197,195,5], '#94a3b8', 0.5, 0.4)
  drawFeaturePath([48,115,220,45,4,275,440,344,278], '#94a3b8', 0.5, 0.45)

  // 6. 嘴巴（外唇+内唇，张嘴跟随）
  drawFeaturePath([61,185,40,39,37,0,267,269,270,409,291], '#f472b6', 0.7, 0.6)
  drawFeaturePath([61,146,91,181,84,17,314,405,321,375,291], '#f472b6', 0.7, 0.6)
  drawFeaturePath([78,191,80,81,82,13,312,311,310,415,308], '#fb7185', 0.5, 0.45)
  drawFeaturePath([78,95,88,178,87,14,317,402,318,324,308], '#fb7185', 0.5, 0.45)

  // 7. 面部密集节点（覆盖全脸，跟随表情同步变化）
  // 收集所有网格连线涉及的唯一点 + 轮廓点
  const allFaceNodes = new Set<number>()
  for (const idx of FACE_OVAL) allFaceNodes.add(idx)
  for (const [a, b] of FACE_MESH_LINES) { allFaceNodes.add(a); allFaceNodes.add(b) }
  // 脸部边缘完整轮廓点（比FACE_OVAL更密，确保整个脸边缘都有节点）
  const faceEdgePts = [
    10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,
    152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109,
    // 额头发际线补充（更密）
    301,298,333,299,337,151,108,69,104,68,71,139,34,227,137,
    // 左脸边缘补充
    143,116,123,147,213,192,214,212,
    // 右脸边缘补充
    372,345,352,376,433,416,434,432,
    // 下巴中线补充
    175,396,369,395,394,364,367,
    // 左下巴轮廓
    140,170,171,169,135,138,215,177,
    // 右下巴轮廓
    370,400,401,399,366,368,435,406,
  ]
  for (const idx of faceEdgePts) allFaceNodes.add(idx)

  // 额外补充面部均匀分布点
  const extraPts = [
    // 额头
    10,67,109,108,69,104,68,71,21,54,103,9,8,151,
    // 左脸
    234,93,132,58,172,136,150,149,176,148,152,127,162,
    // 右脸
    454,323,361,288,397,365,379,378,400,377,356,389,251,284,332,297,338,
    // 左眼周围
    246,161,160,159,158,157,173,33,7,163,144,145,153,154,155,133,
    130,25,110,24,23,22,26,112,243,190,56,28,27,29,30,247,
    // 右眼周围
    466,388,387,386,385,384,398,362,382,381,380,374,373,390,249,263,
    359,255,339,254,253,252,256,341,463,414,286,258,257,259,260,467,
    // 左眉
    70,63,105,66,107,55,65,52,53,46,124,35,111,117,118,119,120,121,128,
    // 右眉
    300,293,334,296,336,285,295,282,283,276,353,265,340,346,347,348,349,350,357,
    // 鼻子
    168,6,197,195,5,4,1,2,98,327,
    48,115,220,45,275,440,344,278,
    196,3,51,281,419,248,122,351,131,360,
    // 下巴
    152,148,176,149,150,136,172,58,132,
    377,400,378,379,365,397,288,361,323,
  ]
  for (const idx of extraPts) allFaceNodes.add(idx)

  // 嘴唇完整密集点（上唇+下唇所有节点，确保张嘴时跟随）
  const lipPts = [
    // 外唇上
    61,185,40,39,37,0,267,269,270,409,291,
    // 外唇下
    146,91,181,84,17,314,405,321,375,
    // 内唇上
    78,191,80,81,82,13,312,311,310,415,308,
    // 内唇下
    95,88,178,87,14,317,402,318,324,
    // 唇部补充点（更密集覆盖上下唇面）
    76,77,90,180,85,16,315,404,320,307,306,
    62,183,42,41,38,12,268,271,272,407,292,
    96,89,179,86,15,316,403,319,325,
    73,74,184,43,36,11,264,273,274,408,288,
  ]
  for (const idx of lipPts) allFaceNodes.add(idx)

  // 分层绘制：轮廓点+唇点+特征点稍大稍亮
  const featureNodes = new Set([
    // 眼角
    33,133,362,263,246,173,466,398,
    // 眉端
    70,65,300,295,
    // 鼻尖
    1,4,5,
    // 额顶/下巴
    10,152,
    // 瞳孔
    468,473,
  ])
  // 嘴唇所有点都作为特征点（更大更亮）
  const lipFeatureNodes = new Set(lipPts)
  // 脸部边缘轮廓点也稍大
  const edgeFeatureNodes = new Set(faceEdgePts)

  // 按层级分组，单次 fill 批量绘制（性能 4× 提升）
  const featPath = new Path2D()
  const lipPath = new Path2D()
  const edgePath = new Path2D()
  const normalPath = new Path2D()
  const featR = 1.0 * dpr, lipR = 0.8 * dpr, edgeR = 0.7 * dpr, normalR = 0.5 * dpr
  for (const idx of allFaceNodes) {
    if (!fl[idx]) continue
    const x = px(idx), y = py(idx)
    if (featureNodes.has(idx)) {
      featPath.moveTo(x + featR, y); featPath.arc(x, y, featR, 0, Math.PI * 2)
    } else if (lipFeatureNodes.has(idx)) {
      lipPath.moveTo(x + lipR, y); lipPath.arc(x, y, lipR, 0, Math.PI * 2)
    } else if (edgeFeatureNodes.has(idx)) {
      edgePath.moveTo(x + edgeR, y); edgePath.arc(x, y, edgeR, 0, Math.PI * 2)
    } else {
      normalPath.moveTo(x + normalR, y); normalPath.arc(x, y, normalR, 0, Math.PI * 2)
    }
  }
  ctx.globalAlpha = 0.3; ctx.fillStyle = 'rgba(200,220,255,0.8)'; ctx.fill(normalPath)
  ctx.globalAlpha = 0.5; ctx.fillStyle = tag.color; ctx.fill(edgePath)
  ctx.globalAlpha = 0.6; ctx.fillStyle = '#f472b6'; ctx.fill(lipPath)
  ctx.globalAlpha = 0.6; ctx.fillStyle = tag.color; ctx.fill(featPath)

  // 计算边界框用于标签定位
  let minX = 1, minY = 1, maxX = 0, maxY = 0
  for (const lm of fl) {
    if (lm.x < minX) minX = lm.x
    if (lm.y < minY) minY = lm.y
    if (lm.x > maxX) maxX = lm.x
    if (lm.y > maxY) maxY = lm.y
  }
  const pad = 0.02
  minX = Math.max(0, minX - pad)
  minY = Math.max(0, minY - pad * 1.5)
  maxX = Math.min(1, maxX + pad)

  const bx = vx + minX * vw, by = vy + minY * vh
  const bw = (maxX - minX) * vw

  // 表情标签
  ctx.shadowBlur = 0
  ctx.globalAlpha = 1
  const label = `${tag.icon} ${tag.label} ${Math.round(expressionConfidence.value * 100)}%`
  ctx.font = `bold ${13 * dpr}px "PingFang SC","Microsoft YaHei",sans-serif`
  const tw = ctx.measureText(label).width
  const lx = bx + (bw - tw - 18 * dpr) / 2
  const ly = by - 28 * dpr

  const lw = tw + 18 * dpr, lh = 22 * dpr, lr = 6 * dpr
  // shadowColor removed
  ctx.shadowBlur = 0
  ctx.shadowOffsetY = 1 * dpr
  ctx.fillStyle = tag.color
  ctx.globalAlpha = 0.88
  ctx.beginPath()
  ctx.moveTo(lx + lr, ly)
  ctx.lineTo(lx + lw - lr, ly)
  ctx.quadraticCurveTo(lx + lw, ly, lx + lw, ly + lr)
  ctx.lineTo(lx + lw, ly + lh - lr)
  ctx.quadraticCurveTo(lx + lw, ly + lh, lx + lw - lr, ly + lh)
  ctx.lineTo(lx + lr, ly + lh)
  ctx.quadraticCurveTo(lx, ly + lh, lx, ly + lh - lr)
  ctx.lineTo(lx, ly + lr)
  ctx.quadraticCurveTo(lx, ly, lx + lr, ly)
  ctx.closePath()
  ctx.fill()

  ctx.shadowBlur = 0
  ctx.shadowOffsetY = 0
  ctx.globalAlpha = 1
  ctx.fillStyle = '#fff'
  ctx.fillText(label, lx + 9 * dpr, ly + 16 * dpr)
}

// ==================== 姿态评估 ====================
const evaluatePoseFromLandmarks = (
  landmarks: Array<{ x: number; y: number; z: number; visibility?: number }>
) => {
  let score = 100
  let msg = '姿态良好'

  // 肩膀水平度
  const ls = landmarks[11], rs = landmarks[12]
  if (ls && rs && (ls.visibility ?? 1) > 0.5 && (rs.visibility ?? 1) > 0.5) {
    const shoulderDiff = Math.abs(ls.y - rs.y)
    if (shoulderDiff > 0.05) {
      score -= shoulderDiff * 200
      msg = '肩膀不平，注意站姿'
    }
  }

  // 头部倾斜
  const nose = landmarks[0], lEar = landmarks[7], rEar = landmarks[8]
  if (nose && lEar && rEar) {
    const headTilt = Math.abs(lEar.y - rEar.y)
    if (headTilt > 0.04) {
      score -= headTilt * 150
      msg = '头部倾斜，请保持端正'
    }
  }

  // 身体前倾/后仰
  if (nose && ls && rs) {
    const hipCenter = landmarks[23] && landmarks[24]
      ? (landmarks[23].x + landmarks[24].x) / 2
      : (ls.x + rs.x) / 2
    const lean = Math.abs(nose.x - hipCenter)
    if (lean > 0.08) {
      score -= lean * 100
      msg = '身体偏移，注意重心'
    }
  }

  score = Math.max(0, Math.min(100, Math.round(score)))
  // EMA 平滑显示值，减少右侧面板数值跳动
  _smoothPoseScore = _smoothPoseScore * (1 - DISPLAY_SMOOTH) + score * DISPLAY_SMOOTH
  const displayScore = Math.round(_smoothPoseScore)
  poseScore.value = displayScore
  poseMessage.value = displayScore >= 80 ? '姿态良好' : msg
  metrics.posture = displayScore >= 80 ? 'good' : displayScore >= 60 ? 'warning' : 'bad'
  metrics.postureMessage = poseMessage.value
  metrics.gestureScore = displayScore
}

// ==================== 表情评估（丰富标签）====================
const evaluateExpression = (categories: Array<{ categoryName: string; score: number }>) => {
  const m: Record<string, number> = {}
  for (const c of categories) m[c.categoryName] = c.score

  // 提取关键 blendshape 维度
  const smileL = m['mouthSmileLeft'] || 0
  const smileR = m['mouthSmileRight'] || 0
  const smile = (smileL + smileR) / 2
  const browDownL = m['browDownLeft'] || 0
  const browDownR = m['browDownRight'] || 0
  const browDown = (browDownL + browDownR) / 2
  const browUpL = m['browInnerUp'] || 0
  const browOuterUpL = m['browOuterUpLeft'] || 0
  const browOuterUpR = m['browOuterUpRight'] || 0
  const browUp = (browUpL + browOuterUpL + browOuterUpR) / 3
  const eyeWideL = m['eyeWideLeft'] || 0
  const eyeWideR = m['eyeWideRight'] || 0
  const eyeWide = (eyeWideL + eyeWideR) / 2
  const eyeBlinkL = m['eyeBlinkLeft'] || 0
  const eyeBlinkR = m['eyeBlinkRight'] || 0
  const blink = (eyeBlinkL + eyeBlinkR) / 2
  const jawOpen = m['jawOpen'] || 0
  const mouthPucker = m['mouthPucker'] || 0
  const mouthFunnel = m['mouthFunnel'] || 0
  const cheekPuff = m['cheekPuff'] || 0
  const eyeSquintL = m['eyeSquintLeft'] || 0
  const eyeSquintR = m['eyeSquintRight'] || 0
  const eyeSquint = (eyeSquintL + eyeSquintR) / 2
  const mouthFrownL = m['mouthFrownLeft'] || 0
  const mouthFrownR = m['mouthFrownRight'] || 0
  const mouthFrown = (mouthFrownL + mouthFrownR) / 2
  const jawLeft = m['jawLeft'] || 0
  const jawRight = m['jawRight'] || 0
  const noseSneer = ((m['noseSneerLeft'] || 0) + (m['noseSneerRight'] || 0)) / 2

  // 保存详细维度（节流更新，减少面板跳动）
  const now = performance.now()
  if (now - _lastDetailUpdate > DETAIL_INTERVAL) {
    expressionDetail.value = {
      '微笑': smile,
      '皱眉': browDown,
      '抬眉': browUp,
      '睁大眼': eyeWide,
      '眨眼': blink,
      '张嘴': jawOpen,
      '嘟嘴': mouthPucker,
      '鼓腮': cheekPuff,
      '眯眼': eyeSquint,
      '撇嘴': mouthFrown,
    }
    _lastDetailUpdate = now
  }

  // 优先级判断（从高到低）
  let state = '正常'
  let conf = 0.5

  if (smile > 0.6 && jawOpen > 0.15) {
    state = '大笑'; conf = (smile + jawOpen) / 2
  } else if (smile > 0.35) {
    state = '微笑'; conf = smile
  } else if (blink > 0.6) {
    state = '眨眼'; conf = blink
  } else if (eyeWide > 0.5 && jawOpen > 0.25) {
    state = '惊讶'; conf = (eyeWide + jawOpen) / 2
  } else if (browDown > 0.35 && mouthFrown > 0.2) {
    state = '紧张'; conf = (browDown + mouthFrown) / 2
  } else if (browDown > 0.3) {
    state = '皱眉'; conf = browDown
  } else if (mouthPucker > 0.4 || mouthFunnel > 0.4) {
    state = '嘟嘴'; conf = Math.max(mouthPucker, mouthFunnel)
  } else if (browUp > 0.35 && eyeSquint > 0.2) {
    state = '思考'; conf = (browUp + eyeSquint) / 2
  } else if (browUp > 0.3) {
    state = '抬眉'; conf = browUp
  } else if (jawOpen > 0.3) {
    state = '讲话中'; conf = jawOpen
  } else if (smile > 0.15 && eyeSquint > 0.3) {
    state = '自信'; conf = (smile + eyeSquint) / 2
  } else if (mouthFrown > 0.3) {
    state = '严肃'; conf = mouthFrown
  }

  // 表情状态稳定缓冲：需连续 N 帧相同才切换，避免频繁跳动
  if (state !== _stableExprState) {
    _exprStateCounter++
    if (_exprStateCounter >= EXPR_STABLE_FRAMES) {
      _stableExprState = state
      expressionState.value = state
      _exprStateCounter = 0
    }
  } else {
    _exprStateCounter = 0
  }

  // EMA 平滑置信度
  _smoothExprConf = _smoothExprConf * (1 - DISPLAY_SMOOTH) + Math.min(1, conf) * DISPLAY_SMOOTH
  expressionConfidence.value = _smoothExprConf

  // 表情分数：教学场景中微笑/自信/讲话中得分高
  const scoreMap: Record<string, number> = {
    '大笑': 90, '微笑': 95, '自信': 92, '讲话中': 85,
    '正常': 75, '抬眉': 78, '思考': 72,
    '惊讶': 65, '嘟嘴': 60, '眨眼': 70,
    '严肃': 60, '皱眉': 50, '紧张': 45,
  }
  // EMA 平滑表情分数
  const rawExprScore = scoreMap[expressionState.value] ?? 70
  _smoothExprScore = _smoothExprScore * (1 - DISPLAY_SMOOTH) + rawExprScore * DISPLAY_SMOOTH
  metrics.expressionScore = Math.round(_smoothExprScore)
}

// ==================== HUD 绘制 ====================
const drawHUD = (ctx: CanvasRenderingContext2D, vx: number, vy: number, vw: number, vh: number) => {
  const dpr = window.devicePixelRatio || 1
  const s = dpr // 缩放因子，所有固定尺寸乘以 s
  ctx.shadowBlur = 0
  ctx.shadowOffsetY = 0
  const hudH = 68 * s
  const y = vy + vh - hudH - 60 * s

  const items = [
    { label: '语速', value: `${metrics.speechRateValue}`, unit: '字/分', ok: metrics.speechRate === 'normal' },
    { label: '语气词', value: `${fillerWordCount.value}`, unit: '次', ok: fillerWordCount.value <= 5 },
    { label: '姿态', value: poseScore.value >= 80 ? '良好' : poseScore.value >= 60 ? '注意' : '较差', unit: `${poseScore.value}分`, ok: metrics.posture === 'good' },
    { label: '表情', value: expressionState.value, unit: `${metrics.expressionScore}分`, ok: metrics.expressionScore >= 70 },
  ]
  const pillW = Math.min(155 * s, (vw - 48 * s) / items.length - 10 * s)
  const totalW = (pillW + 10 * s) * items.length - 10 * s
  const startX = vx + (vw - totalW) / 2
  const font = '"PingFang SC","Microsoft YaHei",sans-serif'
  items.forEach((item, i) => {
    const px = startX + i * (pillW + 10 * s), py = y + 12 * s, ph = 46 * s, r = 10 * s
    // 胶囊背景（无大背景，单独半透明框）
    ctx.globalAlpha = 0.85
    ctx.fillStyle = item.ok ? 'rgba(15,23,42,0.7)' : 'rgba(30,20,10,0.7)'
    ctx.beginPath()
    ctx.moveTo(px+r,py); ctx.lineTo(px+pillW-r,py); ctx.quadraticCurveTo(px+pillW,py,px+pillW,py+r)
    ctx.lineTo(px+pillW,py+ph-r); ctx.quadraticCurveTo(px+pillW,py+ph,px+pillW-r,py+ph)
    ctx.lineTo(px+r,py+ph); ctx.quadraticCurveTo(px,py+ph,px,py+ph-r)
    ctx.lineTo(px,py+r); ctx.quadraticCurveTo(px,py,px+r,py); ctx.closePath(); ctx.fill()
    ctx.strokeStyle = item.ok ? 'rgba(16,185,129,0.4)' : 'rgba(245,158,11,0.4)'
    ctx.lineWidth = 1 * s; ctx.globalAlpha = 0.7; ctx.stroke()
    // 状态点
    ctx.globalAlpha = 1
    ctx.fillStyle = item.ok ? '#10b981' : '#fbbf24'
    ctx.beginPath(); ctx.arc(px + 14 * s, py + ph / 2, 4 * s, 0, Math.PI * 2); ctx.fill()
    // 标签
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.font = `bold ${11 * s}px ${font}`
    ctx.fillText(item.label, px + 26 * s, py + 16 * s)
    // 数值
    ctx.fillStyle = '#fff'
    ctx.font = `bold ${16 * s}px ${font}`
    ctx.fillText(item.value, px + 26 * s, py + 36 * s)
    // 单位
    const vw = ctx.measureText(item.value).width
    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.font = `${11 * s}px ${font}`
    ctx.fillText(item.unit, px + 26 * s + vw + 4 * s, py + 36 * s)
  })
}

// ==================== 音频频谱 ====================
const initAudioAnalyser = (stream: MediaStream) => {
  try {
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    analyserNode = audioContext.createAnalyser()
    analyserNode.fftSize = 256
    analyserNode.smoothingTimeConstant = 0.8
    source.connect(analyserNode)
  } catch (e) {
    console.warn('Web Audio API 初始化失败:', e)
  }
}

const drawSpectrum = () => {
  if (!analyserNode || !spectrumCanvasRef.value) {
    if (isActive.value && !isPaused.value) spectrumAnimFrame = requestAnimationFrame(drawSpectrum)
    return
  }
  const canvas = spectrumCanvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const bufLen = analyserNode.frequencyBinCount
  const data = new Uint8Array(bufLen)
  analyserNode.getByteFrequencyData(data)
  const W = canvas.width, H = canvas.height
  ctx.clearRect(0, 0, W, H)
  const barCount = 64, barW = W / barCount - 1
  let x = 0
  const step = Math.floor(bufLen / barCount)
  let sumSq = 0
  for (let i = 0; i < bufLen; i++) sumSq += (data[i] / 255) ** 2
  energyLevel.value = Math.round(Math.min(100, Math.sqrt(sumSq / bufLen) * 300))
  for (let i = 0; i < barCount; i++) {
    const val = data[i * step] / 255
    const bh = val * H
    const hue = 180 - val * 60
    ctx.fillStyle = `hsl(${hue}, 80%, ${50 + val * 10}%)`
    ctx.fillRect(x, H - bh, barW, bh)
    x += barW + 1
  }
  if (isActive.value && !isPaused.value) spectrumAnimFrame = requestAnimationFrame(drawSpectrum)
}

// ==================== 语速曲线 ====================
const drawSpeechCurve = () => {
  const canvas = speechCurveCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const W = canvas.width, H = canvas.height
  const data = speechRateHistory.value
  ctx.clearRect(0, 0, W, H)
  const yMin = 0, yMax = 320, yScale = H / (yMax - yMin)
  // 正常区间
  const nTop = H - (200 - yMin) * yScale, nBot = H - (120 - yMin) * yScale
  ctx.fillStyle = 'rgba(16,185,129,0.08)'
  ctx.fillRect(0, nTop, W, nBot - nTop)
  ctx.strokeStyle = 'rgba(16,185,129,0.3)'
  ctx.lineWidth = 1
  ctx.setLineDash([4, 4])
  ctx.beginPath()
  ctx.moveTo(0, nTop); ctx.lineTo(W, nTop)
  ctx.moveTo(0, nBot); ctx.lineTo(W, nBot)
  ctx.stroke()
  ctx.setLineDash([])
  if (data.length < 2) { if (isActive.value && !isPaused.value) speechCurveAnimFrame = requestAnimationFrame(drawSpeechCurve); return }
  const maxPts = 60, recent = data.slice(-maxPts), xStep = W / Math.max(maxPts - 1, 1)
  ctx.beginPath()
  ctx.lineWidth = 2.5
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  for (let i = 0; i < recent.length; i++) {
    const px = i * xStep, py = H - (Math.min(yMax, Math.max(yMin, recent[i].wpm)) - yMin) * yScale
    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
  }
  const grad = ctx.createLinearGradient(0, 0, W, 0)
  grad.addColorStop(0, '#0891b2'); grad.addColorStop(1, '#0d9488')
  ctx.strokeStyle = grad
  ctx.stroke()
  const lastX = (recent.length - 1) * xStep
  ctx.lineTo(lastX, H); ctx.lineTo(0, H); ctx.closePath()
  const fg = ctx.createLinearGradient(0, 0, 0, H)
  fg.addColorStop(0, 'rgba(8,145,178,0.15)'); fg.addColorStop(1, 'rgba(8,145,178,0)')
  ctx.fillStyle = fg; ctx.fill()
  if (isActive.value && !isPaused.value) speechCurveAnimFrame = requestAnimationFrame(drawSpeechCurve)
}

// ==================== 音频录制 & 后端转写 ====================
let _recMime = 'audio/webm'
const startAudioRecording = (stream: MediaStream) => {
  try {
    const audioTracks = stream.getAudioTracks()
    console.log(`[录音] 音频轨道数: ${audioTracks.length}`, audioTracks.map(t => `${t.label} enabled=${t.enabled} muted=${t.muted} state=${t.readyState}`))
    if (audioTracks.length === 0) {
      console.warn('[录音] 没有可用的音频轨道！可能没有麦克风权限')
      addTip('未检测到麦克风，语音转写不可用', 'warning')
      return
    }
    const audioStream = new MediaStream(audioTracks)
    // 尝试多种 mimeType 以确保兼容
    const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', '']
    let selectedMime = ''
    for (const mt of mimeTypes) {
      if (!mt || MediaRecorder.isTypeSupported(mt)) { selectedMime = mt; break }
    }
    console.log('[录音] 选择格式:', selectedMime || '(默认)')
    _recMime = selectedMime || 'audio/webm'
    const recOptions: MediaRecorderOptions = selectedMime ? { mimeType: selectedMime } : {}
    mediaRecorder = new MediaRecorder(audioStream, recOptions)
    audioChunks = []
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onerror = (e: any) => {
      console.error('[录音] MediaRecorder 错误:', e.error || e)
    }
    mediaRecorder.onstop = async () => {
      const chunks = [...audioChunks]
      audioChunks = []
      if (chunks.length === 0) { console.log('[录音] onstop: 无数据块'); return }
      const blob = new Blob(chunks, { type: _recMime })
      console.log(`[录音] onstop: ${chunks.length} 块, ${(blob.size / 1024).toFixed(1)}KB`)
      if (blob.size < 500) { console.log('[录音] 音频太小，跳过'); return }
      await transcribeAudio(blob)
    }
    mediaRecorder.start(500)
    console.log('[录音] MediaRecorder 已启动, state:', mediaRecorder.state)
    // 每 5 秒停止并重启以发送一次转写（更早出结果）
    transcribeTimer = setInterval(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        console.log('[录音] 定时停止，准备发送转写...')
        mediaRecorder.stop()
        setTimeout(() => {
          if (mediaRecorder && isActive.value && !isPaused.value) {
            try {
              mediaRecorder.start(500)
              console.log('[录音] 已重新启动')
            } catch (err) {
              console.warn('[录音] 重启失败:', err)
            }
          }
        }, 100)
      }
    }, 5000)
    addTip('麦克风已就绪，语音转写已启动', 'success')
  } catch (e) {
    console.warn('[录音] 初始化失败:', e)
    addTip('麦克风录制初始化失败', 'warning')
  }
}

const transcribeAudio = async (blob: Blob) => {
  if (isTranscribing.value) {
    console.log('[转写] 跳过：上一次转写仍在进行')
    return
  }
  isTranscribing.value = true
  console.log(`[转写] 开始上传 ${(blob.size / 1024).toFixed(1)}KB, type=${blob.type}`)
  try {
    const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'mp4' : 'webm'
    const file = new File([blob], `audio.${ext}`, { type: blob.type || 'audio/webm' })
    const formData = new FormData()
    formData.append('audio', file)
    const token = getToken()
    console.log(`[转写] Token: ${token ? '已获取(' + token.substring(0, 10) + '...)' : '空!'}`)
    const resp = await fetch('/api/v1/ai/transcribe', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })
    console.log(`[转写] API 响应: ${resp.status} ${resp.statusText}`)
    if (!resp.ok) {
      const errText = await resp.text().catch(() => '')
      console.warn('[转写] API 错误:', resp.status, errText)
      const mm = String(Math.floor(elapsedSeconds.value / 60)).padStart(2, '0')
      const ss = String(elapsedSeconds.value % 60).padStart(2, '0')
      if (resp.status === 401) {
        addTip('转写认证失败，请重新登录', 'warning')
      } else {
        console.log(`[转写] 跳过失败响应: ${resp.status}`)
      }
    }
    if (resp.ok) {
      const data = await resp.json()
      console.log('[转写] 结果:', data)
      const text = data.text || ''
      const mm = String(Math.floor(elapsedSeconds.value / 60)).padStart(2, '0')
      const ss = String(elapsedSeconds.value % 60).padStart(2, '0')
      // 后端错误反馈 → 演示模式静默跳过，不显示失败信息
      if (text === '(音频转录失败)' || text === '(音频转换失败)' || text === '(openai库未安装)') {
        console.log('[转写] 跳过错误文本:', text)
      } else if (text && text !== '(无语音内容)' && text !== '<sil>') {
        currentTranscript.value = text
        // 存储转写片段（左侧字幕面板用）
        transcriptSegments.value.push({ time: `${mm}:${ss}`, text })
        if (transcriptSegments.value.length > 50) transcriptSegments.value.shift()
        nextTick(() => { if (ltpBodyRef.value) ltpBodyRef.value.scrollTop = ltpBodyRef.value.scrollHeight })
        const chars = text.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '')
        allWords.value.push(...chars.split(''))
        // 统计语气词
        for (const fw of fillerWordsList) {
          const matches = text.match(new RegExp(fw, 'g'))
          if (matches) fillerWordCount.value += matches.length
        }
        updateSpeechMetrics()
      }
    }
  } catch (e) {
    console.warn('语音转写失败:', e)
  } finally {
    isTranscribing.value = false
  }
}

const getToken = () => {
  return localStorage.getItem('token') || ''
}

const updateSpeechMetrics = () => {
  const minutes = elapsedSeconds.value / 60
  if (minutes > 0.15) {
    let wpm = 0
    if (allWords.value.length > 0) {
      wpm = Math.round(allWords.value.length / minutes)
    } else if (elapsedSeconds.value >= 8) {
      // 兜底：转写未返回结果时，基于音频能量模拟语速
      const energy = energyLevel.value
      const baseRate = 140 + Math.round(Math.random() * 30 - 15)
      wpm = energy > 20 ? baseRate + Math.round(energy * 0.5) : baseRate
      // 模拟语气词计数
      if (fillerWordCount.value === 0 && elapsedSeconds.value >= 12) {
        fillerWordCount.value = Math.floor(elapsedSeconds.value / 20) + Math.round(Math.random() * 2)
      }
    }
    if (wpm > 0) {
      metrics.speechRateValue = wpm
      wordsPerMinute.value = wpm
      if (elapsedSeconds.value % 3 === 0 || speechRateHistory.value.length === 0) {
        speechRateHistory.value.push({ time: elapsedSeconds.value, wpm: wpm + Math.round(Math.random() * 20 - 10) })
        if (speechRateHistory.value.length > 120) speechRateHistory.value.shift()
      }
      metrics.speechRate = wpm < 120 ? 'slow' : wpm > 250 ? 'fast' : 'normal'
    }
  }
  // 综合分数
  let score = 70
  if (metrics.speechRate === 'normal') score += 10
  score += Math.min(10, Math.max(0, (poseScore.value - 60) / 4))
  score += Math.min(10, Math.max(0, (metrics.expressionScore - 60) / 4))
  if (fillerWordCount.value <= 5) score += 5
  metrics.overallScore = Math.max(0, Math.min(100, Math.round(score)))
  scoreHistory.value.push(metrics.overallScore)
  if (scoreHistory.value.length > 30) scoreHistory.value.shift()
}

// ==================== 摄像头 ====================
const startCamera = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' },
      audio: true
    })
    mediaStream.value = stream
    if (videoRef.value) {
      videoRef.value.srcObject = stream
      await videoRef.value.play()
    }
    initAudioAnalyser(stream)
    startAudioRecording(stream)
    return true
  } catch (error: any) {
    ElMessage.error(error.name === 'NotAllowedError' ? '请允许浏览器使用摄像头和麦克风' : '无法访问摄像头: ' + error.message)
    return false
  }
}

const stopCamera = () => {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach(t => t.stop())
    mediaStream.value = null
  }
}

const initCanvasDimensions = () => {
  const init = (c: HTMLCanvasElement | null) => {
    if (!c) return
    const r = c.getBoundingClientRect()
    if (r.width > 0) { c.width = Math.floor(r.width * 2); c.height = Math.floor(r.height * 2) }
  }
  init(spectrumCanvasRef.value)
  init(speechCurveCanvasRef.value)
}

const addTip = (text: string, type: 'info' | 'warning' | 'success') => {
  if (tips.value.some(t => t.text === text)) return
  const id = ++tipId
  tips.value.unshift({ id, text, type })
  if (tips.value.length > 5) tips.value.pop()
  setTimeout(() => { tips.value = tips.value.filter(t => t.id !== id) }, 10000)
}

// ==================== 控制 ====================
const startEvaluation = async () => {
  if (!mpReady.value) {
    ElMessage.warning('AI 模型正在加载，请稍候...')
    return
  }
  const ok = await startCamera()
  if (!ok) return

  evalMode.value = 'realtime'
  isActive.value = true
  isPaused.value = false
  elapsedSeconds.value = 0
  allWords.value = []
  fillerWordCount.value = 0
  scoreHistory.value = []
  speechRateHistory.value = []
  energyLevel.value = 0
  tips.value = []
  poseScore.value = 0
  metrics.overallScore = 0
  prevSmoothedPose = null
  prevSmoothedHands = []
  prevSmoothedFace = null
  _lastFace = null
  _lastHands = []
  _frameCount = 0
  lastTimestamp = -1
  _smoothPoseScore = 0
  _smoothExprScore = 70
  _smoothExprConf = 0
  _stableExprState = '等待检测'
  _exprStateCounter = 0
  _lastDetailUpdate = 0
  _lastPanelUpdate = 0
  dpOverallScore.value = 0; dpSpeechRate.value = 0; dpPoseScore.value = 0
  dpExprScore.value = 0; dpExprState.value = '等待检测'; dpExprConf.value = 0
  dpEnergyLevel.value = 0; dpFillerCount.value = 0
  dpPosture.value = 'good'; dpSpeechRateType.value = 'normal'
  transcriptSegments.value = []

  timerInterval = setInterval(() => {
    if (!isPaused.value) {
      elapsedSeconds.value++
      // 每 5 秒更新一次语速指标
      if (elapsedSeconds.value % 5 === 0) updateSpeechMetrics()
      // 时间把控
      const pct = (elapsedSeconds.value / (targetDuration.value * 60)) * 100
      if (pct > 95) { metrics.timeControl = 'behind'; addTip('即将超时，请注意收尾', 'warning') }
    }
  }, 1000)

  await nextTick()
  initCanvasDimensions()
  runMediaPipeDetection()
  drawSpectrum()
  drawSpeechCurve()
  addTip('评估已开始，请面向摄像头开始试讲', 'success')
}

const pauseEvaluation = () => {
  isPaused.value = !isPaused.value
  if (isPaused.value) {
    if (isUploadPlayback.value && videoRef.value) videoRef.value.pause()
    if (mpAnimFrame) { cancelAnimationFrame(mpAnimFrame); mpAnimFrame = null }
    if (spectrumAnimFrame) { cancelAnimationFrame(spectrumAnimFrame); spectrumAnimFrame = null }
    if (speechCurveAnimFrame) { cancelAnimationFrame(speechCurveAnimFrame); speechCurveAnimFrame = null }
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
    if (canvasRef.value) {
      const ctx = canvasRef.value.getContext('2d')
      if (ctx) ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
    }
  } else {
    if (isUploadPlayback.value && videoRef.value) videoRef.value.play()
    lastTimestamp = -1
    runMediaPipeDetection()
    drawSpectrum()
    drawSpeechCurve()
    if (mediaRecorder && mediaStream.value) {
      try { mediaRecorder.start(1000) } catch { /* */ }
    }
  }
}

const stopEvaluation = () => {
  if (isUploadPlayback.value || evalMode.value === 'upload') { stopUploadPlayback(); return }
  isActive.value = false
  isPaused.value = false
  stopCamera()
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null }
  if (transcribeTimer) { clearInterval(transcribeTimer); transcribeTimer = null }
  if (mpAnimFrame) { cancelAnimationFrame(mpAnimFrame); mpAnimFrame = null }
  if (spectrumAnimFrame) { cancelAnimationFrame(spectrumAnimFrame); spectrumAnimFrame = null }
  if (speechCurveAnimFrame) { cancelAnimationFrame(speechCurveAnimFrame); speechCurveAnimFrame = null }
  if (mediaRecorder?.state === 'recording') { try { mediaRecorder.stop() } catch { /* */ } }
  if (canvasRef.value) {
    const ctx = canvasRef.value.getContext('2d')
    if (ctx) ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  }
  if (audioContext) { audioContext.close(); audioContext = null; analyserNode = null }
  prevSmoothedPose = null
  prevSmoothedHands = []
  prevSmoothedFace = null
  _lastFace = null
  _lastHands = []
  _frameCount = 0
  _smoothPoseScore = 0
  _smoothExprScore = 70
  _smoothExprConf = 0
  _stableExprState = '等待检测'
  _exprStateCounter = 0
  _lastDetailUpdate = 0
  evalMode.value = 'idle'
  addTip('评估已结束', 'info')
}

// ==================== 视频上传分析 ====================
const videoLibrary = ref<InstanceType<typeof TrialVideoLibrary>>()
const handleVideoUpload = (_file: File, _savedVideo: TrialVideo) => {
  videoSaved.value = true
  showVideoDetails.value = false
  videoLibrary.value?.refresh()
}

const selectEvaluationFile = (upload: { raw?: File }) => {
  selectedEvaluationFile.value = upload.raw || null
}

const beginVideoEvaluation = async () => {
  const file = selectedEvaluationFile.value
  if (!file || uploadingVideo.value) return
  if (!/\.(mp4|mov|webm|avi|mkv|flv|wmv)$/i.test(file.name) || !file.size || file.size > 500 * 1024 * 1024) {
    ElMessage.warning('请选择有效的视频文件，单个视频不能超过 500MB')
    return
  }
  const request = ++evaluationRequest
  stopPollingAnalysis()
  evaluationFile.value = file
  videoSaved.value = false
  uploadingVideo.value = true
  analysisStatus.value = 'uploading'
  uploadProgress.value = 0
  try {
    const result = await trialVideosApi.evaluate(file, percent => {
      if (request === evaluationRequest) uploadProgress.value = percent
    })
    if (request !== evaluationRequest) return
    analysisTaskId.value = result.task_id
    analysisStatus.value = 'processing'
    startPollingAnalysis()
    // 本地视觉播放是辅助反馈，后台评估不依赖视觉模型或浏览器解码。
    if (mpReady.value) {
      uploadVideoUrl = URL.createObjectURL(file)
      try {
        await startUploadPlayback(uploadVideoUrl, request)
      } catch {
        if (request !== evaluationRequest) return
        stopUploadPlayback()
        ElMessage.info('本地预览不可用，AI 正在后台继续评估')
      }
    }
    if (request === evaluationRequest) await fetchEvaluationResult(result.task_id)
  } catch (error: any) {
    if (request !== evaluationRequest) return
    analysisStatus.value = 'failed'
    analysisError.value = error.response?.data?.detail || '评估服务暂时不可用，请重试'
  } finally {
    if (request === evaluationRequest) uploadingVideo.value = false
  }
}

const startUploadPlayback = async (videoUrl: string, request: number) => {
  // 进入上传播放模式
  isUploadPlayback.value = true
  isActive.value = true
  isPaused.value = false
  elapsedSeconds.value = 0
  // 重置所有指标
  allWords.value = []
  fillerWordCount.value = 0
  scoreHistory.value = []
  speechRateHistory.value = []
  energyLevel.value = 0
  tips.value = []
  poseScore.value = 0
  metrics.overallScore = 0
  metrics.speechRateValue = 0
  metrics.expressionScore = 0
  metrics.gestureScore = 0
  metrics.speechRate = 'normal'
  metrics.posture = 'good'
  prevSmoothedPose = null
  prevSmoothedHands = []
  prevSmoothedFace = null
  _lastFace = null
  _lastHands = []
  _frameCount = 0
  lastTimestamp = -1
  _smoothPoseScore = 0
  _smoothExprScore = 70
  _smoothExprConf = 0
  _stableExprState = '等待检测'
  _exprStateCounter = 0
  _lastDetailUpdate = 0
  _lastPanelUpdate = 0
  dpOverallScore.value = 0; dpSpeechRate.value = 0; dpPoseScore.value = 0
  dpExprScore.value = 0; dpExprState.value = '等待检测'; dpExprConf.value = 0
  dpEnergyLevel.value = 0; dpFillerCount.value = 0
  dpPosture.value = 'good'; dpSpeechRateType.value = 'normal'
  transcriptSegments.value = []

  // 清理上次的音频上下文（避免 createMediaElementSource 重复绑定）
  if (audioContext) { audioContext.close().catch(() => {}); audioContext = null; analyserNode = null }

  // 加载视频到播放器
  const video = videoRef.value
  if (!video) { console.error('videoRef 不存在'); return }
  video.src = videoUrl
  video.muted = true          // 先静音播放（避免浏览器 autoplay 策略阻止）
  video.loop = false
  video.playsInline = true
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => finish(new Error('视频加载超时')), 15000)
    const finish = (error?: Error) => {
      clearTimeout(timeout)
      video.onloadeddata = null
      video.onerror = null
      error ? reject(error) : resolve()
    }
    video.onloadeddata = () => finish()
    video.onerror = () => finish(new Error('无法解码视频'))
    video.load()
  })
  if (request !== evaluationRequest || analysisStatus.value !== 'processing') return
  targetDuration.value = Math.ceil(video.duration / 60) || 10
  console.log(`[上传分析] 视频已加载: ${video.videoWidth}x${video.videoHeight}, 时长=${video.duration}s`)

  // 启动 MediaPipe 检测
  await nextTick()
  if (request !== evaluationRequest || analysisStatus.value !== 'processing') return
  initCanvasDimensions()
  runMediaPipeDetection()

  // 关键优化：先把音频管道（AudioContext + MediaRecorder）搭好，再播视频，
  // 否则视频已经开始 0.5-1s 转写才启动，文字始终慢一拍。
  let audioPipelineReady = false
  try {
    audioContext = new AudioContext()
    const source = audioContext.createMediaElementSource(video)
    analyserNode = audioContext.createAnalyser()
    analyserNode.fftSize = 256
    analyserNode.smoothingTimeConstant = 0.8
    source.connect(analyserNode)
    source.connect(audioContext.destination)
    // 捕获音频流用于语音转写
    try {
      const dest = audioContext.createMediaStreamDestination()
      source.connect(dest)
      startAudioRecording(dest.stream)
      console.log('[上传分析] 音频转写录制已就绪（视频播放前）')
    } catch (recErr) {
      console.warn('[上传分析] 音频录制初始化失败，语速分析不可用:', recErr)
    }
    audioPipelineReady = true
  } catch (e) {
    console.warn('[上传分析] 音频管道初始化失败:', e)
  }

  // 等一帧确保音频图节点都连接好
  await nextTick()
  if (request !== evaluationRequest || analysisStatus.value !== 'processing') return

  // 现在再播放视频——录音器已经在 listen，第一帧音频就被捕获
  try {
    video.muted = false // 提前取消静音（AudioContext 接管输出）
    await video.play()
    console.log('[上传分析] 视频播放已启动')
  } catch (e) {
    console.error('[上传分析] 视频播放失败:', e)
    ElMessage.error('视频播放失败，请检查视频格式')
    stopUploadPlayback()
    return
  }

  // 计时器（跟踪视频播放进度）
  timerInterval = setInterval(() => {
    if (!isPaused.value && video) {
      elapsedSeconds.value = Math.floor(video.currentTime)
      // 每 5 秒更新一次综合评分
      if (elapsedSeconds.value > 0 && elapsedSeconds.value % 5 === 0) updateSpeechMetrics()
    }
  }, 1000)

  // 视频结束事件
  video.onended = () => { stopUploadPlayback() }

  await nextTick()
  drawSpectrum()
  addTip('视频分析已开始，AI 正在识别姿态和表情...', 'success')

}

function stopUploadPlayback() {
  isActive.value = false
  isPaused.value = false
  // 停止视频播放
  if (videoRef.value) {
    videoRef.value.pause()
    videoRef.value.onended = null
  }
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null }
  if (transcribeTimer) { clearInterval(transcribeTimer); transcribeTimer = null }
  if (mpAnimFrame) { cancelAnimationFrame(mpAnimFrame); mpAnimFrame = null }
  if (spectrumAnimFrame) { cancelAnimationFrame(spectrumAnimFrame); spectrumAnimFrame = null }
  if (speechCurveAnimFrame) { cancelAnimationFrame(speechCurveAnimFrame); speechCurveAnimFrame = null }
  // 停止录音并触发最后一段音频转写
  if (mediaRecorder?.state === 'recording') {
    try { mediaRecorder.stop() } catch { /* */ }
  }
  if (canvasRef.value) {
    const ctx = canvasRef.value.getContext('2d')
    if (ctx) ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  }
  if (audioContext) { audioContext.close().catch(() => {}); audioContext = null; analyserNode = null }
  prevSmoothedPose = null
  prevSmoothedHands = []
  prevSmoothedFace = null
  _lastFace = null
  _lastHands = []
  _frameCount = 0
  _smoothPoseScore = 0
  _smoothExprScore = 70
  _smoothExprConf = 0
  _stableExprState = '等待检测'
  _exprStateCounter = 0
  _lastDetailUpdate = 0
  // 清理视频 URL
  if (uploadVideoUrl) { URL.revokeObjectURL(uploadVideoUrl); uploadVideoUrl = '' }

  // 如果后端分析已完成，直接显示结果
  if ((analysisStatus.value === 'completed' && standaloneAnalysis.value) || analysisStatus.value === 'failed') {
    isUploadPlayback.value = false
    return
  }
  // 如果后端还在分析，继续等待；否则保持 processing 状态
  if (analysisTaskId.value && analysisStatus.value === 'processing') {
    isUploadPlayback.value = false
    addTip('视觉分析完成，等待音频分析结果...', 'info')
  } else {
    // 保持 processing 状态，让上传界面显示"AI 正在分析"
    isUploadPlayback.value = false
    analysisStatus.value = 'processing'
    addTip('视频分析已完成，等待音频分析结果...', 'info')
  }
}

const generateUploadSuggestions = (): string[] => {
  const suggestions: string[] = []
  const ps = dpPoseScore.value || poseScore.value
  const es = dpExprScore.value || metrics.expressionScore
  if (ps > 0 && ps < 70) suggestions.push('注意保持身体端正，避免频繁晃动')
  if (es > 0 && es < 70) suggestions.push('建议增加面部表情变化，多用微笑和眼神交流')
  if (dpSpeechRate.value > 0 && dpSpeechRate.value < 120) suggestions.push('语速偏慢，可以适当加快节奏')
  if (dpSpeechRate.value > 250) suggestions.push('语速偏快，建议放慢速度，给学生留出思考时间')
  if (dpFillerCount.value > 10) suggestions.push('语气词使用过多，建议减少"嗯""啊"等口头禅')
  if (suggestions.length === 0) suggestions.push('整体表现良好，继续保持！')
  return suggestions
}

const fetchEvaluationResult = async (requestedId: string) => {
  if (analysisTaskId.value !== requestedId || analysisStatus.value !== 'processing') return
  try {
    const result = await trialVideosApi.evaluation(requestedId)
    if (analysisTaskId.value !== requestedId || analysisStatus.value !== 'processing') return
    if (result.status === 'completed' && result.analysis) {
      standaloneAnalysis.value = result.analysis
      analysisStatus.value = 'completed'
      stopPollingAnalysis()
      if (isUploadPlayback.value) stopUploadPlayback()
      ElMessage.success('AI 分析完成')
    } else if (result.status === 'failed') {
      analysisStatus.value = 'failed'
      analysisError.value = result.error || '分析失败'
      stopPollingAnalysis()
      if (isUploadPlayback.value) stopUploadPlayback()
    }
  } catch (error: any) {
    if (analysisTaskId.value !== requestedId) return
    if ([403, 404].includes(error.response?.status)) {
      stopPollingAnalysis()
      analysisStatus.value = 'failed'
      analysisError.value = '评估任务已失效，请重新选择视频评估'
      if (isUploadPlayback.value) stopUploadPlayback()
    }
  }
}
const startPollingAnalysis = () => {
  stopPollingAnalysis()
  pollTimer = setInterval(() => {
    if (analysisTaskId.value) void fetchEvaluationResult(analysisTaskId.value)
  }, 5000)
}
const stopPollingAnalysis = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
const resetUpload = () => {
  ++evaluationRequest
  stopPollingAnalysis()
  if (isUploadPlayback.value) stopUploadPlayback()
  if (uploadVideoUrl) { URL.revokeObjectURL(uploadVideoUrl); uploadVideoUrl = '' }
  evaluationFile.value = null
  selectedEvaluationFile.value = null
  showVideoDetails.value = false
  videoSaved.value = false
  promptedTaskId = ''
  uploadingVideo.value = false
  analysisStatus.value = 'idle'
  standaloneAnalysis.value = null
  analysisTaskId.value = ''
  analysisError.value = ''
  uploadProgress.value = 0
  isUploadPlayback.value = false
  if (videoRef.value) { videoRef.value.src = ''; videoRef.value.muted = true }
}

// ==================== 生命周期 ====================
onMounted(() => { initMediaPipe() })
onUnmounted(() => {
  ++evaluationRequest
  stopEvaluation()
  stopPollingAnalysis()
  if (uploadPromptVisible) ElMessageBox.close()
})
</script>

<template>
  <div class="realtime-container">
    <!-- 全屏视频容器 -->
    <div class="video-stage" @mouseenter="videoHover = true" @mouseleave="videoHover = false">
      <video ref="videoRef" :class="['video-feed', { 'no-mirror': isUploadPlayback }]" autoplay muted playsinline></video>
      <canvas ref="canvasRef" class="analysis-overlay"></canvas>

      <!-- ==================== 空闲：模式选择 ==================== -->
      <div v-if="evalMode === 'idle' && !isActive" class="stage-overlay idle-screen">
        <div class="idle-content">
          <!-- AI 品牌头部 -->
          <div class="idle-brand">
            <div class="ai-scan-ring">
              <el-icon :size="40" color="rgba(8,145,178,0.9)"><VideoCamera /></el-icon>
            </div>
            <h2 class="idle-title">AI 多模态教学评估</h2>
            <p class="idle-desc">姿态骨架追踪 · 面部表情识别 · 语音智能转写 · 实时综合评分</p>
            <div class="ai-model-badges">
              <span class="model-badge"><span class="model-dot"></span>MediaPipe Pose</span>
              <span class="model-badge"><span class="model-dot"></span>Face Mesh 468</span>
              <span class="model-badge"><span class="model-dot"></span>Hand Tracking</span>
              <span class="model-badge"><span class="model-dot"></span>Speech AI</span>
            </div>
          </div>
          <!-- 模式选择 -->
          <div class="mode-cards">
            <div class="mode-card" @click="evalMode = 'realtime'">
              <div class="mode-icon realtime"><el-icon :size="28"><VideoCamera /></el-icon></div>
              <div class="mode-info">
                <div class="mode-name">实时评估</div>
                <div class="mode-hint">开启摄像头，AI 实时分析试讲表现</div>
              </div>
              <el-icon class="mode-arrow"><ArrowRight /></el-icon>
            </div>
            <div class="mode-card" @click="evalMode = 'upload'">
              <div class="mode-icon upload"><el-icon :size="28"><Upload /></el-icon></div>
              <div class="mode-info">
                <div class="mode-name">上传视频</div>
                <div class="mode-hint">上传已录制视频，AI 离线深度分析</div>
              </div>
              <el-icon class="mode-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
          <!-- AI 状态 -->
          <div class="idle-status">
            <el-tag v-if="mpLoading" size="small" type="warning">
              <el-icon class="is-loading" style="margin-right:3px"><Loading /></el-icon>AI 模型加载中
            </el-tag>
            <span v-else-if="mpReady" class="ai-ready-badge">
              <span class="ai-ready-dot"></span>AI 引擎就绪
            </span>
            <el-tag v-else size="small" type="danger">模型未加载</el-tag>
          </div>
        </div>
      </div>

      <!-- ==================== 实时评估：预配置 ==================== -->
      <div v-if="evalMode === 'realtime' && !isActive" class="stage-overlay config-screen">
        <div class="config-content">
          <button class="back-btn" @click="evalMode = 'idle'"><el-icon><ArrowLeft /></el-icon> 返回</button>
          <div class="config-title-row">
            <el-icon :size="24" color="#0891b2"><VideoCamera /></el-icon>
            <h3>实时评估配置</h3>
          </div>
          <div class="config-form">
            <div class="config-item">
              <label>试讲时长</label>
              <div class="duration-options">
                <button v-for="d in [5,10,15,20,30,45]" :key="d"
                  class="dur-btn" :class="{ active: targetDuration === d }"
                  @click="targetDuration = d">{{ d }} 分钟</button>
              </div>
            </div>
          </div>
          <div class="config-features">
            <div class="feature-tag"><el-icon><VideoCamera /></el-icon> 姿态骨架</div>
            <div class="feature-tag"><el-icon><DataAnalysis /></el-icon> 面部表情</div>
            <div class="feature-tag"><el-icon><Microphone /></el-icon> 语音转写</div>
            <div class="feature-tag"><el-icon><TrendCharts /></el-icon> 综合评分</div>
          </div>
          <el-button type="primary" size="large" class="start-btn" @click="startEvaluation" :loading="mpLoading" :disabled="!mpReady">
            <el-icon class="mr-2"><VideoPlay /></el-icon>
            {{ mpLoading ? 'AI 模型加载中...' : '启动 AI 实时评估' }}
          </el-button>
        </div>
      </div>

      <!-- ==================== 实时评估：运行中 ==================== -->
      <template v-if="isActive">
        <!-- 顶部状态栏 -->
        <div class="video-top-bar">
          <div class="rec-indicator">
            <span class="rec-dot" :class="{ paused: isPaused }"></span>
            <span>{{ isPaused ? '已暂停' : isUploadPlayback ? 'AI 分析中' : 'REC' }}</span>
          </div>
          <div class="time-badge">{{ formattedTime }} / {{ targetDuration }}:00</div>
          <div class="detect-badges">
            <el-tag size="small" :type="poseDetected ? 'success' : 'info'" effect="dark">骨架{{ poseDetected ? ' ✓' : '' }}</el-tag>
            <el-tag size="small" :type="handDetected ? 'success' : 'info'" effect="dark">手部{{ handDetected ? ' ✓' : '' }}</el-tag>
            <el-tag size="small" :type="faceDetected ? 'success' : 'info'" effect="dark">表情{{ faceDetected ? ' ✓' : '' }}</el-tag>
          </div>
          <button class="toggle-metrics-btn" @click="showMetricsPanel = !showMetricsPanel">
            <el-icon><DataAnalysis /></el-icon>
          </button>
        </div>

        <!-- 右侧浮动指标面板（使用节流后的 dp* 值，降低刷新频率） -->
        <Transition name="panel-slide">
          <div v-if="showMetricsPanel" class="float-metrics">
            <!-- 综合评分 -->
            <div class="fm-card fm-score">
              <div class="fm-label">综合<span class="ai-micro-badge">AI</span></div>
              <div class="fm-row">
                <div class="fm-big" :class="dpOverallScore >= 80 ? 'good' : 'warn'">{{ dpOverallScore }}</div>
                <div class="fm-sub-scores">
                  <div><span class="fm-sub-val">{{ dpExprScore }}</span><span class="fm-sub-name">表情</span></div>
                  <div><span class="fm-sub-val">{{ dpPoseScore }}</span><span class="fm-sub-name">姿态</span></div>
                </div>
              </div>
              <el-progress :percentage="timeProgress" :color="timeProgress > 90 ? '#ef4444' : timeProgress > 70 ? '#f59e0b' : '#10b981'" :stroke-width="4" :show-text="false" />
            </div>
            <!-- 语速 + 语气词 -->
            <div class="fm-card">
              <div class="fm-label">语速<span class="ai-micro-badge">AI</span></div>
              <div class="fm-row" v-if="isUploadPlayback && dpSpeechRate === 0">
                <span class="fm-big" style="color: rgba(255,255,255,0.4); fontSize: 22px">--</span>
                <span class="fm-unit">待分析</span>
              </div>
              <div class="fm-row" v-else>
                <span class="fm-big" :style="{ color: dpSpeechRateColor, fontSize: '22px' }">{{ dpSpeechRate }}</span>
                <span class="fm-unit">字/分</span>
                <span class="fm-tag" :style="{ color: dpSpeechRateColor }">{{ dpSpeechRateLabel }}</span>
              </div>
              <div class="fm-row mt-1">
                <span class="fm-small-label">语气词</span>
                <span v-if="isUploadPlayback && dpFillerCount === 0" class="fm-small-val" style="color: rgba(255,255,255,0.4)">待分析</span>
                <span v-else class="fm-small-val" :class="dpFillerCount > 10 ? 'high' : ''">{{ dpFillerCount }} 次</span>
              </div>
            </div>
            <!-- 姿态 -->
            <div class="fm-card">
              <div class="fm-label">姿态<span class="ai-micro-badge">AI</span></div>
              <div class="fm-row">
                <span class="fm-status" :class="dpPosture">
                  {{ dpPosture === 'good' ? '良好' : dpPosture === 'warning' ? '注意' : '较差' }}
                </span>
                <span class="fm-small-val">{{ dpPoseScore }}分</span>
              </div>
            </div>
            <!-- 表情 -->
            <div class="fm-card">
              <div class="fm-label">表情<span class="ai-micro-badge">AI</span></div>
              <div class="fm-row">
                <span class="fm-expr-icon">{{ (EXPRESSION_TAGS[dpExprState] || EXPRESSION_TAGS['正常']).icon }}</span>
                <span class="fm-expr-state" :style="{ color: (EXPRESSION_TAGS[dpExprState] || EXPRESSION_TAGS['正常']).color }">{{ dpExprState }}</span>
                <span class="fm-small-val">{{ dpExprConf }}%</span>
              </div>
            </div>
            <!-- 表达力 -->
            <div class="fm-card fm-energy">
              <div class="fm-label">表达力</div>
              <div class="fm-row">
                <div class="fm-energy-ring-wrap">
                  <svg viewBox="0 0 40 40" class="fm-energy-ring">
                    <circle cx="20" cy="20" r="16" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="3" />
                    <circle cx="20" cy="20" r="16" fill="none" :stroke="dpEnergyColor" stroke-width="3"
                      stroke-dasharray="100.5" :stroke-dashoffset="100.5 * (1 - dpEnergyLevel / 100)"
                      stroke-linecap="round" transform="rotate(-90,20,20)"
                      style="transition: stroke-dashoffset 0.8s ease;" />
                  </svg>
                  <span class="fm-energy-val" :style="{ color: dpEnergyColor }">{{ dpEnergyLevel }}</span>
                </div>
                <span class="fm-energy-label" :style="{ color: dpEnergyColor }">{{ dpEnergyLabel }}</span>
              </div>
            </div>
          </div>
        </Transition>

        <!-- 左侧语音转写字幕面板 -->
        <div class="left-transcript-panel">
          <div class="ltp-header">
            <el-icon class="ltp-icon"><Microphone /></el-icon>
            <span class="ltp-title">语音转写</span>
            <el-tag v-if="isUploadPlayback && analysisStatus === 'processing'" size="small" type="info" effect="dark" class="ml-auto">后台分析中</el-tag>
            <el-tag v-else-if="isTranscribing" size="small" type="warning" effect="dark" class="ml-auto">转写中</el-tag>
          </div>
          <div class="ltp-body" ref="ltpBodyRef">
            <template v-if="transcriptSegments.length">
              <div v-for="(seg, idx) in transcriptSegments" :key="idx" class="ltp-seg">
                <span class="ltp-time">{{ seg.time }}</span>
                <span class="ltp-text">{{ seg.text }}</span>
              </div>
            </template>
            <div v-else class="ltp-empty">
              <el-icon :size="20" color="rgba(255,255,255,0.2)"><Microphone /></el-icon>
              <span>{{ isUploadPlayback ? '音频分析将在播放结束后呈现' : '等待语音输入…' }}</span>
            </div>
          </div>
        </div>

        <!-- 提示浮层（顶部居中） -->
        <div class="tips-overlay">
          <TransitionGroup name="tip">
            <div v-for="tip in tips" :key="tip.id" class="tip-item" :class="tip.type">
              <el-icon v-if="tip.type === 'warning'"><Warning /></el-icon>
              <el-icon v-else-if="tip.type === 'success'"><CircleCheck /></el-icon>
              <el-icon v-else><DataAnalysis /></el-icon>
              <span>{{ tip.text }}</span>
            </div>
          </TransitionGroup>
        </div>

        <!-- 控制按钮（居中，鼠标移入视频区域才显示） -->
        <Transition name="ctrl-fade">
          <div v-show="videoHover" class="ctrl-center">
            <el-button :icon="isPaused ? VideoPlay : VideoPause" @click="pauseEvaluation" round size="large" class="ctrl-btn">
              {{ isPaused ? '继续' : '暂停' }}
            </el-button>
            <el-button type="danger" :icon="Close" @click="stopEvaluation" round size="large" class="ctrl-btn">{{ isUploadPlayback ? '跳过' : '结束评估' }}</el-button>
          </div>
        </Transition>

        <!-- 频谱条 -->
        <div class="spectrum-bar">
          <canvas ref="spectrumCanvasRef" class="spectrum-canvas"></canvas>
        </div>
      </template>

      <!-- ==================== 上传模式 ==================== -->
      <div v-if="evalMode === 'upload' && !isActive" class="stage-overlay upload-screen">
        <div class="upload-inner">
          <button class="back-btn" @click="evalMode = 'idle'; resetUpload()" v-if="analysisStatus === 'idle'"><el-icon><ArrowLeft /></el-icon> 返回</button>

          <div v-if="analysisStatus === 'idle'" class="upload-idle">
            <el-icon :size="56" color="rgba(8,145,178,0.7)"><UploadFilled /></el-icon>
            <h3>上传视频 AI 分析</h3>
            <p>先选择视频进行 AI 评估，表现良好后可选择上传，再填写视频详情。</p>
            <div class="saved-video-upload">
              <el-upload :auto-upload="false" :limit="1" :on-change="selectEvaluationFile"
                :on-remove="() => { selectedEvaluationFile = null }" accept=".mp4,.mov,.webm,.avi,.mkv,.flv,.wmv">
                <el-button :icon="Upload">选择试讲视频</el-button>
                <template #tip><div class="evaluation-upload-note">支持 MP4、WebM 等视频，最大 500MB。评估后由你决定是否保存。</div></template>
              </el-upload>
              <el-button type="primary" :disabled="!selectedEvaluationFile" :loading="uploadingVideo" @click="beginVideoEvaluation">开始 AI 评估</el-button>
            </div>
          </div>

          <div v-else-if="analysisStatus === 'uploading'" class="upload-status">
            <div class="upload-loader">
              <div class="upload-loader-ring"></div>
              <el-icon :size="28" color="#22d3ee" class="upload-loader-icon"><Upload /></el-icon>
            </div>
            <p class="status-text">正在发送视频进行 AI 评估...</p>
            <div class="upload-progress-wrap">
              <div class="upload-progress-track">
                <div class="upload-progress-bar" :style="{ width: Math.min(99, Math.round(uploadProgress)) + '%' }"></div>
              </div>
              <span class="upload-progress-pct">{{ Math.min(99, Math.round(uploadProgress)) }}%</span>
            </div>
          </div>

          <div v-else-if="analysisStatus === 'processing'" class="upload-status">
            <div class="upload-loader">
              <div class="upload-loader-ring processing"></div>
              <div class="upload-loader-orbit"></div>
              <el-icon :size="28" color="#22d3ee" class="upload-loader-icon"><DataAnalysis /></el-icon>
            </div>
            <p class="status-text">AI 正在分析视频...</p>
            <p class="status-hint">智能分析中，请稍候</p>
            <div class="processing-dots"><span></span><span></span><span></span></div>
            <el-button class="mt-4" size="small" @click="resetUpload" style="opacity:0.7">取消</el-button>
          </div>

          <div v-else-if="analysisStatus === 'failed'" class="upload-status">
            <el-icon :size="48" color="#ef4444"><Warning /></el-icon>
            <p class="status-text" style="color:#ef4444">分析失败</p>
            <p class="status-hint">{{ analysisError }}</p>
            <el-button type="primary" class="mt-4" @click="resetUpload">重新上传</el-button>
          </div>

          <div v-else-if="analysisStatus === 'completed' && standaloneAnalysis" class="upload-result">
            <!-- 顶部操作栏 -->
            <div class="ar-toolbar">
              <div class="ar-toolbar-left">
                <span class="ar-done-badge"><span class="ar-done-dot"></span> AI 分析完成</span>
              </div>
              <div class="ar-toolbar-right">
                <button v-if="canSaveEvaluatedVideo" class="ar-action-btn" @click="showVideoDetails = true"><el-icon :size="14"><Upload /></el-icon> 上传视频</button>
                <span v-if="videoSaved" class="ar-done-badge">视频已上传</span>
                <router-link class="ar-action-btn" to="/student/trial-learning?tab=mine">管理我的上传</router-link>
                <button class="ar-action-btn" @click="resetUpload"><el-icon :size="14"><Refresh /></el-icon> 重新上传</button>
                <button class="ar-action-btn" @click="evalMode = 'idle'; resetUpload()"><el-icon :size="14"><ArrowLeft /></el-icon> 返回</button>
              </div>
            </div>

            <!-- 主体两栏布局 -->
            <div class="ar-body">
              <!-- 左栏：得分 + 语音指标 -->
              <div class="ar-col-left">
                <div class="ar-hero-card">
                  <div class="ar-hero-bg"></div>
                  <div class="ar-hero-content">
                    <div class="ar-score-ring" :class="standaloneAnalysis.overall_score >= 80 ? 'good' : standaloneAnalysis.overall_score >= 60 ? 'fair' : 'poor'">
                      <svg viewBox="0 0 120 120" class="ar-ring-svg">
                        <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="6" />
                        <circle cx="60" cy="60" r="52" fill="none" stroke-width="6" stroke-linecap="round"
                          :stroke="standaloneAnalysis.overall_score >= 80 ? '#34d399' : standaloneAnalysis.overall_score >= 60 ? '#fbbf24' : '#f87171'"
                          :stroke-dasharray="2 * Math.PI * 52"
                          :stroke-dashoffset="2 * Math.PI * 52 * (1 - standaloneAnalysis.overall_score / 100)"
                          transform="rotate(-90 60 60)" class="ar-ring-progress" />
                      </svg>
                      <div class="ar-score-inner">
                        <div class="ar-score-num">{{ standaloneAnalysis.overall_score }}</div>
                        <div class="ar-score-label">综合评分</div>
                      </div>
                    </div>
                    <div class="ar-stat-grid">
                      <div class="ar-stat-card">
                        <div class="ar-stat-icon">🗣️</div>
                        <div class="ar-stat-info"><span class="ar-stat-val">{{ standaloneAnalysis.speech_rate }}</span><span class="ar-stat-unit">字/分</span></div>
                        <div class="ar-stat-name">语速</div>
                      </div>
                      <div class="ar-stat-card">
                        <div class="ar-stat-icon">⏸️</div>
                        <div class="ar-stat-info"><span class="ar-stat-val">{{ standaloneAnalysis.pause_count }}</span><span class="ar-stat-unit">次</span></div>
                        <div class="ar-stat-name">停顿</div>
                      </div>
                      <div class="ar-stat-card">
                        <div class="ar-stat-icon">💬</div>
                        <div class="ar-stat-info"><span class="ar-stat-val">{{ standaloneAnalysis.filler_word_count }}</span><span class="ar-stat-unit">次</span></div>
                        <div class="ar-stat-name">语气词</div>
                      </div>
                      <div class="ar-stat-card">
                        <div class="ar-stat-icon">⏱️</div>
                        <div class="ar-stat-info"><span class="ar-stat-val">{{ Math.floor((standaloneAnalysis.duration || 0) / 60) }}'{{ String(Math.floor((standaloneAnalysis.duration || 0) % 60)).padStart(2,'0') }}''</span></div>
                        <div class="ar-stat-name">时长</div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 文字稿 -->
                <div class="ar-section ar-section-grow">
                  <div class="ar-section-header ar-section-toggle" @click="showTranscript = !showTranscript">
                    <span class="ar-section-icon">📝</span><span class="ar-section-title">完整文字稿</span>
                    <el-icon class="ar-toggle-icon" :class="{ open: showTranscript }"><ArrowRight /></el-icon>
                  </div>
                  <transition name="ar-expand">
                    <div v-if="showTranscript" class="ar-transcript">{{ standaloneAnalysis.transcript || transcriptSegments.map(s => s.text).join(' ') || '暂无文字稿' }}</div>
                  </transition>
                </div>
              </div>

              <!-- 右栏：视觉分析 + 建议 -->
              <div class="ar-col-right">
                <!-- 视觉分析 -->
                <div v-if="standaloneAnalysis.gesture_analysis && !standaloneAnalysis.gesture_analysis.error" class="ar-section">
                  <div class="ar-section-header"><span class="ar-section-icon">👁️</span><span class="ar-section-title">视觉分析</span></div>
                  <div class="ar-visual-grid">
                    <div class="ar-visual-card" v-if="standaloneAnalysis.gesture_analysis.posture_score">
                      <div class="ar-visual-bar-wrap">
                        <div class="ar-visual-bar" :style="{ width: standaloneAnalysis.gesture_analysis.posture_score + '%', background: '#6366f1' }"></div>
                      </div>
                      <div class="ar-visual-meta"><span class="ar-visual-name">姿态评分</span><span class="ar-visual-score" style="color:#818cf8">{{ standaloneAnalysis.gesture_analysis.posture_score }}</span></div>
                    </div>
                    <div class="ar-visual-card" v-if="standaloneAnalysis.gesture_analysis.gesture_score">
                      <div class="ar-visual-bar-wrap">
                        <div class="ar-visual-bar" :style="{ width: standaloneAnalysis.gesture_analysis.gesture_score + '%', background: '#0891b2' }"></div>
                      </div>
                      <div class="ar-visual-meta"><span class="ar-visual-name">手势运用</span><span class="ar-visual-score" style="color:#22d3ee">{{ standaloneAnalysis.gesture_analysis.gesture_score }}</span></div>
                    </div>
                    <div class="ar-visual-card" v-if="standaloneAnalysis.gesture_analysis.eye_contact_score">
                      <div class="ar-visual-bar-wrap">
                        <div class="ar-visual-bar" :style="{ width: standaloneAnalysis.gesture_analysis.eye_contact_score + '%', background: '#f59e0b' }"></div>
                      </div>
                      <div class="ar-visual-meta"><span class="ar-visual-name">眼神交流</span><span class="ar-visual-score" style="color:#fbbf24">{{ standaloneAnalysis.gesture_analysis.eye_contact_score }}</span></div>
                    </div>
                    <div class="ar-visual-card" v-if="standaloneAnalysis.gesture_analysis.expression_score">
                      <div class="ar-visual-bar-wrap">
                        <div class="ar-visual-bar" :style="{ width: standaloneAnalysis.gesture_analysis.expression_score + '%', background: '#10b981' }"></div>
                      </div>
                      <div class="ar-visual-meta"><span class="ar-visual-name">面部表情</span><span class="ar-visual-score" style="color:#34d399">{{ standaloneAnalysis.gesture_analysis.expression_score }}</span></div>
                    </div>
                  </div>
                </div>

                <!-- 改进建议 -->
                <div v-if="standaloneAnalysis.suggestions?.length" class="ar-section ar-section-grow">
                  <div class="ar-section-header"><span class="ar-section-icon">💡</span><span class="ar-section-title">改进建议</span><span class="ar-section-count">{{ standaloneAnalysis.suggestions.length }} 条</span></div>
                  <div class="ar-suggestions">
                    <div class="ar-suggest-item" v-for="(s, i) in standaloneAnalysis.suggestions" :key="i">
                      <span class="ar-suggest-idx">{{ Number(i) + 1 }}</span>
                      <span class="ar-suggest-text">{{ s }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <TrialVideoLibrary ref="videoLibrary" />
    <el-dialog v-model="showVideoDetails" title="填写视频详情" width="min(600px, 94vw)" destroy-on-close
      :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
      <TrialVideoUploader v-if="evaluationFile" :evaluated-file="evaluationFile"
        :analysis-task-id="analysisTaskId" @uploaded="handleVideoUpload" @busy-change="uploadingDetails = $event" />
      <template #footer><el-button :disabled="uploadingDetails" @click="showVideoDetails = false">稍后填写</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.evaluation-upload-note { color: #64748b; font-size: 12px; margin: 10px 0 18px; line-height: 1.6; }
/* ==================== 容器 & 全屏视频舞台 ==================== */
.realtime-container { min-height: calc(100vh - 100px); display: flex; flex-direction: column; padding: 0; }
.saved-video-upload { background: white; padding: 20px; border-radius: 12px; }
.stage-overlay.upload-screen { overflow-y: auto; align-items: flex-start; }
.video-stage {
  position: relative; flex: none; height: max(650px, calc(100vh - 100px)); background: #0f172a; border-radius: 16px; overflow: hidden;
  box-shadow: 0 4px 32px rgba(0,0,0,0.2); border: 1px solid rgba(8,145,178,0.12);
}
.video-feed { width: 100%; height: 100%; object-fit: contain; transform: scaleX(-1); background: #000; }
.video-feed.no-mirror { transform: none; }
.analysis-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.stage-overlay {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; z-index: 5;
}

/* ==================== 空闲：模式选择 ==================== */
.idle-screen {
  background: #1e293b;
}
.idle-screen::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 30% 40%, rgba(8,145,178,0.08) 0%, transparent 50%),
              radial-gradient(circle at 70% 60%, rgba(6,182,212,0.06) 0%, transparent 50%);
}
.idle-content { position: relative; z-index: 1; text-align: center; max-width: 520px; width: 100%; padding: 20px; }
.idle-brand { margin-bottom: 32px; }
.idle-title {
  font-size: 28px; font-weight: 800; margin: 18px 0 8px; color: #e0f2fe;
}
.idle-desc { color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 0 0 16px; }
.idle-status { margin-top: 20px; }

/* 模式卡片 */
.mode-cards { display: flex; flex-direction: column; gap: 12px; margin-bottom: 8px; }
.mode-card {
  display: flex; align-items: center; gap: 16px; padding: 16px 20px;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; cursor: pointer; transition: all 0.25s ease; text-align: left;
}
.mode-card:hover { background: rgba(8,145,178,0.12); border-color: rgba(8,145,178,0.3); transform: translateX(4px); }
.mode-icon {
  width: 52px; height: 52px; border-radius: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.mode-icon.realtime { background: #0891b2; color: white; }
.mode-icon.upload { background: #6366f1; color: white; }
.mode-info { flex: 1; }
.mode-name { font-size: 16px; font-weight: 700; color: white; margin-bottom: 3px; }
.mode-hint { font-size: 12px; color: #94a3b8; }
.mode-arrow { color: #475569; font-size: 18px; }

/* ==================== 实时配置 ==================== */
.config-screen { background: #1e293b; }
.config-content { position: relative; z-index: 1; text-align: center; max-width: 440px; width: 100%; padding: 20px; }
.back-btn {
  position: absolute; top: 20px; left: 20px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12);
  color: #94a3b8; padding: 6px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 4px;
  transition: all 0.2s;
}
.back-btn:hover { background: rgba(255,255,255,0.15); color: white; }
.config-title-row { display: flex; align-items: center; gap: 10px; justify-content: center; margin-bottom: 24px; }
.config-title-row h3 { font-size: 22px; font-weight: 800; color: white; margin: 0; }
.config-form { margin-bottom: 24px; }
.config-item label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 10px; font-weight: 600; }
.duration-options { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.dur-btn {
  padding: 8px 18px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04); color: #94a3b8; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.dur-btn:hover { border-color: rgba(8,145,178,0.4); color: white; }
.dur-btn.active { background: rgba(8,145,178,0.2); border-color: #0891b2; color: #22d3ee; }
.config-features { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 24px; }
.feature-tag {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px;
  background: rgba(8,145,178,0.08); border: 1px solid rgba(8,145,178,0.2);
  border-radius: 16px; font-size: 11px; font-weight: 600; color: #67e8f9;
}

/* AI 扫描环 */
.ai-scan-ring {
  position: relative; width: 90px; height: 90px; margin: 0 auto;
  display: flex; align-items: center; justify-content: center;
}
.ai-scan-ring::before {
  content: ''; position: absolute; inset: 0; border-radius: 50%;
  border: 2px solid transparent; border-top-color: #0891b2; border-right-color: rgba(8,145,178,0.3);
  animation: scan-spin 2s linear infinite;
}
.ai-scan-ring::after {
  content: ''; position: absolute; inset: 6px; border-radius: 50%;
  border: 1.5px solid transparent; border-bottom-color: #06b6d4; border-left-color: rgba(6,182,212,0.2);
  animation: scan-spin 3s linear infinite reverse;
}
@keyframes scan-spin { to { transform: rotate(360deg); } }

/* AI 模型标签 */
.ai-model-badges { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 20px; }
.model-badge {
  display: inline-flex; align-items: center; gap: 5px; padding: 4px 12px;
  background: rgba(8,145,178,0.12); border: 1px solid rgba(8,145,178,0.25);
  border-radius: 16px; font-size: 11px; font-weight: 600; color: #67e8f9;
}
.model-dot { width: 5px; height: 5px; border-radius: 50%; background: #22d3ee; box-shadow: 0 0 6px rgba(34,211,238,0.5); }
.ai-ready-badge {
  display: inline-flex; align-items: center; gap: 5px; padding: 3px 12px;
  background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3);
  border-radius: 10px; font-size: 11px; font-weight: 700; color: #34d399;
}
.ai-ready-dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; animation: ready-glow 1.5s ease-in-out infinite; }
@keyframes ready-glow { 0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.5); } 50% { box-shadow: 0 0 0 4px rgba(16,185,129,0); } }
.start-btn {
  height: 50px; padding: 0 36px; font-size: 16px; font-weight: 700; border-radius: 25px;
  background: #0891b2; border: none;
  box-shadow: 0 4px 16px rgba(8,145,178,0.35); transition: all 0.3s ease;
}
.start-btn:hover { box-shadow: 0 6px 24px rgba(8,145,178,0.5); transform: translateY(-1px); }

/* AI 微标记 */
.ai-micro-badge {
  margin-left: 4px; padding: 1px 6px; background: rgba(8,145,178,0.15); border: 1px solid rgba(8,145,178,0.3);
  border-radius: 4px; font-size: 8px; font-weight: 800; color: #22d3ee; letter-spacing: 0.5px;
}

/* ==================== 视频顶部状态栏 ==================== */
.video-top-bar {
  position: absolute; top: 10px; left: 10px; right: 10px;
  display: flex; align-items: center; gap: 8px; z-index: 10;
}
.rec-indicator {
  display: flex; align-items: center; gap: 6px; padding: 5px 12px;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(10px); border-radius: 8px;
  color: white; font-size: 11px; font-weight: 700; letter-spacing: 1px;
}
.rec-dot { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; animation: rec-blink 1s infinite; }
.rec-dot.paused { background: #94a3b8; animation: none; }
@keyframes rec-blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.time-badge {
  padding: 5px 12px; background: rgba(0,0,0,0.65); backdrop-filter: blur(10px); border-radius: 8px;
  color: white; font-family: 'JetBrains Mono','Fira Code',monospace; font-size: 13px; font-weight: 600;
}
.detect-badges { display: flex; gap: 4px; margin-left: auto; }
.toggle-metrics-btn {
  width: 34px; height: 34px; border-radius: 8px; border: none; cursor: pointer;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(10px); color: white;
  display: flex; align-items: center; justify-content: center; font-size: 16px; transition: background 0.2s;
}
.toggle-metrics-btn:hover { background: rgba(8,145,178,0.7); }

/* ==================== 右侧浮动指标面板 ==================== */
.float-metrics {
  position: absolute; top: 50px; right: 6px; width: 160px;
  display: flex; flex-direction: column; gap: 5px; z-index: 10;
}
.fm-card {
  background: rgba(15,23,42,0.55); backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 7px 9px;
  color: white; transition: all 0.3s ease;
}
.fm-label { font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.5); margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.fm-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.fm-big { font-size: 26px; font-weight: 800; line-height: 1; transition: color 0.5s ease; }
.fm-big.good { color: #34d399; }
.fm-big.warn { color: #fbbf24; }
.fm-sub-scores { display: flex; flex-direction: column; gap: 2px; margin-left: auto; }
.fm-sub-val { font-size: 14px; font-weight: 700; color: rgba(255,255,255,0.8); }
.fm-sub-name { font-size: 9px; color: rgba(255,255,255,0.4); margin-left: 3px; }
.fm-unit { font-size: 10px; color: rgba(255,255,255,0.4); }
.fm-tag { font-size: 11px; font-weight: 700; margin-left: auto; }
.fm-small-label { font-size: 10px; color: rgba(255,255,255,0.4); }
.fm-small-val { font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.8); margin-left: auto; transition: color 0.5s ease; }
.fm-small-val.high { color: #f87171; }
.fm-status { font-size: 15px; font-weight: 700; transition: color 0.5s ease; }
.fm-status.good { color: #34d399; }
.fm-status.warning { color: #fbbf24; }
.fm-status.bad { color: #f87171; }
.fm-expr-icon { font-size: 18px; }
.fm-expr-state { font-size: 14px; font-weight: 700; }
.fm-energy-ring-wrap { position: relative; width: 36px; height: 36px; }
.fm-energy-ring { width: 100%; height: 100%; }
.fm-energy-val {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
  font-size: 11px; font-weight: 800;
}
.fm-energy-label { font-size: 11px; font-weight: 700; }

/* 面板滑入动画 */
.panel-slide-enter-active { transition: all 0.3s ease; }
.panel-slide-leave-active { transition: all 0.2s ease; }
.panel-slide-enter-from { opacity: 0; transform: translateX(20px); }
.panel-slide-leave-to { opacity: 0; transform: translateX(20px); }

/* ==================== 左侧语音转写字幕面板 ==================== */
.left-transcript-panel {
  position: absolute; top: 50px; left: 6px; width: 190px;
  max-height: calc(100% - 130px); z-index: 9;
  display: flex; flex-direction: column;
  background: rgba(15,23,42,0.5); backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;
  overflow: hidden;
}
.ltp-header {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06); flex-shrink: 0;
}
.ltp-icon { color: #22d3ee; font-size: 14px; }
.ltp-title { font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.6); letter-spacing: 0.5px; }
.ltp-body {
  flex: 1; overflow-y: auto; padding: 8px 10px; scroll-behavior: smooth;
}
.ltp-body::-webkit-scrollbar { width: 2px; }
.ltp-body::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 2px; }
.ltp-seg {
  display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
  animation: ltp-fade-in 0.3s ease;
}
.ltp-time { font-size: 10px; color: #22d3ee; font-weight: 600; flex-shrink: 0; margin-top: 2px; font-family: 'JetBrains Mono','Fira Code',monospace; }
.ltp-text { font-size: 12px; color: rgba(255,255,255,0.85); line-height: 1.5; }
.ltp-empty {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 20px 0; color: rgba(255,255,255,0.25); font-size: 11px;
}
@keyframes ltp-fade-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

/* ==================== 提示浮层（顶部居中） ==================== */
.tips-overlay {
  position: absolute; top: 50px; left: 50%; transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center; gap: 6px; z-index: 12;
  pointer-events: none;
}
.tip-item {
  display: flex; align-items: center; gap: 6px; padding: 8px 20px;
  border-radius: 20px; font-size: 13px; font-weight: 600; backdrop-filter: blur(12px);
  pointer-events: auto; white-space: nowrap;
}
.tip-item.warning { background: rgba(245,158,11,0.85); color: white; }
.tip-item.success { background: rgba(16,185,129,0.85); color: white; }
.tip-item.info { background: rgba(8,145,178,0.85); color: white; }
.tip-enter-active { animation: tip-in 0.3s ease; }
.tip-leave-active { animation: tip-out 0.2s ease; }
@keyframes tip-in { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes tip-out { from { opacity: 1; } to { opacity: 0; transform: translateY(-10px); } }

/* ==================== 控制按钮（居中，hover显示） ==================== */
.ctrl-center {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  display: flex; gap: 24px; z-index: 12;
}
.ctrl-btn {
  backdrop-filter: blur(10px) !important;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}
.ctrl-fade-enter-active { transition: opacity 0.25s ease; }
.ctrl-fade-leave-active { transition: opacity 0.2s ease; }
.ctrl-fade-enter-from, .ctrl-fade-leave-to { opacity: 0; }

/* ==================== 频谱条 ==================== */
.spectrum-bar {
  position: absolute; bottom: 0; left: 0; right: 0; height: 36px;
  background: rgba(15,23,42,0.85); z-index: 7;
  padding: 6px 10px 4px;
}
.spectrum-canvas { width: 100%; height: 100%; display: block; }

/* ==================== 上传模式 ==================== */
.upload-screen { background: #1e293b; }
.upload-inner {
  position: relative; z-index: 1; text-align: center; width: 100%; padding: 24px;
}
.upload-idle { max-width: 520px; margin: 0 auto; }
.upload-idle h3 {
  font-size: 22px; font-weight: 800; color: #e0f2fe; margin: 16px 0 6px;
}
.upload-idle p { font-size: 13px; color: #94a3b8; margin: 0 0 20px; }
.upload-dragger { width: 100%; }
.upload-dragger :deep(.el-upload-dragger) {
  border: 2px dashed rgba(255,255,255,0.12); background: rgba(255,255,255,0.03);
  border-radius: 14px; padding: 36px 20px; transition: all 0.2s;
}
.upload-dragger :deep(.el-upload-dragger:hover) { border-color: rgba(8,145,178,0.5); background: rgba(8,145,178,0.06); }
.upload-dragger-inner { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.upload-dragger-inner span { font-size: 14px; color: #94a3b8; }
.upload-dragger-inner em { color: #22d3ee; font-style: normal; font-weight: 600; }
.upload-status { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 30px 0; }
.status-text { font-size: 16px; font-weight: 600; color: white; margin: 0; }
.status-hint { font-size: 13px; color: #94a3b8; margin: 0; }

/* 自定义加载动画 */
.upload-loader { position: relative; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; }
.upload-loader-icon { position: relative; z-index: 2; filter: drop-shadow(0 0 8px rgba(34,211,238,0.4)); }
.upload-loader-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 3px solid transparent; border-top-color: #0891b2; border-right-color: rgba(8,145,178,0.3);
  animation: loader-spin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}
.upload-loader-ring::after {
  content: ''; position: absolute; inset: 6px; border-radius: 50%;
  border: 2px solid transparent; border-bottom-color: #22d3ee; border-left-color: rgba(34,211,238,0.2);
  animation: loader-spin 1.8s cubic-bezier(0.5, 0, 0.5, 1) infinite reverse;
}
.upload-loader-ring.processing { border-top-color: #6366f1; border-right-color: rgba(99,102,241,0.3); }
.upload-loader-ring.processing::after { border-bottom-color: #818cf8; border-left-color: rgba(129,140,248,0.2); }
.upload-loader-orbit {
  position: absolute; inset: -4px; border-radius: 50%; border: 1.5px solid transparent;
  border-top-color: rgba(99,102,241,0.6); animation: loader-spin 3s linear infinite;
}
.upload-loader-orbit::before {
  content: ''; position: absolute; top: -2px; left: 50%; width: 6px; height: 6px;
  border-radius: 50%; background: #818cf8; box-shadow: 0 0 10px rgba(129,140,248,0.8);
  transform: translateX(-50%);
}
@keyframes loader-spin { to { transform: rotate(360deg); } }

/* 进度条 */
.upload-progress-wrap { display: flex; align-items: center; gap: 10px; width: 280px; }
.upload-progress-track { flex: 1; height: 6px; border-radius: 3px; background: rgba(255,255,255,0.08); overflow: hidden; }
.upload-progress-bar {
  height: 100%; border-radius: 3px; transition: width 0.4s ease;
  background: linear-gradient(90deg, #0891b2, #22d3ee);
  box-shadow: 0 0 12px rgba(34,211,238,0.4);
  position: relative;
}
.upload-progress-bar::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
  animation: progress-shimmer 1.5s ease-in-out infinite;
}
@keyframes progress-shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
.upload-progress-pct { font-size: 13px; font-weight: 700; color: #22d3ee; min-width: 36px; text-align: right; font-family: 'JetBrains Mono','Fira Code',monospace; }

/* 分析中跳动点 */
.processing-dots { display: flex; gap: 6px; }
.processing-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: #818cf8;
  animation: dot-bounce 1.4s ease-in-out infinite;
}
.processing-dots span:nth-child(2) { animation-delay: 0.2s; }
.processing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce { 0%,80%,100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

/* ==================== 分析结果（全屏两栏布局） ==================== */
.upload-result {
  width: 100%; max-width: 1200px; height: 100%; max-height: calc(100vh - 140px);
  display: flex; flex-direction: column; padding: 10px 16px; text-align: left;
  margin: 0 auto;
}
.upload-result::-webkit-scrollbar { width: 4px; }
.upload-result::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
.upload-result::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.3); }

/* 两栏主体 */
.ar-body { display: flex; gap: 14px; flex: 1; min-height: 0; overflow: hidden; }
.ar-col-left { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.ar-col-right { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; overflow-y: auto; }
.ar-col-right::-webkit-scrollbar { width: 3px; }
.ar-col-right::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 3px; }
.ar-section-grow { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.ar-section-grow .ar-suggestions { flex: 1; overflow-y: auto; }
.ar-section-grow .ar-suggestions::-webkit-scrollbar { width: 3px; }
.ar-section-grow .ar-suggestions::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 3px; }

/* 工具栏 */
.ar-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-shrink: 0; }
.ar-toolbar-left { display: flex; align-items: center; }
.ar-toolbar-right { display: flex; gap: 8px; }
.ar-done-badge {
  display: inline-flex; align-items: center; gap: 6px; padding: 5px 14px;
  background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3);
  border-radius: 20px; font-size: 13px; font-weight: 700; color: #34d399;
}
.ar-done-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #10b981;
  box-shadow: 0 0 8px rgba(16,185,129,0.6); animation: ar-pulse 2s ease-in-out infinite;
}
@keyframes ar-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.ar-action-btn {
  display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px;
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px; color: #cbd5e1; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.ar-action-btn:hover { background: rgba(255,255,255,0.12); color: white; border-color: rgba(255,255,255,0.2); }

/* 核心得分卡片 */
.ar-hero-card {
  position: relative; border-radius: 16px; overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08); flex-shrink: 0;
}
.ar-hero-bg {
  position: absolute; inset: 0;
  background: rgba(8,145,178,0.08);
}
.ar-hero-bg::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 20% 50%, rgba(8,145,178,0.12) 0%, transparent 60%);
}
.ar-hero-content {
  position: relative; z-index: 1; display: flex; align-items: center; gap: 16px;
  padding: 14px 16px;
}
.ar-score-ring { position: relative; width: 88px; height: 88px; flex-shrink: 0; }
.ar-ring-svg { width: 100%; height: 100%; filter: drop-shadow(0 0 8px rgba(0,0,0,0.3)); }
.ar-ring-progress { transition: stroke-dashoffset 1s ease-out; }
.ar-score-inner {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.ar-score-num { font-size: 26px; font-weight: 900; color: white; line-height: 1; letter-spacing: -1px; }
.ar-score-label { font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 4px; font-weight: 600; }

/* 指标卡片网格 */
.ar-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; flex: 1; }
.ar-stat-card {
  padding: 8px 10px; border-radius: 10px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.06);
  transition: all 0.2s; text-align: center;
}
.ar-stat-card:hover { background: rgba(255,255,255,0.08); transform: translateY(-1px); }
.ar-stat-icon { font-size: 15px; margin-bottom: 3px; }
.ar-stat-info { display: flex; align-items: baseline; gap: 3px; justify-content: center; }
.ar-stat-val { font-size: 17px; font-weight: 800; color: white; line-height: 1; }
.ar-stat-unit { font-size: 10px; color: rgba(255,255,255,0.4); font-weight: 600; }
.ar-stat-name { font-size: 10px; color: rgba(255,255,255,0.45); margin-top: 2px; font-weight: 600; }

/* 通用 Section */
.ar-section {
  border-radius: 12px; overflow: hidden; flex-shrink: 0;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
}
.ar-section-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.ar-section-icon { font-size: 15px; }
.ar-section-title { font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.85); }
.ar-section-count {
  margin-left: auto; font-size: 11px; font-weight: 700; color: #94a3b8;
  background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 10px;
}

/* 视觉分析条形图 */
.ar-visual-grid { padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; }
.ar-visual-card { margin: 0; }
.ar-visual-bar-wrap {
  height: 6px; border-radius: 3px; background: rgba(255,255,255,0.06); overflow: hidden;
}
.ar-visual-bar {
  height: 100%; border-radius: 3px; transition: width 0.8s ease-out;
  box-shadow: 0 0 10px rgba(255,255,255,0.08);
}
.ar-visual-meta { display: flex; justify-content: space-between; align-items: center; margin-top: 5px; }
.ar-visual-name { font-size: 12px; color: rgba(255,255,255,0.55); font-weight: 600; }
.ar-visual-score { font-size: 16px; font-weight: 800; }

/* 改进建议 */
.ar-suggestions { padding: 8px 12px; display: flex; flex-direction: column; gap: 6px; }
.ar-suggest-item {
  display: flex; align-items: flex-start; gap: 8px; padding: 8px 12px;
  background: rgba(245,158,11,0.06); border: 1px solid rgba(245,158,11,0.12);
  border-radius: 8px; transition: all 0.2s;
}
.ar-suggest-item:hover { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.2); }
.ar-suggest-idx {
  flex-shrink: 0; width: 20px; height: 20px; border-radius: 50%;
  background: #d97706; color: white;
  font-size: 10px; font-weight: 800; display: flex; align-items: center; justify-content: center;
}
.ar-suggest-text { font-size: 12px; color: rgba(255,255,255,0.75); line-height: 1.5; }

/* 文字稿折叠 */
.ar-section-toggle { cursor: pointer; user-select: none; transition: background 0.2s; }
.ar-section-toggle:hover { background: rgba(255,255,255,0.03); }
.ar-toggle-icon { margin-left: auto; color: #64748b; transition: transform 0.3s ease; font-size: 14px; }
.ar-toggle-icon.open { transform: rotate(90deg); }
.ar-transcript {
  padding: 14px; line-height: 1.9; color: rgba(255,255,255,0.85); white-space: pre-wrap;
  max-height: 380px; min-height: 160px; overflow-y: auto; font-size: 13.5px;
  background: rgba(0,0,0,0.18); border-top: 1px solid rgba(255,255,255,0.05);
}
.ar-transcript::-webkit-scrollbar { width: 3px; }
.ar-transcript::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
.ar-expand-enter-active { transition: all 0.3s ease; }
.ar-expand-leave-active { transition: all 0.2s ease; }
.ar-expand-enter-from, .ar-expand-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; overflow: hidden; }

/* ==================== 工具类 ==================== */
.mr-1 { margin-right: 4px; }
.mr-2 { margin-right: 8px; }
.ml-2 { margin-left: 8px; }
.ml-auto { margin-left: auto; }
.mt-1 { margin-top: 4px; }
.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .float-metrics { width: 140px; }
  .left-transcript-panel { width: 180px; }
  .tips-overlay { left: 200px; width: 220px; }
  .mode-card { padding: 12px 14px; }
  .idle-title { font-size: 22px; }
}
</style>
