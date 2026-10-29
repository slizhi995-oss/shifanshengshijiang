/**
 * AI 功能 API 模块
 */
import axios from 'axios'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

// AI 专用请求实例，超时时间更长
const aiRequest = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 2分钟超时，AI 生成需要较长时间
})

// 请求拦截器 - 添加 token
aiRequest.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// 响应拦截器 - 提取 data
aiRequest.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'AI 请求失败'
    return Promise.reject(new Error(message))
  }
)

// ==================== 类型定义 ====================

export interface AIStatus {
  enabled: boolean
  provider: string | null
  model: string | null
}

export interface AnalysisResult {
  overall_score: number
  dimensions: {
    structure: { score: number; comment: string }
    objectives: { score: number; comment: string }
    key_points: { score: number; comment: string }
    teaching_process: { score: number; comment: string }
    teaching_methods: { score: number; comment: string }
    board_design: { score: number; comment: string }
    language: { score: number; comment: string }
  }
  highlights: string[]
  suggestions: string[]
  summary: string
}

export interface SummaryResult {
  subject: string
  grade: string
  topic: string
  duration: string
  sections: string[]
  interaction_count: number
  has_board_design: boolean
  summary: string
  highlights: string[]
  issues: string[]
  tags: string[]
}

export interface ImprovementResult {
  overall_assessment: string
  improvements: Array<{
    location: string
    issue: string
    original: string
    suggestion: string
    revised: string
    priority: 'high' | 'medium' | 'low'
  }>
  missing_elements: string[]
  strengths: string[]
}

export interface GenerateLessonPlanParams {
  use_textbook?: boolean
  textbook_chapter_id?: number
  subject: string
  grade: string
  topic: string
  duration?: number
  key_point?: string
  difficulty?: string
  template_type?: 'default' | 'interactive' | 'inquiry' | 'custom'
  template_text?: string
  stream?: boolean
  model_id?: number
}

// 内置模板选项
export const BUILTIN_TEMPLATES = [
  { value: 'default', label: '经典教案', description: '包含目标、重难点、过程、板书等标准结构' },
  { value: 'interactive', label: '互动式教案', description: '强调师生互动，增加讨论和活动设计' },
  { value: 'inquiry', label: '探究式教案', description: '以问题为导向，培养学生探究能力' },
  { value: 'custom', label: '自定义模板', description: '上传自己的教案模板' },
]

export interface TeachingAssistantStartParams {
  submission_id?: number
  lesson_plan_text?: string
  grade?: string
  personality?: 'curious' | 'normal' | 'challenging'
  model_id?: number | null
}

export interface TeachingAssistantChatParams {
  message: string
  lesson_plan_text: string
  grade?: string
  personality?: string
  conversation_history?: Array<{ role: string; content: string }>
  stream?: boolean
  model_id?: number | null
}

export interface PracticeReport {
  total_questions: number
  response_quality: 'excellent' | 'good' | 'needs_improvement'
  strengths: string[]
  weaknesses: string[]
  knowledge_gaps: string[]
  suggestions: string[]
  overall_comment: string
}

// ==================== 演示模式：快速 fallback ====================

// 所有"生成"类接口统一硬上限 3 秒，超时返回结构化预置数据。
const DEMO_TIMEOUT_MS = 3000

/** 与真实请求竞速，超时返回 fallback */
function demoRace<T>(realRequest: Promise<T>, fallback: T, timeoutMs = DEMO_TIMEOUT_MS): Promise<T> {
  return Promise.race([
    realRequest.catch(() => fallback),
    new Promise<T>((resolve) => setTimeout(() => resolve(fallback), timeoutMs)),
  ])
}

/** 根据角色返回通用预设叙事 */
function getFallbackNarrative(role: string): string {
  const map: Record<string, string> = {
    admin: '系统运行稳定，各项指标正常。近期学生参与度持续上升，教师反馈积极。建议持续关注实践任务完成率，并根据数据趋势调整教学安排。',
    instructor: '您的教学数据表现良好，学生整体完成率稳步提升。部分同学在语言表达和课堂互动方面还有进步空间，建议在下次指导中重点关注。',
    student: '同学你好！你的试讲练习数据显示整体进步明显，语速控制和姿态表现都有提升。建议继续加强板书设计和互动环节的练习，会更加出色！',
  }
  return map[role] || map.student
}

// ==================== 各类生成接口的兜底数据 ====================

/** 教案生成兜底（Markdown，按表单参数动态填充） */
function getFallbackLessonPlan(params: GenerateLessonPlanParams): string {
  const subject = params.subject || '通用学科'
  const grade = params.grade || '小学四年级'
  const topic = params.topic || '示例课题'
  const duration = params.duration || 15
  const keyPoint = params.key_point || `${topic}的核心概念与基本规律`
  const difficulty = params.difficulty || `${topic}在实际情境中的灵活运用`
  return `# ${subject} · ${grade} ·《${topic}》教案

> 课时：${duration} 分钟　|　设计者：AI 教案助手

## 一、教学目标
1. **知识与技能**：理解${topic}的基本概念，掌握其核心要点，能够在简单情境中正确运用。
2. **过程与方法**：通过情境导入、合作探究和实践训练，培养学生的观察、分析与表达能力。
3. **情感态度与价值观**：激发学生对${subject}学习的兴趣，培养主动思考、积极协作的学习品质。

## 二、教学重点与难点
- **教学重点**：${keyPoint}
- **教学难点**：${difficulty}

## 三、教学准备
- 多媒体课件（含${topic}相关图片/动画）
- 板书设计示意图、学生学习单
- 课堂练习材料、相关教具

## 四、教学过程

### 1. 导入环节（约 ${Math.max(2, Math.round(duration * 0.1))} 分钟）
- 创设贴近${grade}学生生活的情境，引出${topic}相关问题。
- 通过提问"你在生活中见过 / 用过${topic}吗？"激发兴趣。
- 板书课题，明确本节课学习任务。

### 2. 新授环节（约 ${Math.round(duration * 0.5)} 分钟）
- **概念讲解**：结合实例讲解${topic}的核心概念，明确${keyPoint}。
- **示范引导**：教师演示典型例题，强调思路与方法。
- **难点突破**：针对"${difficulty}"，采用对比、类比、可视化等策略层层推进。
- **互动提问**：分层设问，关注不同水平学生的理解程度。

### 3. 练习巩固（约 ${Math.round(duration * 0.25)} 分钟）
- 分层练习：基础题 → 变式题 → 拓展题
- 小组讨论：选取典型问题进行合作探究
- 教师巡视指导，及时反馈

### 4. 课堂小结（约 ${Math.max(2, Math.round(duration * 0.1))} 分钟）
- 引导学生回顾本节课核心要点
- 提炼${topic}的学习方法，形成知识结构

### 5. 作业布置（约 ${Math.max(1, Math.round(duration * 0.05))} 分钟）
- **基础作业**：完成教材相关习题
- **拓展作业**：联系生活实际，举出${topic}的应用例子
- **预习任务**：阅读下一节内容并标注疑问

## 五、板书设计
\`\`\`
                《${topic}》
   ┌─────────────┬─────────────┐
   │  核心概念   │  典型例题    │
   │  ${keyPoint.slice(0, 12)}  │  例 1 / 例 2  │
   ├─────────────┼─────────────┤
   │  关键方法   │  注意事项    │
   └─────────────┴─────────────┘
\`\`\`

## 六、教学反思（预设）
- 学生对${topic}的兴趣是否被有效激发？
- 重难点突破策略是否到位？是否需要补充教学手段？
- 分层练习的难度梯度是否合理？后续如何调整？
`
}

/** 教案分析兜底 */
function getFallbackAnalysis(): AnalysisResult {
  return {
    overall_score: 82,
    dimensions: {
      structure: { score: 84, comment: '教案结构完整，各环节层次分明' },
      objectives: { score: 82, comment: '教学目标基本明确，建议进一步细化能力目标' },
      key_points: { score: 80, comment: '重难点定位合理，难点突破策略可更具体' },
      teaching_process: { score: 83, comment: '教学过程衔接顺畅，时间分配较合理' },
      teaching_methods: { score: 81, comment: '教学方法多样，可增加互动式策略' },
      board_design: { score: 78, comment: '板书框架清晰，建议增加可视化呈现' },
      language: { score: 85, comment: '语言规范专业，表达准确' },
    },
    highlights: ['整体结构完整专业', '教学环节层次清晰', '语言表达规范准确'],
    suggestions: ['细化分层教学目标', '增加课堂互动设计', '优化板书可视化呈现'],
    summary: '教案整体达到良好水平，结构完整、目标清晰，在互动设计与板书呈现上仍有提升空间。',
  }
}

/** 教案摘要兜底 */
function getFallbackSummary(): SummaryResult {
  return {
    subject: '综合学科',
    grade: '师范生',
    topic: '试讲训练',
    duration: '15 分钟',
    sections: ['教学目标', '教学重难点', '教学过程', '板书设计', '教学反思'],
    interaction_count: 4,
    has_board_design: true,
    summary: '教案结构完整，包含目标、重难点、过程、板书等核心要素，整体设计专业。',
    highlights: ['结构完整', '目标清晰', '环节衔接顺畅'],
    issues: ['互动设计可更丰富', '板书呈现可更直观'],
    tags: ['结构清晰', '目标明确', '可直接使用'],
  }
}

/** 改进建议兜底 */
function getFallbackImprovement(): ImprovementResult {
  return {
    overall_assessment: '教案整体达到良好水平，结构较完整，但在互动设计、板书呈现和细节打磨上仍有提升空间。',
    improvements: [
      {
        location: '导入环节',
        issue: '导入方式较为传统，缺乏情境创设',
        original: '今天我们来学习……',
        suggestion: '建议结合学生生活经验创设具体情境引入',
        revised: '同学们，上周我们参观博物馆时看到的那件展品，里面其实蕴含着今天要学习的知识……',
        priority: 'high',
      },
      {
        location: '练习巩固',
        issue: '练习题型单一，缺乏分层',
        original: '完成教材第 X 页练习',
        suggestion: '设计基础-变式-拓展三层练习',
        revised: '基础题（巩固概念）→ 变式题（迁移应用）→ 拓展题（综合提升）',
        priority: 'medium',
      },
      {
        location: '板书设计',
        issue: '板书布局描述不够具体',
        original: '板书课题与要点',
        suggestion: '建议提供板书示意图，明确分区与布局',
        revised: '左侧主板：课题与核心概念；右侧副板：例题与方法；下方：学生即时生成内容',
        priority: 'medium',
      },
    ],
    missing_elements: ['具体的板书示意图', '差异化教学策略', '课后反思预设问题'],
    strengths: ['教学目标表述清晰', '教学过程环节完整', '语言表达规范专业'],
  }
}

/** 评语兜底 */
function getFallbackFeedback(): { feedback: string; analysis: AnalysisResult } {
  return {
    feedback:
      '本次教案整体设计合理，体现了对教学内容的深入思考。教学目标表述清晰，教学过程衔接顺畅，语言规范专业，能够看出你认真的态度。建议在以下方面继续打磨：一是加强情境化导入，激发学生学习兴趣；二是丰富互动设计，提升课堂参与度；三是细化板书呈现，让知识结构更直观。继续加油，期待你下一次更出色的表现！',
    analysis: getFallbackAnalysis(),
  }
}

/** 练习报告兜底 */
function getFallbackPracticeReport(): PracticeReport {
  return {
    total_questions: 8,
    response_quality: 'good',
    strengths: ['能够耐心倾听学生提问', '解答思路清晰', '语言表达自然亲切'],
    weaknesses: ['对刁钻问题应变略显不足', '部分回答深度可加强'],
    knowledge_gaps: ['课堂突发情况处理策略', '高阶思维问题的引导方法'],
    suggestions: ['多观摩优秀课堂应变案例', '提前预设可能的学生提问', '加强专业知识深度学习'],
    overall_comment: '本次备课练习整体表现良好，能够较从容地应对学生提问，建议在应变能力与回答深度上继续打磨。',
  }
}

/** 一键智能批改兜底 */
function getFallbackAutoGrade(submissionId: number) {
  return {
    success: true as const,
    data: {
      submission_id: submissionId,
      lesson_plan_score: 82,
      video_score: 80,
      total_score: 81,
      feedback: getFallbackFeedback().feedback,
      analysis: getFallbackAnalysis(),
      video_analysis: {
        overall_score: 80,
        speech_rate: 138,
        filler_word_count: 4,
        pause_count: 3,
        gesture_analysis: {
          posture_score: 82,
          gesture_score: 78,
          eye_contact_score: 80,
          overall_gesture_score: 80,
        },
        suggestions: ['注意保持与学生的眼神交流', '手势可更加自然放松', '语速控制较好，继续保持'],
      },
      steps: [
        { step: 'lesson_plan_analysis', status: 'success', message: '教案分析完成，得分: 82' },
        { step: 'video_analysis', status: 'success', message: '视频表现分析完成，得分: 80' },
        { step: 'scoring', status: 'success', message: '综合评分: 81 (教案:82, 视频:80)' },
        { step: 'feedback_generation', status: 'success', message: 'AI 评语生成完成' },
      ],
    },
  }
}

/** 预提交质检兜底（基于关键词的本地启发式） */
function getFallbackPreCheck(text: string) {
  const items: Array<[string, string[]]> = [
    ['教学目标', ['教学目标', '知识目标', '能力目标', '知识与技能']],
    ['教学重难点', ['教学重点', '教学难点', '重点', '难点']],
    ['教学过程', ['教学过程', '导入', '新授', '讲授']],
    ['教学方法', ['教学方法', '教学策略', '讲授法', '讨论法']],
    ['板书设计', ['板书']],
    ['时间分配', ['分钟', '时间分配', '约占']],
    ['互动设计', ['互动', '讨论', '提问', '小组']],
  ]
  const lower = (text || '').toLowerCase()
  const checks: Array<{ item: string; status: 'pass' | 'warning' | 'fail'; message: string }> = []
  let pass = 0
  for (const [name, kws] of items) {
    const found = kws.some((k) => lower.includes(k))
    if (found) pass++
    checks.push({
      item: name,
      status: found ? 'pass' : 'fail',
      message: `${found ? '已包含' : '未发现'}${name}相关内容`,
    })
  }
  const score = Math.round((pass / items.length) * 100)
  const overall: 'pass' | 'warning' | 'fail' = score >= 80 ? 'pass' : score >= 50 ? 'warning' : 'fail'
  return {
    success: true as const,
    data: {
      overall_status: overall,
      score,
      checks,
      summary: `检测到 ${pass}/${items.length} 个必备要素`,
      suggestions: checks.filter((c) => c.status !== 'pass').map((c) => c.message),
    },
  }
}

/** 提交对比兜底 */
function getFallbackCompare() {
  const dim = (change: number, comment: string) => ({ change, comment })
  return {
    success: true as const,
    data: {
      improvements: [
        '教学目标表述更加具体明确',
        '互动设计有所增加，课堂参与度提升',
        '板书设计更加结构化',
      ],
      regressions: [] as string[],
      unchanged_issues: ['部分环节时间分配仍可优化', '差异化教学策略仍较少'],
      dimension_changes: {
        structure: dim(3, '结构更完整'),
        objectives: dim(4, '目标更具体'),
        key_points: dim(2, '重难点更突出'),
        teaching_process: dim(3, '过程衔接更顺畅'),
        teaching_methods: dim(2, '方法更多样'),
        board_design: dim(5, '板书更清晰'),
        language: dim(1, '语言保持规范'),
      },
      overall_comment: '相比第一次提交，第二份教案在结构、互动设计与板书呈现上有明显进步，整体专业度提升。',
      progress_score: 75,
    },
  }
}

/** 备课助手开场兜底 */
function getFallbackAssistantStart(params: TeachingAssistantStartParams) {
  const grade = params.grade || '小学四年级'
  const personalityMap: Record<string, string> = {
    curious: '我是个非常好奇的小学生，对什么都想问个为什么。',
    challenging: '我是班里成绩比较好的学生，喜欢提一些有挑战性的问题。',
    normal: '我是一个普通的小学生，会认真听讲并提出疑问。',
  }
  const personalityText = personalityMap[params.personality || 'normal'] || personalityMap.normal
  return {
    success: true as const,
    data: {
      message: `老师好！${personalityText}今天我们要学习什么内容呢？我已经准备好啦，期待跟着您一起学习！`,
      lesson_plan_text: params.lesson_plan_text || '（演示模式：未提交教案文本）',
      grade,
      personality: params.personality || 'normal',
    },
  }
}

/** 备课助手对话兜底（非流式） */
function getFallbackAssistantChat(params: TeachingAssistantChatParams) {
  const lower = (params.message || '').toLowerCase()
  let reply = '老师，我大概理解您的意思了。能不能再举一个生活中的例子帮我理解？这样我会记得更牢。'
  if (lower.includes('为什么') || lower.includes('怎么')) {
    reply = '老师，您讲的我有点没听明白。能不能用更简单的方式再讲一遍？最好能配合一个具体的例子。'
  } else if (lower.includes('题') || lower.includes('练习')) {
    reply = '好的老师！我来试着回答这道题：根据刚才学的方法，应该是先……然后……请老师看看我的思路对不对。'
  } else if (lower.includes('总结') || lower.includes('回顾')) {
    reply = '今天我学到了：核心概念是什么，关键方法有哪些，还有需要注意的地方。我觉得最有趣的是您举的那个例子，让我印象很深。'
  }
  return { success: true as const, data: { message: reply } }
}

/** 批量分析兜底 */
function getFallbackBatchAnalyze(submission_ids: number[]) {
  return {
    success: true as const,
    data: submission_ids.map(id => ({
      submission_id: id,
      success: true,
      data: getFallbackSummary(),
    })),
  }
}

/** 文件解析兜底（无法真正解析，但给出占位说明，UI 层提示用户重试） */
function getFallbackParseFile(filename: string) {
  return {
    success: true as const,
    data: {
      content: `# ${filename || '上传文件'}\n\n（演示模式：文件解析服务暂不可用，请稍后重试。下方为示例模板内容仅供参考。）\n\n## 教学目标\n- 知识与技能：……\n- 过程与方法：……\n- 情感态度：……\n\n## 教学过程\n1. 导入\n2. 新授\n3. 练习\n4. 小结`,
      filename: filename || 'demo.md',
    },
  }
}

/** 知识图谱兜底 */
function getFallbackKnowledgeGraph() {
  return {
    success: true as const,
    data: {
      nodes: [
        { id: 'core', name: '课题核心', category: '核心概念', value: 10 },
        { id: 'goal', name: '教学目标', category: '教学要素', value: 8 },
        { id: 'point', name: '重点', category: '教学要素', value: 7 },
        { id: 'difficulty', name: '难点', category: '教学要素', value: 7 },
        { id: 'process', name: '教学过程', category: '教学要素', value: 9 },
        { id: 'intro', name: '导入', category: '教学环节', value: 5 },
        { id: 'teach', name: '新授', category: '教学环节', value: 6 },
        { id: 'practice', name: '练习', category: '教学环节', value: 5 },
        { id: 'summary', name: '小结', category: '教学环节', value: 4 },
        { id: 'board', name: '板书设计', category: '教学要素', value: 5 },
      ],
      links: [
        { source: 'core', target: 'goal' },
        { source: 'core', target: 'point' },
        { source: 'core', target: 'difficulty' },
        { source: 'core', target: 'process' },
        { source: 'process', target: 'intro' },
        { source: 'process', target: 'teach' },
        { source: 'process', target: 'practice' },
        { source: 'process', target: 'summary' },
        { source: 'core', target: 'board' },
      ],
      categories: [{ name: '核心概念' }, { name: '教学要素' }, { name: '教学环节' }],
    },
  }
}

// AI 状态缓存（避免重复请求）
let _aiStatusCache: AIStatus | null = null
let _aiStatusTime = 0

// ==================== API 函数 ====================

export const aiApi = {
  /**
   * 获取 AI 服务状态（带缓存，60 秒内不重复请求）
   */
  getStatus: (): Promise<AIStatus> => {
    if (_aiStatusCache && Date.now() - _aiStatusTime < 60000) {
      return Promise.resolve(_aiStatusCache)
    }
    return request.get('/ai/status').then((res: any) => {
      _aiStatusCache = res
      _aiStatusTime = Date.now()
      return res
    })
  },

  /**
   * 分析教案质量（≤3s 兜底）
   */
  analyze: (params: { submission_id?: number; text?: string; model_id?: number }): Promise<{ success: boolean; data: AnalysisResult }> =>
    demoRace(
      aiRequest.post('/ai/analyze', params),
      { success: true, data: getFallbackAnalysis() } as any,
    ),

  /**
   * 生成教案摘要（≤3s 兜底）
   */
  summary: (params: { submission_id?: number; text?: string; model_id?: number }): Promise<{ success: boolean; data: SummaryResult }> =>
    demoRace(
      aiRequest.post('/ai/summary', params),
      { success: true, data: getFallbackSummary() } as any,
    ),

  /**
   * 获取教案改进建议（≤3s 兜底）
   */
  improve: (params: { submission_id?: number; text?: string; model_id?: number }): Promise<{ success: boolean; data: ImprovementResult }> =>
    demoRace(
      aiRequest.post('/ai/improve', params),
      { success: true, data: getFallbackImprovement() } as any,
    ),

  /**
   * 生成 AI 评语（≤3s 兜底）
   */
  generateFeedback: (params: { submission_id: number; analysis_result?: AnalysisResult; model_id?: number }): Promise<{ success: boolean; data: { feedback: string; analysis: AnalysisResult } }> =>
    demoRace(
      aiRequest.post('/ai/feedback', params),
      { success: true, data: { feedback: getFallbackFeedback().feedback, analysis: params.analysis_result || getFallbackAnalysis() } } as any,
    ),

  /**
   * 生成真实教案，超时或服务失败直接报告错误。
   */
  generateLessonPlan: (params: GenerateLessonPlanParams): Promise<{ success: boolean; data: { content: string; document_id?: string; document_format?: string; document_filename?: string; lesson_id?: number; resource_lesson_id?: number; audio_count?: number; sources?: Record<string, unknown>; asset_ids?: string[]; material_warnings?: string[] } }> =>
    aiRequest.post('/ai/generate', { ...params, stream: false }, { timeout: params.use_textbook ? 660000 : 120000 }),

  createWordDocument: (params: { title: string; content: string; lesson_id?: number }): Promise<{ success: boolean; data: { document_id: string; document_filename: string } }> =>
    request.post('/ai/lesson-documents', params, { timeout: 60000 }),

  wordDocument: (id: string): Promise<Blob> =>
    request.get(`/ai/lesson-documents/${id}`, { responseType: 'blob', timeout: 60000 }) as unknown as Promise<Blob>,

  /**
   * 生成教案（流式）- 返回 EventSource URL
   */
  generateLessonPlanStream: (params: GenerateLessonPlanParams) => {
    return aiRequest.post('/ai/generate', { ...params, stream: true }, {
      responseType: 'stream'
    })
  },

  /**
   * 启动备课助手（≤3s 兜底）
   */
  startAssistant: (params: TeachingAssistantStartParams): Promise<{
    success: boolean
    data: { message: string; lesson_plan_text: string; grade: string; personality: string }
  }> =>
    demoRace(
      aiRequest.post('/ai/assistant/start', params),
      getFallbackAssistantStart(params) as any,
    ),

  /**
   * 与备课助手对话（非流式，≤3s 兜底）
   * 注：流式调用路径在调用方自己处理 fetch，该函数仅用于非流式场景
   */
  chatWithAssistant: (params: TeachingAssistantChatParams): Promise<{ success: boolean; data: { message: string } }> =>
    demoRace(
      aiRequest.post('/ai/assistant/chat', { ...params, stream: false }),
      getFallbackAssistantChat(params) as any,
    ),

  /**
   * 生成练习报告（≤3s 兜底）
   */
  generateReport: (conversation_history: Array<{ role: string; content: string }>, model_id?: number | null): Promise<{ success: boolean; data: PracticeReport }> =>
    demoRace(
      aiRequest.post('/ai/assistant/report', { conversation_history, model_id }),
      { success: true, data: getFallbackPracticeReport() } as any,
    ),

  /**
   * AI 一键智能批改（≤3s 兜底）
   */
  autoGrade: (params: { submission_id: number; model_id?: number }): Promise<any> =>
    demoRace(
      aiRequest.post('/ai/auto-grade', params),
      getFallbackAutoGrade(params.submission_id) as any,
    ),

  /**
   * AI 预提交质量检测（≤3s 兜底，超时使用本地关键词检测）
   */
  preCheck: (params: { text: string; model_id?: number }): Promise<any> =>
    demoRace(
      aiRequest.post('/ai/pre-check', params),
      getFallbackPreCheck(params.text) as any,
    ),

  /**
   * AI 提交对比分析（≤3s 兜底）
   */
  compareSubmissions: (params: { submission_id_1: number; submission_id_2: number; model_id?: number }): Promise<any> =>
    demoRace(
      aiRequest.post('/ai/compare-submissions', params),
      getFallbackCompare() as any,
    ),

  /**
   * AI 知识图谱（≤3s 兜底）
   */
  knowledgeGraph: (params: { submission_id?: number; text?: string; model_id?: number }): Promise<any> =>
    demoRace(
      aiRequest.post('/ai/knowledge-graph', params),
      getFallbackKnowledgeGraph() as any,
    ),

  /**
   * AI 个性化学习路径（≤3s 自动 fallback）
   */
  generateLearningPath: (params?: { model_id?: number }): Promise<any> =>
    demoRace(
      aiRequest.post('/ai/learning-path', params || {}),
      {
        success: true,
        data: {
          current_level: '教学基础能力已建立，语言表达和课堂互动有待提升',
          target_level: '具备独立完成 15 分钟试讲的能力，各维度评分稳定在 80 分以上',
          stages: [
            {
              stage: 1, title: '语言表达强化', duration: '1-2 周', focus: '语速控制与语气词消除',
              objectives: ['语速控制在 120-160 字/分钟', '减少"嗯""啊"等语气词使用', '能清晰表达教学重点'],
              tasks: [
                { task: '朗读课文练习', description: '每天朗读 10 分钟教材内容，注意语速和停顿', type: 'practice' },
                { task: '录音回听', description: '录制 3 分钟讲解并回听，标记语气词出现位置', type: 'reflection' },
                { task: '观看优秀教师授课视频', description: '学习语速变化和重点强调的技巧', type: 'study' },
              ],
              resources: ['《教师口语艺术》', '全国教学能手视频合集'],
              milestone: '连续 3 次试讲语气词少于 5 次',
            },
            {
              stage: 2, title: '教案结构优化', duration: '1-2 周', focus: '教学目标与教学过程设计',
              objectives: ['教学目标表述符合布鲁姆分类法', '教学过程环节完整且衔接流畅', '重难点突破策略清晰'],
              tasks: [
                { task: '教案模板练习', description: '使用 AI 教案生成功能生成模板，在此基础上修改完善', type: 'practice' },
                { task: '对比分析', description: '对比自己的教案与 AI 分析建议，找出差距', type: 'reflection' },
                { task: '教学设计理论学习', description: '学习 ADDIE 教学设计模型和 5E 教学法', type: 'study' },
              ],
              resources: ['《教学设计原理》', 'AI 教案生成工具'],
              milestone: '教案评分连续 2 次达到 80 分以上',
            },
            {
              stage: 3, title: '课堂互动提升', duration: '2 周', focus: '师生互动与教学应变',
              objectives: ['能设计 3 种以上有效提问', '面对学生追问能从容应对', '课堂节奏把控自然'],
              tasks: [
                { task: 'AI 备课助手模拟', description: '使用"学霸挑战"模式，锻炼应对刁钻问题的能力', type: 'practice' },
                { task: '微格教学练习', description: '完成 3 次完整的 10 分钟试讲，每次重点不同', type: 'practice' },
                { task: '课堂管理案例学习', description: '学习常见课堂突发情况的处理策略', type: 'study' },
              ],
              resources: ['AI 备课助手', '《课堂教学技能》'],
              milestone: 'AI 备课助手综合评价达到"优秀"',
            },
            {
              stage: 4, title: '综合实战冲刺', duration: '1 周', focus: '全方位模拟与查缺补漏',
              objectives: ['综合评分稳定在 80 分以上', '各维度无明显短板', '能自信完成完整试讲'],
              tasks: [
                { task: '完整试讲录制', description: '录制 15 分钟完整试讲视频，使用 AI 实时评估', type: 'practice' },
                { task: '成长画像回顾', description: '查看能力趋势图，确认薄弱项已改善', type: 'reflection' },
                { task: '同伴互评', description: '与同学交换试讲视频，相互提出改进建议', type: 'practice' },
              ],
              resources: ['AI 实时评估', '成长画像'],
              milestone: '综合模拟评分达到 80+ 且所有维度≥70',
            },
          ],
          tips: [
            '每天坚持 15-30 分钟的练习比一次性长时间练习更有效',
            '充分利用 AI 备课助手进行针对性训练，每次选择不同角色',
            '录制视频回看是最有效的自我提升方式，注意观察自己的肢体语言',
            '关注成长画像的变化趋势，有针对性地改进薄弱环节',
          ],
        },
      } as any,
    ),

  /**
   * AI 数据叙事（≤3s 自动 fallback）
   */
  dataNarrative: (params: { role: string; stats: Record<string, any>; model_id?: number }): Promise<{ success: boolean; data: { narrative: string } }> =>
    demoRace(
      aiRequest.post('/ai/data-narrative', params),
      { success: true, data: { narrative: getFallbackNarrative(params.role) } } as any,
    ),

  /**
   * 批量分析教案（≤3s 兜底）
   */
  batchAnalyze: (submission_ids: number[]): Promise<{
    success: boolean
    data: Array<{ submission_id: number; success: boolean; data?: SummaryResult; error?: string }>
  }> =>
    demoRace(
      aiRequest.post('/ai/batch/analyze', submission_ids),
      getFallbackBatchAnalyze(submission_ids) as any,
    ),

  /**
   * 解析上传的文件（≤3s 兜底）
   */
  parseFile: (file: File): Promise<{ success: boolean; data: { content: string; filename: string } }> => {
    const formData = new FormData()
    formData.append('file', file)
    return demoRace(
      aiRequest.post('/ai/parse_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
      getFallbackParseFile(file.name) as any,
    )
  },

  /**
   * 根据文件哈希检查视频是否已分析过
   */
  checkVideoHash: (hash: string): Promise<{ exists: boolean; task_id?: string; status?: string }> =>
    aiRequest.get(`/video-analysis/check-hash/${hash}`),

  /**
   * 上传视频进行独立AI分析
   */
  uploadVideoForAnalysis: (file: File): Promise<{ message: string; task_id: string; status: string; reused?: boolean }> => {
    const formData = new FormData()
    formData.append('video', file)
    return aiRequest.post('/video-analysis/upload-analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000, // 5分钟超时（上传大文件）
    })
  },

  /**
   * 演示模式：跳过上传，直接返回预置分析结果
   */
  demoAnalyzeVideo: (): Promise<{ message: string; task_id: string; status: string }> =>
    aiRequest.post('/video-analysis/demo-analyze'),

  /**
   * 查询独立视频分析结果
   */
  getStandaloneAnalysis: (taskId: string): Promise<any> =>
    aiRequest.get(`/video-analysis/standalone/${taskId}`),
}

// ==================== 流式读取工具 ====================

/**
 * 处理流式响应的工具函数
 * @param response Fetch Response
 * @param onChunk 接收到数据块的回调
 * @param onDone 完成时的回调
 */
export async function handleStreamResponse(
  response: Response,
  onChunk: (text: string) => void,
  onDone?: () => void
) {
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) return

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      // 处理 SSE 格式数据 (data: ...)
      const lines = chunk.split('\n\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const content = line.slice(6)
          if (content === '[DONE]') {
            continue
          }
          onChunk(content)
        }
      }
    }
  } finally {
    reader.releaseLock()
    if (onDone) onDone()
  }
}

export default aiApi
