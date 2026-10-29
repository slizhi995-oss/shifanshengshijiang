import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/api/ai'
import type { AudioLessonDetail } from '@/api/resourceCenter'
import { schoolStage, subjectOptions, stagesForSubject } from '@/constants/textbooks'

// 类型定义
export interface GenerationRecord {
  id: string
  title: string
  createdAt: number
  form: {
    subject: string
    grade: string
    topic: string
    duration: number
    key_point: string
    difficulty: string
  }
  templateType: string
  content: string
  lessonId?: number
  resourceLessonId?: number
  documentId?: string
  sources?: Record<string, unknown>
  // The source selection belongs to the saved result, not the next form edit.
  textbookChapterId?: number
}

export interface GenerationForm {
  subject: string
  grade: string
  topic: string
  duration: number
  key_point: string
  difficulty: string
  modelId?: number | null
  use_textbook?: boolean
  textbook_id?: number
  textbook_chapter_id?: number
}

const STORAGE_KEY = 'ai_generator_history'
const STATE_KEY = 'ai_generator_state'

export const useAIGeneratorStore = defineStore('aiGenerator', () => {
  // 状态
  const generating = ref(false)
  const generatedContent = ref('')
  const records = ref<GenerationRecord[]>([])
  const currentRecordId = ref<string | null>(null)
  const selectedTemplate = ref('default')
  const customTemplateText = ref('')
  const customTemplateFile = ref('')

  // 表单数据
  const form = ref<GenerationForm>({
    subject: '',
    grade: '',
    topic: '',
    duration: 15,
    key_point: '',
    difficulty: '',
    modelId: null,
    use_textbook: true,
  })

  // 当前生成任务的信息（用于显示）
  watch(() => [form.value.subject, form.value.grade], () => {
    const allowed = stagesForSubject(form.value.subject)
    const stage = schoolStage(form.value.grade)
    if ((stage && !allowed.includes(stage)) || (!stage && allowed.length === 1)) {
      form.value.grade = allowed.length === 1 ? allowed[0] : ''
      form.value.textbook_id = undefined
      form.value.textbook_chapter_id = undefined
    }
  })

  const currentGenerationInfo = ref<{
    subject: string
    grade: string
    topic: string
    useTextbook: boolean
  } | null>(null)

  // 计算属性
  const generationHint = computed(() => {
    const missing = []
    if (!form.value.subject.trim()) missing.push('选择科目')
    if (!form.value.grade.trim()) missing.push('选择学段')
    if (!form.value.topic.trim()) missing.push('填写课题名称')
    if (form.value.use_textbook && !form.value.textbook_chapter_id) missing.push('选择章节')
    if (selectedTemplate.value === 'custom' && !customTemplateText.value.trim()) missing.push('上传自定义模板')
    return missing.length ? `请先${missing.join('、')}` : ''
  })

  const canGenerate = computed(() => !generationHint.value)

  const sortedRecords = computed(() => {
    return [...records.value].sort((a, b) => b.createdAt - a.createdAt)
  })

  const currentRecord = computed(() => {
    return records.value.find(r => r.id === currentRecordId.value)
  })

  // ==================== 本地存储 ====================

  function loadRecords() {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      if (data) {
        records.value = JSON.parse(data)
      }
    } catch (e) {
      console.error('Failed to load records:', e)
    }
  }

  function saveRecords() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records.value))
    } catch (e) {
      console.error('Failed to save records:', e)
    }
  }

  function loadState() {
    try {
      const data = localStorage.getItem(STATE_KEY)
      if (data) {
        const state = JSON.parse(data)
        form.value = state.form || form.value
        form.value.grade = schoolStage(form.value.grade)
        if (!subjectOptions.includes(form.value.subject)) {
          form.value.subject = ''; form.value.textbook_id = undefined; form.value.textbook_chapter_id = undefined
        }
        selectedTemplate.value = state.templateType || 'default'
        generatedContent.value = state.content || ''
        currentRecordId.value = state.currentRecordId || null
        customTemplateText.value = state.customTemplateText || ''
        customTemplateFile.value = state.customTemplateFile || ''
        // 注意：不恢复 generating 状态，因为页面刷新会中断 API 请求
        // 但如果是路由切换，generating 状态会保持在内存中
      }
    } catch (e) {
      console.error('Failed to load state:', e)
    }
  }

  function saveState() {
    try {
      const state = {
        form: form.value,
        templateType: selectedTemplate.value,
        content: generatedContent.value,
        currentRecordId: currentRecordId.value,
        customTemplateText: customTemplateText.value,
        customTemplateFile: customTemplateFile.value,
      }
      localStorage.setItem(STATE_KEY, JSON.stringify(state))
    } catch (e) {
      console.error('Failed to save state:', e)
    }
  }

  // ==================== 生成方法 ====================

  async function generateLessonPlan() {
    if (!canGenerate.value) {
      ElMessage.warning(generationHint.value)
      return false
    }

    if (selectedTemplate.value === 'custom' && !customTemplateText.value) {
      ElMessage.warning('请先上传自定义模板')
      return false
    }

    // 保存当前生成信息用于显示
    currentGenerationInfo.value = {
      subject: form.value.subject,
      grade: form.value.grade,
      topic: form.value.topic,
      useTextbook: !!form.value.use_textbook,
    }

    generating.value = true
    generatedContent.value = ''
    const submittedForm = { ...form.value }
    const submittedTemplate = selectedTemplate.value

    try {
      const res = await aiApi.generateLessonPlan({
        subject: submittedForm.subject,
        grade: submittedForm.grade,
        topic: submittedForm.topic,
        duration: submittedForm.duration,
        key_point: submittedForm.key_point,
        difficulty: submittedForm.difficulty,
        template_type: submittedTemplate as any,
        template_text: submittedTemplate === 'custom' ? customTemplateText.value : '',
        model_id: submittedForm.modelId || undefined,
        use_textbook: !!submittedForm.use_textbook,
        textbook_chapter_id: submittedForm.use_textbook ? submittedForm.textbook_chapter_id : undefined,
      })

      if (res.success) {
        generatedContent.value = res.data.content

        // 保存到历史记录
        const newRecord: GenerationRecord = {
          id: Date.now().toString(),
          title: `${submittedForm.subject} - ${submittedForm.topic}`,
          createdAt: Date.now(),
          form: submittedForm,
          templateType: submittedTemplate,
          content: res.data.content,
          lessonId: res.data.lesson_id,
          resourceLessonId: res.data.resource_lesson_id,
          documentId: res.data.document_id,
          sources: res.data.sources,
          textbookChapterId: submittedForm.use_textbook ? submittedForm.textbook_chapter_id : undefined,
        }
        records.value.unshift(newRecord)
        currentRecordId.value = newRecord.id

        saveRecords()
        saveState()

        if (res.data.material_warnings?.length) ElMessage.warning(res.data.material_warnings.join('；'))
        else ElMessage.success('教案生成成功！')
        return true
      }
      return false
    } catch (error: any) {
      ElMessage.error(error.message || '生成失败，请重试')
      return false
    } finally {
      generating.value = false
      currentGenerationInfo.value = null
    }
  }

  // ==================== 记录管理 ====================

  function selectRecord(record: GenerationRecord) {
    currentRecordId.value = record.id
    form.value = { ...record.form }
    form.value.grade = schoolStage(form.value.grade)
    selectedTemplate.value = record.templateType
    generatedContent.value = record.content
    saveState()
  }

  function deleteRecord(id: string) {
    records.value = records.value.filter(r => r.id !== id)
    if (currentRecordId.value === id) {
      currentRecordId.value = null
      generatedContent.value = ''
    }
    saveRecords()
    saveState()
    ElMessage.success('已删除')
  }

  function setWordDocument(recordId: string, documentId: string) {
    const record = records.value.find(item => item.id === recordId)
    if (record) { record.documentId = documentId; saveRecords() }
  }

  function restoreResourceLesson(lesson: AudioLessonDetail) {
    let record = records.value.find(item => item.resourceLessonId === lesson.id ||
      (!!lesson.textbook_lesson_id && item.lessonId === lesson.textbook_lesson_id))
    if (!record) {
      record = {
        id: `resource-${lesson.id}`, title: `${lesson.subject} - ${lesson.title}`,
        createdAt: Date.parse(lesson.created_at) || Date.now(), templateType: 'default',
        content: lesson.content, resourceLessonId: lesson.id, lessonId: lesson.textbook_lesson_id,
        form: { subject: lesson.subject, grade: lesson.grade, topic: lesson.title, duration: 15, key_point: '', difficulty: '' },
      }
      records.value.unshift(record)
    } else {
      record.resourceLessonId = lesson.id
    }
    selectRecord(record)
    saveRecords()
  }

  function createNew() {
    currentRecordId.value = null
    form.value = {
      subject: '',
      grade: '',
      topic: '',
      duration: 15,
      key_point: '',
      difficulty: '',
      modelId: null,
      use_textbook: true,
    }
    generatedContent.value = ''
    selectedTemplate.value = 'default'
    customTemplateText.value = ''
    customTemplateFile.value = ''
    saveState()
  }

  function setCustomTemplate(text: string, filename: string) {
    customTemplateText.value = text
    customTemplateFile.value = filename
    selectedTemplate.value = 'custom'
    saveState()
  }

  function updateForm(newForm: Partial<GenerationForm>) {
    Object.assign(form.value, newForm)
    saveState()
  }

  function setTemplate(template: string) {
    selectedTemplate.value = template
    saveState()
  }

  // 初始化
  function initialize() {
    loadRecords()
    loadState()
  }

  return {
    // 状态
    generating,
    generatedContent,
    records,
    currentRecordId,
    selectedTemplate,
    customTemplateText,
    customTemplateFile,
    form,
    currentGenerationInfo,

    // 计算属性
    canGenerate,
    generationHint,
    sortedRecords,
    currentRecord,

    // 方法
    initialize,
    generateLessonPlan,
    selectRecord,
    deleteRecord,
    setWordDocument,
    restoreResourceLesson,
    createNew,
    setCustomTemplate,
    updateForm,
    setTemplate,
    saveState,
  }
})
