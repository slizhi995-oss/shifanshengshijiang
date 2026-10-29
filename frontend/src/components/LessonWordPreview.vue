<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { aiApi } from '@/api/ai'

const props = defineProps<{ content: string; title: string; lessonId?: number; documentId?: string; flow?: boolean }>()
const emit = defineEmits<{
  (e: 'document-created', id: string): void
  (e: 'ready', ready: boolean): void
}>()
const container = ref<HTMLElement>()
const loading = ref(false)
const failed = ref(false)
let revision = 0
let wordBlob: Blob | undefined
let documentId: string | undefined
let filename = ''

async function load() {
  const current = ++revision
  wordBlob = undefined; failed.value = false; loading.value = true; emit('ready', false)
  try {
    let id = props.documentId || documentId
    let created = false
    if (!id) {
      const result = await aiApi.createWordDocument({ content: props.content, title: props.title, lesson_id: props.lessonId })
      id = result.data.document_id; filename = result.data.document_filename; created = true
    }
    let blob: Blob
    try { blob = await aiApi.wordDocument(id) }
    catch (error: any) {
      if (!created && error.response?.status === 404) {
        const result = await aiApi.createWordDocument({ content: props.content, title: props.title, lesson_id: props.lessonId })
        id = result.data.document_id; filename = result.data.document_filename; created = true
        blob = await aiApi.wordDocument(id)
      } else throw error
    }
    if (current !== revision) return
    const { renderAsync } = await import('docx-preview')
    const detached = document.createElement('div')
    await renderAsync(await blob.arrayBuffer(), detached, undefined, {
      className: 'lesson-docx', inWrapper: true, ignoreHeight: true,
      useBase64URL: true, renderAltChunks: false, breakPages: false,
    })
    if (current !== revision) return
    await nextTick()
    container.value?.replaceChildren(...Array.from(detached.childNodes))
    wordBlob = blob; documentId = id
    if (created) emit('document-created', id)
    emit('ready', true)
  } catch {
    if (current === revision) { failed.value = true; emit('ready', false) }
  } finally {
    if (current === revision) loading.value = false
  }
}

watch(() => [props.content, props.title, props.lessonId], () => {
  documentId = undefined; filename = ''; load()
}, { immediate: true })

function download() {
  if (!wordBlob) return
  const url = URL.createObjectURL(wordBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || `${props.title.replace(/[\\/:*?"<>|]/g, '_') || '教案'}_教案.docx`
  document.body.appendChild(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function copy() {
  if (!wordBlob || !container.value) return
  try {
    await navigator.clipboard.writeText(container.value.innerText)
    ElMessage.success('已复制教案正文')
  } catch { ElMessage.error('复制失败，请选择正文后复制') }
}
onBeforeUnmount(() => { ++revision })
defineExpose({ download, copy })
</script>

<template>
  <div class="lesson-word-preview" :class="{ 'flow-preview': flow }" :aria-busy="loading">
    <p v-if="loading" class="preview-status" role="status">正在加载 Word 教案…</p>
    <div v-if="failed" class="preview-status" role="alert">
      Word 教案加载失败，请重试。
      <el-button link type="primary" @click="load">重试</el-button>
    </div>
    <div v-show="!loading && !failed" ref="container" class="word-pages" tabindex="0" role="region" aria-label="教案预览" />
  </div>
</template>

<style scoped>
.lesson-word-preview { width: 100%; min-width: 0; min-height: 0; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.flow-preview { flex: none; overflow: visible; }.flow-preview .word-pages { flex: none; overflow-x: auto; overscroll-behavior: auto; }
.preview-status { padding: 32px; color: #64748b; text-align: center; }
.word-pages { width: 100%; flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; }
.word-pages :deep(.lesson-docx-wrapper) { background: #f1f5f9; padding: 24px 16px; }
.word-pages :deep(section.lesson-docx) { margin: 0 auto 16px; color: #111827; max-width: none; }
.word-pages :deep(img) { max-width: 100%; height: auto; }
.word-pages :deep(table) { border-collapse: collapse; }
.word-pages :deep(math) { font-family: 'Cambria Math', 'STIX Two Math', serif; }
</style>
