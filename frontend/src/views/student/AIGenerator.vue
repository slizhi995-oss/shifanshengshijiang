<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { 
  Document, 
  Download,
  Refresh,
  MagicStick,
  Close,
  CopyDocument,
  Plus,
  Delete,
  FolderOpened
} from '@element-plus/icons-vue'
import { aiApi, BUILTIN_TEMPLATES } from '@/api/ai'
import { useAIGeneratorStore } from '@/stores/aiGenerator'
import { storeToRefs } from 'pinia'
import TextbookSelector from '@/components/TextbookSelector.vue'
import LessonWordPreview from '@/components/LessonWordPreview.vue'
import LessonMatchedResources from '@/components/LessonMatchedResources.vue'
import { resourceCenterApi } from '@/api/resourceCenter'
import { subjectOptions, stagesForSubject } from '@/constants/textbooks'

// ==================== Store ====================

const store = useAIGeneratorStore()
const route = useRoute()
const router = useRouter()
const { 
  generating, 
  generatedContent, 
  records, 
  currentRecordId, 
  selectedTemplate,
  form,
  sortedRecords,
  currentRecord,
  canGenerate,
  generationHint,
  currentGenerationInfo,
} = storeToRefs(store)

// ==================== 本地状态 ====================

const aiEnabled = ref(true)
const showSettings = ref(true)
const contentRef = ref<HTMLElement | null>(null)
const wordPreview = ref<InstanceType<typeof LessonWordPreview>>()
const wordReady = ref(false)
const matchedResources = ref<InstanceType<typeof LessonMatchedResources>>()
const resourcesVisible = ref(false)
const historyLoading = ref(false)
const historyFailed = ref(false)
let historyRevision = 0
watch(() => [currentRecordId.value, generating.value], () => { resourcesVisible.value = false }, { flush: 'sync' })
const stageOptions = computed(() => stagesForSubject(form.value.subject))

// ==================== 计算属性 ====================

const currentTemplateLabel = computed(() => {
  const tpl = BUILTIN_TEMPLATES.find(t => t.value === selectedTemplate.value)
  return tpl ? tpl.label : '经典教案'
})

// ==================== 方法 ====================

const checkAIStatus = async () => {
  try {
    const status = await aiApi.getStatus()
    aiEnabled.value = status.enabled
  } catch {
    aiEnabled.value = false
  }
}

const prepareForm = () => {
  store.updateForm({ use_textbook: true, duration: 15 })
  store.setTemplate('default')
}

const leaveSharedLesson = () => {
  ++historyRevision
  historyLoading.value = false
  historyFailed.value = false
  void router.replace({ query: {} })
}

const generateLessonPlan = async () => {
  leaveSharedLesson()
  prepareForm()
  showSettings.value = false
  const success = await store.generateLessonPlan()
  if (success) {
    nextTick(() => contentRef.value?.scrollTo({ top: 0, behavior: 'smooth' }))
  }
}

const selectRecord = (record: any) => {
  leaveSharedLesson()
  store.selectRecord(record)
  showSettings.value = false
}

const deleteRecord = (id: string, e: Event) => {
  e.stopPropagation()
  store.deleteRecord(id)
}

const createNew = () => {
  leaveSharedLesson()
  store.createNew()
  showSettings.value = true
}

const copyContent = () => wordPreview.value?.copy()
const downloadContent = () => wordPreview.value?.download()
const saveDocument = (id: string) => {
  if (currentRecordId.value) store.setWordDocument(currentRecordId.value, id)
}

const showResources = () => matchedResources.value?.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })

async function openSharedLesson() {
  const revision = ++historyRevision
  historyFailed.value = false
  historyLoading.value = false
  const resourceId = Number(route.query.resourceLesson)
  const legacyId = Number(route.query.lesson)
  const validResourceId = Number.isInteger(resourceId) && resourceId > 0
  if (!validResourceId && !(Number.isInteger(legacyId) && legacyId > 0)) return
  historyLoading.value = true
  try {
    const id = validResourceId ? resourceId : (await resourceCenterApi.resolve(legacyId, true)).id
    const lesson = await resourceCenterApi.detail(id, true)
    if (revision !== historyRevision) return
    if (!lesson.content?.trim()) throw new Error('教案正文不可用')
    store.restoreResourceLesson(lesson)
    showSettings.value = false
  } catch { if (revision === historyRevision) historyFailed.value = true }
  finally { if (revision === historyRevision) historyLoading.value = false }
}
watch(() => [route.query.resourceLesson, route.query.lesson], openSharedLesson)
onBeforeUnmount(() => { ++historyRevision })

const formatDate = (ts: number) => {
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

// 初始化时，如果正在生成中则不显示设置面板
onMounted(() => {
  checkAIStatus()
  store.initialize()
  void openSharedLesson()
  if (!generating.value && !generatedContent.value) prepareForm()
  
  // 如果正在生成或有内容，隐藏设置面板
  if (generating.value || generatedContent.value) {
    showSettings.value = false
  }
})
</script>

<template>
  <div class="generator-layout">
    <!-- 左侧历史记录 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <el-button class="new-btn" @click="createNew">
          <el-icon><Plus /></el-icon>
          <span>新建教案</span>
        </el-button>
      </div>
      
      <div class="history-list">
        <div class="list-title">历史记录</div>
        <div v-if="sortedRecords.length === 0" class="empty-history">
          暂无历史记录
        </div>
        <div 
          v-for="record in sortedRecords" 
          :key="record.id"
          class="history-item"
          :class="{ active: currentRecordId === record.id }"
          @click="selectRecord(record)"
        >
          <div class="item-content">
            <span class="item-title">{{ record.title }}</span>
            <span class="item-date">{{ formatDate(record.createdAt) }}</span>
          </div>
          <el-button 
            class="delete-btn" 
            link 
            type="danger" 
            @click="(e: Event) => deleteRecord(record.id, e)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主区域 -->
    <div class="main-area">
      <!-- AI 未启用提示 -->
      <el-alert
        v-if="!aiEnabled"
        title="AI 功能暂未开启"
        type="warning"
        description="请联系管理员开启 AI 功能"
        show-icon
        :closable="false"
        class="alert-bar"
      />

      <div class="content-wrapper" v-else>
        <div v-if="historyLoading" class="loading-state" role="status">正在打开历史教案…</div>
        <div v-else-if="historyFailed" class="loading-state" role="alert">历史教案加载失败 <el-button @click="openSharedLesson">重试</el-button></div>
        <!-- 生成结果页 -->
        <div v-else-if="generatedContent || generating" class="result-view">
          <div class="result-toolbar">
            <div class="info">
              <el-button @click="showSettings = true; generatedContent = ''; prepareForm()" circle>
                <el-icon><MagicStick /></el-icon>
              </el-button>
              <div class="meta-group">
                <span class="title">{{ form.topic || '未命名教案' }}</span>
                <span class="meta">{{ form.subject }} · {{ form.grade }} · {{ currentTemplateLabel }}</span>
              </div>
            </div>
            <div class="actions">
              <el-button v-if="resourcesVisible && !generating" :icon="FolderOpened" @click="showResources">配套资源</el-button>
              <el-button @click="copyContent" :disabled="generating || !wordReady">
                <el-icon class="mr-1"><CopyDocument /></el-icon>
                复制
              </el-button>
              <el-button type="primary" @click="downloadContent" :disabled="generating || !wordReady">
                <el-icon class="mr-1"><Download /></el-icon>
                下载 Word
              </el-button>
            </div>
          </div>

          <!-- 生成中状态 -->
          <div class="loading-state" v-if="generating">
            <div class="spinner"></div>
            <h3>{{ currentGenerationInfo?.useTextbook ? '正在按教材生成教案...' : '正在生成教案...' }}</h3>
            <p>{{ currentGenerationInfo?.subject || form.subject }} · {{ currentGenerationInfo?.grade || form.grade }} · {{ currentGenerationInfo?.topic || form.topic }}</p>
            <p class="hint">{{ currentGenerationInfo?.useTextbook ? '先提取并核对所选章节的图片，再结合教材正文和图片资料生成教案；已有提取结果会直接复用，请稍候' : 'AI 正在根据你的要求撰写教案，请稍候' }}</p>
            <p class="hint-safe">切换页面不会中断生成</p>
          </div>

          <!-- 生成结果 -->
          <div v-else ref="contentRef" class="result-body">
          <LessonWordPreview ref="wordPreview" flow :content="generatedContent" :title="form.topic || '教案'"
            :lesson-id="currentRecord?.lessonId" :document-id="currentRecord?.documentId"
            @ready="wordReady = $event" @document-created="saveDocument" />
          <LessonMatchedResources v-if="currentRecord?.resourceLessonId || currentRecord?.lessonId"
            :key="currentRecord.id" ref="matchedResources" :resource-lesson-id="currentRecord.resourceLessonId"
            :lesson-id="currentRecord.lessonId" @results="resourcesVisible = $event" />
          </div>
        </div>

        <!-- 参数设置页 -->
        <div v-else class="form-view">
          <div class="form-container">
            <div class="view-header">
              <h2>AI 教案生成</h2>
              <p>选择科目、学段、教材和章节，生成对应教案</p>
            </div>

            <!-- 基本信息 -->
            <div class="section">
              <div class="section-title">课题信息</div>
              <el-form label-position="top" size="large">
                <div class="form-row">
                  <el-form-item label="科目" required class="flex-1">
                    <el-select v-model="form.subject" placeholder="选择科目" class="w-full">
                      <el-option v-for="sub in subjectOptions" :key="sub" :value="sub" :label="sub" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="学段" required class="flex-1">
                    <el-select v-model="form.grade" placeholder="选择学段" :disabled="!form.subject" class="w-full">
                      <el-option v-for="g in stageOptions" :key="g" :value="g" :label="g" />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item>
                  <TextbookSelector v-model="form.textbook_chapter_id" v-model:book-id="form.textbook_id"
                    :subject="form.subject" :grade="form.grade" v-model:topic="form.topic" class="w-full" />
                </el-form-item>
                <el-form-item label="课题名称" required>
                  <el-input v-model="form.topic" placeholder="选择章节后自动填写，也可自行修改" />
                </el-form-item>
                <div class="form-row">
                  <el-form-item label="教学重点（可选）" class="flex-1">
                    <el-input v-model="form.key_point" type="textarea" :rows="2" placeholder="教学重点" />
                  </el-form-item>
                  <el-form-item label="教学难点（可选）" class="flex-1">
                    <el-input v-model="form.difficulty" type="textarea" :rows="2" placeholder="教学难点" />
                  </el-form-item>
                </div>
              </el-form>
            </div>

            <!-- 生成按钮 -->
            <div class="action-bar">
              <p v-if="generationHint" role="status" style="color:#64748b;font-size:13px">{{ generationHint }}</p>
              <el-button 
                type="primary" 
                size="large"
                :loading="generating" 
                :disabled="!canGenerate"
                @click="generateLessonPlan"
                class="generate-btn"
              >
                <el-icon class="mr-1" v-if="!generating"><MagicStick /></el-icon>
                {{ generating ? '正在生成...' : '生成教案' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.generator-layout {
  display: flex;
  height: calc(100vh - 84px);
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  border: 1px solid #f3f4f6;
  margin: -12px;
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  background: #f8fafc;
  border-right: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 20px;
}

.new-btn {
  width: 100%;
  background: #10b981;
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
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(16, 185, 129, 0.1);
}

.new-btn:hover {
  background: #059669;
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(16, 185, 129, 0.2);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px;
}

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
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.history-item:hover {
  background: #ffffff;
  border-color: #e2e8f0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.history-item.active {
  background: #ecfdf5;
  border-color: #d1fae5;
  color: #059669;
}

.item-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  margin-right: 8px;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #334155;
}

.history-item.active .item-title {
  color: #059669;
}

.item-date {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 3px;
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

/* 主区域 */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background: #ffffff;
}

.alert-bar {
  margin: 16px 24px 0;
  border-radius: 10px;
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

/* 表单视图：居中 + 限宽 */
.form-view {
  flex: 1;
  overflow-y: auto;
  padding: 40px 32px 56px;
  background: #ffffff;
}

.form-container {
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

/* 页面标题 */
.view-header {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f1f5f9;
}

.view-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.view-header p {
  color: #64748b;
  font-size: 13px;
  margin: 0;
}

/* 区块 */
.section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-left: 3px solid #10b981;
  padding-left: 12px;
}

/* 快捷填充 */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-card:hover {
  border-color: #10b981;
  background: #f0fdf4;
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.quick-card .icon {
  font-size: 24px;
  color: #10b981;
}

.quick-card .text {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

/* 表单行 */
.form-row {
  display: flex;
  gap: 20px;
}

.flex-1 {
  flex: 1;
}

.w-100 {
  width: 140px;
}

.w-full {
  width: 100%;
}

/* 模板选择 */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.template-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px;
  background: #f8fafc;
  border: 2px solid transparent;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  background: #f1f5f9;
}

.template-card.active {
  border-color: #10b981;
  background: #ecfdf5;
}

.template-card .icon {
  font-size: 32px;
  color: #64748b;
}

.template-card.active .icon {
  color: #059669;
}

.template-card .label {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.template-card.active .label {
  color: #059669;
}

/* 上传区域 */
.upload-area {
  margin-top: 20px;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 32px;
  border-radius: 16px;
  border: 2px dashed #e2e8f0;
  background: #f8fafc;
  transition: all 0.2s;
}

.upload-area :deep(.el-upload-dragger:hover) {
  border-color: #10b981;
  background: #f0fdf4;
}

.upload-content, .uploaded-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #64748b;
}

.upload-icon {
  font-size: 40px;
  color: #94a3b8;
  margin-bottom: 4px;
}

/* 生成按钮 */
.action-bar {
  margin-top: 40px;
  padding-top: 32px;
  border-top: 1px solid #f1f5f9;
}

.generate-btn {
  width: 100%;
  height: 52px;
  background: #10b981;
  border: none;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(16, 185, 129, 0.15);
  transition: all 0.2s;
}

.generate-btn:hover {
  background: #059669;
  transform: translateY(-1px);
  box-shadow: 0 6px 8px rgba(16, 185, 129, 0.2);
}

.generate-btn:disabled {
  background: #d1fae5;
  transform: none;
  box-shadow: none;
}

/* 结果视图 */
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

.result-body { flex: 1; min-height: 0; overflow: auto; }

@media (max-width: 760px) {
  .generator-layout { flex-direction: column; margin: 0; height: calc(100dvh - 100px); }
  .sidebar { width: 100%; max-height: 150px; border-right: 0; border-bottom: 1px solid #f1f5f9; }
  .sidebar-header { padding: 10px 12px; }.new-btn { height: 36px; }.history-list { padding: 0 12px 8px; }
  .main-area { min-height: 0; }.result-toolbar { padding: 12px; flex-wrap: wrap; gap: 12px; }
  .result-toolbar .info { min-width: 0; gap: 10px; }.meta-group { min-width: 0; }.meta-group .title { overflow-wrap: anywhere; }
  .result-toolbar .actions { flex-wrap: wrap; gap: 8px; }.result-toolbar .actions .el-button { margin: 0; }
  .form-view { padding: 24px 16px; }.form-row { flex-direction: column; gap: 0; }
}

/* 加载状态 */
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #fff;
}

.spinner {
  width: 56px;
  height: 56px;
  border: 4px solid #f1f5f9;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 1s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite;
  margin-bottom: 32px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state h3 {
  font-size: 22px;
  color: #1e293b;
  margin: 0 0 12px;
  font-weight: 700;
}

.loading-state p {
  color: #64748b;
  margin: 0;
  font-size: 16px;
}

.loading-state .hint {
  margin-top: 24px;
  font-size: 14px;
  background: #f0fdf4;
  color: #166534;
  padding: 10px 20px;
  border-radius: 20px;
}

.loading-state .hint-safe {
  margin-top: 12px;
  font-size: 13px;
  color: #10b981;
  font-weight: 500;
}

/* 工具类 */
.mr-1 { margin-right: 4px; }
</style>
