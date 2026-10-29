<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { textbookApi, type Textbook, type Chapter, type TextbookAsset } from '@/api/textbooks'
import TextbookImage from '@/components/TextbookImage.vue'
import { subjectOptions, stageOptions } from '@/constants/textbooks'
const books = ref<Textbook[]>([])
const selected = ref<Textbook>()
const chapters = ref<Chapter[]>([])
const assets = ref<TextbookAsset[]>([])
const chapterId = ref<number>()
const page = ref(1)
const loading = ref(false)
const uploading = ref(false)
const uploadVisible = ref(false)
const chapterVisible = ref(false)
const pdfVisible = ref(false)
const pdfSource = ref('')
const imageVisible = ref(false)
const imageFile = ref<File>()
const imagePage = ref(1)
const uploadFile = ref<File>()
const editingBook = ref<number>()
const uploadKey = ref(0)
const metadata = reactive({ title: '', subject: '物理', grade: '高中一年级', publisher: '', edition: '', volume: '必修第一册' })
const editor = reactive({ title: '', parent_title: '', start_page: 1, end_page: 1, printed_pages: '', content: '', is_published: false })
const candidates = computed(() => assets.value.slice((page.value - 1) * 12, page.value * 12))
const activeChapter = computed(() => chapters.value.find(c => c.id === chapterId.value))
async function load() { books.value = (await textbookApi.books()).data }
async function select(book: Textbook) {
  selected.value = book; chapterId.value = undefined; page.value = 1
  loading.value = true
  try {
    const [c, a] = await Promise.all([textbookApi.chapters(book.id), textbookApi.assets(book.id)])
    chapters.value = c.data; assets.value = a.data
  } finally { loading.value = false }
}
function chooseFile(file: UploadFile) { uploadFile.value = file.raw }
function editMetadata(book?: Textbook) {
  editingBook.value = book?.id; uploadFile.value = undefined; uploadKey.value++
  for (const key of Object.keys(metadata) as (keyof typeof metadata)[]) metadata[key] = book?.[key] || (key === 'subject' ? '物理' : key === 'grade' ? '高中一年级' : key === 'volume' ? '必修第一册' : '')
  uploadVisible.value = true
}
function chooseImage(file: UploadFile) { imageFile.value = file.raw }
async function uploadImage() {
  if (!selected.value || !imageFile.value) { ElMessage.warning('请选择裁好的教材图片'); return }
  const body = new FormData()
  body.append('file', imageFile.value); body.append('pdf_page', String(imagePage.value))
  uploading.value = true
  try {
    await textbookApi.uploadAsset(selected.value.id, body)
    imageVisible.value = false; await filterAssets()
    ElMessage.success('图片已保存，请填写章节、标签与说明并核对')
  } finally { uploading.value = false }
}
async function upload() {
  if (!metadata.title.trim() || (!editingBook.value && !uploadFile.value)) { ElMessage.warning('请选择PDF并填写教材名称'); return }
  const body = new FormData()
  if (uploadFile.value) body.append('file', uploadFile.value)
  for (const [key, value] of Object.entries(metadata)) body.append(key, value)
  uploading.value = true
  try {
    const result = editingBook.value ? await textbookApi.saveBook(editingBook.value, { ...metadata }) : await textbookApi.upload(body)
    uploadVisible.value = false; await load(); await select(result.data)
    ElMessage.success('教材已保存，请核对章节正文和图片后发布')
  } finally { uploading.value = false }
}
async function editChapter(chapter?: Chapter) {
  chapterId.value = chapter?.id
  if (chapter) {
    const result = await textbookApi.chapter(chapter.id)
    Object.assign(editor, result.data)
  } else Object.assign(editor, { title: '', parent_title: '', start_page: 1, end_page: 1, printed_pages: '', content: '', is_published: false })
  chapterVisible.value = true
}
async function pullText() {
  if (!selected.value || editor.end_page < editor.start_page) return
  loading.value = true
  try {
    const rows = await Promise.all(Array.from({ length: editor.end_page - editor.start_page + 1 }, (_, n) => textbookApi.page(selected.value!.id, editor.start_page + n)))
    editor.content = rows.map((row, i) => `[PDF第${editor.start_page + i}页]\n${row.data.content}`).join('\n\n')
  } finally { loading.value = false }
}
async function saveChapter() {
  if (!selected.value) return
  const body = { ...editor, content: editor.content || null }
  const result = chapterId.value ? await textbookApi.saveChapter(chapterId.value, body) : await textbookApi.createChapter(selected.value.id, body)
  chapterVisible.value = false; chapterId.value = result.data.id
  chapters.value = (await textbookApi.chapters(selected.value.id)).data
  await filterAssets(); await load()
  ElMessage.success(editor.is_published ? '章节已发布，可用于生成教案' : '章节草稿已保存')
}
async function filterAssets() {
  if (!selected.value) return
  page.value = 1
  const chapter = activeChapter.value
  assets.value = (await textbookApi.assets(selected.value.id, chapter?.start_page, chapter?.end_page)).data
}
function tagsChanged(asset: TextbookAsset, value: string) { asset.tags = value.split(/[，,；;]/).map(t => t.trim()).filter(Boolean) }
async function saveImage(asset: TextbookAsset) {
  const result = await textbookApi.saveAsset(asset)
  Object.assign(asset, result.data)
  ElMessage.success('图片信息已保存')
}
async function showPdf() {
  if (!selected.value) return
  if (pdfSource.value) URL.revokeObjectURL(pdfSource.value)
  pdfSource.value = URL.createObjectURL(await textbookApi.pdf(selected.value.id))
  pdfVisible.value = true
}
onMounted(load)
onBeforeUnmount(() => { if (pdfSource.value) URL.revokeObjectURL(pdfSource.value) })
</script>
<template>
  <div class="textbook-manager">
    <div class="toolbar"><h2>教材与图片素材</h2><el-button type="primary" @click="editMetadata()">上传教材 PDF</el-button></div>
    <p>核对版本、章节正文和图片信息后发布。用户确认章节后，生成教案会使用对应正文与已核对图片。</p>
    <el-table :data="books" highlight-current-row @row-click="select">
      <el-table-column prop="title" label="教材" /><el-table-column prop="edition" label="版本" />
      <el-table-column prop="volume" label="册次" /><el-table-column prop="grade" label="年级" width="120" />
      <el-table-column prop="page_count" label="PDF页数" width="90" />
      <el-table-column label="状态" width="140"><template #default="{ row }">{{ row.status === 'needs_ocr' ? '需要OCR/补充正文' : row.is_published ? '已发布章节' : '待核对' }}</template></el-table-column>
      <el-table-column label="操作" width="110"><template #default="{ row }"><el-button size="small" @click.stop="editMetadata(row)">修改信息</el-button></template></el-table-column>
    </el-table>
    <section v-if="selected" v-loading="loading">
      <div class="toolbar"><h3>{{ selected.title }} · {{ selected.edition }}</h3><div><el-button @click="showPdf">查看原教材</el-button><el-button @click="editChapter()">新增章节</el-button></div></div>
      <el-alert v-if="selected.status === 'needs_ocr'" type="warning" :closable="false" title="此PDF文字不足，请先补充并核对章节正文；整页扫描图不会自动作为教材插图入库。" />
      <el-table :data="chapters">
        <el-table-column prop="title" label="章节" /><el-table-column label="PDF页码"><template #default="{ row }">{{ row.start_page }}–{{ row.end_page }}</template></el-table-column>
        <el-table-column label="状态"><template #default="{ row }">{{ row.is_published ? '已核对发布' : '草稿' }}</template></el-table-column>
        <el-table-column label="操作"><template #default="{ row }"><el-button size="small" @click="editChapter(row)">核对正文</el-button><el-button size="small" @click="chapterId = row.id; filterAssets()">整理图片</el-button></template></el-table-column>
      </el-table>
      <div class="toolbar"><h3>图片候选（{{ assets.length }}）</h3><el-select v-model="chapterId" clearable placeholder="按章节筛选" @change="filterAssets"><el-option v-for="c in chapters" :key="c.id" :value="c.id" :label="c.title" /></el-select></div>
      <p>图片来自PDF原图，装饰、标题图和不适用素材可保持未核对。只有关联章节且已核对的图片用于教案生成。扫描或矢量图可从原教材裁图后上传。</p>
      <el-button @click="imagePage = activeChapter?.start_page || 1; imageVisible = true">补充教材裁图</el-button>
      <div class="asset-grid">
        <div v-for="asset in candidates" :key="asset.asset_id" class="asset-card">
          <TextbookImage :asset-id="asset.asset_id" :alt="asset.title" />
          <small>PDF第{{ asset.pdf_page }}页 · {{ asset.width }}×{{ asset.height }}像素</small>
          <el-input v-model="asset.title" placeholder="图片名称" />
          <el-select v-model="asset.chapter_id" clearable placeholder="关联章节"><el-option v-for="c in chapters.filter(c => c.start_page <= asset.pdf_page && c.end_page >= asset.pdf_page)" :key="c.id" :value="c.id" :label="c.title" /></el-select>
          <el-input v-model="asset.figure_number" placeholder="教材图号（无编号留空）" />
          <el-input v-model="asset.description" type="textarea" :rows="2" placeholder="实际图片内容和教学用途" />
          <el-input :model-value="asset.tags.join('，')" @update:model-value="tagsChanged(asset, $event)" placeholder="知识点、对象、用途标签，以逗号分隔" />
          <el-input v-model="asset.conditions" type="textarea" :rows="2" placeholder="必要条件及不适用情况" />
          <el-checkbox v-model="asset.is_reviewed">已核对实图、图注和适用条件</el-checkbox>
          <el-button @click="saveImage(asset)">保存图片信息</el-button>
        </div>
      </div>
      <el-pagination v-model:current-page="page" :page-size="12" :total="assets.length" layout="prev, pager, next" />
    </section>
    <el-dialog v-model="uploadVisible" :title="editingBook ? '修改教材信息' : '上传教材 PDF'" width="560px">
      <el-form label-position="top">
        <el-form-item label="教材名称"><el-input v-model="metadata.title" /></el-form-item>
        <div class="row"><el-form-item label="科目"><el-select v-model="metadata.subject"><el-option v-for="s in subjectOptions" :key="s" :value="s" :label="s" /></el-select></el-form-item><el-form-item label="学段 / 年级"><el-select v-model="metadata.grade" filterable allow-create><el-option v-for="g in stageOptions" :key="g" :value="g" :label="g" /></el-select></el-form-item></div>
        <el-form-item label="出版社"><el-input v-model="metadata.publisher" /></el-form-item>
        <el-form-item label="版本/版次"><el-input v-model="metadata.edition" placeholder="依据教材版权页填写" /></el-form-item>
        <el-form-item label="册次"><el-input v-model="metadata.volume" /></el-form-item>
        <el-upload v-if="!editingBook" :key="uploadKey" :auto-upload="false" :limit="1" accept=".pdf" :on-change="chooseFile"><el-button>选择PDF（最多80MB）</el-button></el-upload>
      </el-form><template #footer><el-button :loading="uploading" type="primary" @click="upload">{{ editingBook ? '保存信息' : '保存并解析' }}</el-button></template>
    </el-dialog>
    <el-dialog v-model="chapterVisible" title="核对章节正文" width="850px">
      <el-input v-model="editor.title" placeholder="章节/小节标题" />
      <div class="row"><el-input-number v-model="editor.start_page" :min="1" :max="selected?.page_count" /><span>至</span><el-input-number v-model="editor.end_page" :min="editor.start_page" :max="selected?.page_count" /><el-button :loading="loading" @click="pullText">读取这些PDF页</el-button></div>
      <el-input v-model="editor.printed_pages" placeholder="教材印刷页码，例如83–87" />
      <el-input v-model="editor.content" type="textarea" :rows="18" placeholder="核对公式、定义、题目条件；扫描教材可在这里补充经核对的正文。" />
      <el-checkbox v-model="editor.is_published">已对照原教材核对正文和页码，发布此章节</el-checkbox>
      <template #footer><el-button type="primary" @click="saveChapter">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="pdfVisible" title="原教材" width="90%"><iframe v-if="pdfSource" :src="pdfSource" style="width:100%;height:75vh;border:0" /></el-dialog>
    <el-dialog v-model="imageVisible" title="补充教材裁图" width="480px">
      <p>填写图片在原PDF中的实际页码。上传后仍需关联章节、填写标签和核对图片。</p>
      <el-input-number v-model="imagePage" :min="1" :max="selected?.page_count" />
      <el-upload :auto-upload="false" :limit="1" accept="image/png,image/jpeg,image/webp" :on-change="chooseImage"><el-button>选择图片（最多12MB）</el-button></el-upload>
      <template #footer><el-button :loading="uploading" type="primary" @click="uploadImage">保存图片</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.textbook-manager { padding: 24px; } .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 18px 0; }
p, small { color: #64748b; } section { margin-top: 24px; } .asset-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(285px,1fr)); gap: 18px; margin: 16px 0; }
.asset-card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 9px; }
.row { display: flex; align-items: center; gap: 12px; margin: 12px 0; } .row .el-form-item { flex: 1; }
</style>
