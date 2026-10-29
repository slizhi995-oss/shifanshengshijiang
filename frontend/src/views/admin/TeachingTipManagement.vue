<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { teachingTipsApi, type TeachingTip, type TeachingTipInput } from '@/api/teachingTips'

const rows = ref<TeachingTip[]>([])
const loading = ref(false)
const failed = ref(false)
const saving = ref(false)
const fetching = ref(false)
const uploadingCover = ref(false)
const busy = computed(() => saving.value || fetching.value || uploadingCover.value)
const coverFileInput = ref<HTMLInputElement>()
const coverPreviewFailed = ref(false)
const editor = ref(false)
const editingId = ref<number>()
const formError = ref('')
const defaults = (): TeachingTipInput => ({ url: '', title: '', category: '试讲技巧', description: '', cover_url: '', sort_order: 0, is_published: false })
const form = reactive(defaults())
watch(() => form.cover_url, () => { coverPreviewFailed.value = false })

async function load() {
  loading.value = true
  failed.value = false
  try { rows.value = (await teachingTipsApi.admin()).items }
  catch { failed.value = true }
  finally { loading.value = false }
}
function edit(item?: TeachingTip) {
  editingId.value = item?.id
  Object.assign(form, item ? { url: item.url, title: item.title, category: item.category, description: item.description, cover_url: item.cover_url, sort_order: item.sort_order, is_published: item.is_published } : defaults())
  formError.value = ''
  editor.value = true
}
async function fetchMetadata() {
  if (!form.url.trim()) { formError.value = '请先填写 B 站视频完整链接'; return }
  fetching.value = true
  formError.value = ''
  const url = form.url
  try {
    const result = await teachingTipsApi.metadata(url)
    if (form.url !== url) return
    if (result.title) form.title = result.title
    if (result.cover_url && !form.cover_url.startsWith('/uploads/teaching-tip-covers/')) form.cover_url = result.cover_url
    if (!result.title && !result.cover_url) formError.value = '暂时无法读取视频信息，请手动填写标题并上传封面。'
  } catch { /* The shared request handler displays errors. */ }
  finally { fetching.value = false }
}
async function uploadCover(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || busy.value) return
  formError.value = ''
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    formError.value = '请上传 JPG、PNG 或 WebP 图片'; return
  }
  if (file.size > 5 * 1024 * 1024) { formError.value = '封面图片不能超过 5 MB'; return }
  uploadingCover.value = true
  try {
    form.cover_url = (await teachingTipsApi.uploadCover(file)).cover_url
    coverPreviewFailed.value = false
    ElMessage.success('封面已上传，保存视频后生效')
  } catch { /* The shared request handler displays upload errors. */ }
  finally { uploadingCover.value = false }
}
async function save() {
  if (busy.value) return
  formError.value = ''
  if (!form.url.trim() || !form.title.trim() || !form.category.trim()) { formError.value = '请填写视频链接、标题和分类'; return }
  saving.value = true
  try {
    if (editingId.value) await teachingTipsApi.update(editingId.value, { ...form })
    else await teachingTipsApi.create({ ...form })
    editor.value = false
    ElMessage.success('试讲技巧视频已保存')
    await load()
  } catch { /* Shared error handling. */ }
  finally { saving.value = false }
}
async function remove(item: TeachingTip) {
  try { await ElMessageBox.confirm(`确定删除“${item.title}”？`, '删除试讲技巧视频', { type: 'warning' }) }
  catch { return }
  try { await teachingTipsApi.remove(item.id); await load() }
  catch { /* Shared error handling. */ }
}
onMounted(load)
</script>

<template>
  <section class="tip-management">
    <header><div><h2>试讲技巧视频</h2><p>在 AI 资源中心没有教案或未找到对应资源时，展示已上架的 B 站精选视频。</p></div><div class="actions"><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button><el-button type="primary" :icon="Plus" @click="edit()">添加视频</el-button></div></header>
    <el-alert title="可自动读取视频信息，也可直接上传封面。排序数值越小越靠前；新视频默认下架，确认内容后可上架。" type="info" :closable="false" show-icon />
    <p v-if="failed" role="alert">视频列表加载失败 <el-button link type="primary" @click="load">重试</el-button></p>
    <el-table v-loading="loading" :data="rows" empty-text="尚未添加试讲技巧视频">
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="封面" width="130"><template #default="{ row }"><el-image v-if="row.cover_url" class="table-cover" :src="row.cover_url" :alt="`${row.title}的封面`" fit="cover" referrerpolicy="no-referrer"><template #error><span class="cover-hint">封面加载失败</span></template></el-image><span v-else class="cover-hint">未设置封面</span></template></el-table-column>
      <el-table-column label="视频" min-width="260"><template #default="{ row }"><a :href="row.url" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">{{ row.title }} ↗</a><p class="description">{{ row.description }}</p></template></el-table-column>
      <el-table-column prop="category" label="分类" min-width="110" />
      <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.is_published ? 'success' : 'info'">{{ row.is_published ? '已上架' : '已下架' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="170"><template #default="{ row }"><el-button link type="primary" @click="edit(row)">编辑 / 上下架</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-dialog v-model="editor" :title="editingId ? '编辑试讲技巧视频' : '添加试讲技巧视频'" width="min(640px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
      <el-form label-position="top" :disabled="busy" @submit.prevent="save">
        <el-form-item label="B 站视频完整链接（必填）"><div class="url-input"><el-input v-model="form.url" placeholder="https://www.bilibili.com/video/BV…/" maxlength="1024" /><el-button :loading="fetching" @click="fetchMetadata">读取标题与封面</el-button></div></el-form-item>
        <el-form-item label="视频标题（必填）"><el-input v-model="form.title" maxlength="256" /></el-form-item>
        <el-form-item label="技巧分类（必填）"><el-input v-model="form.category" placeholder="如：试讲导入、板书设计、教姿教态" maxlength="64" /></el-form-item>
        <el-form-item label="内容简介"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
        <el-form-item label="视频封面">
          <div class="cover-editor">
            <div class="cover-preview"><img v-if="form.cover_url && !coverPreviewFailed" :src="form.cover_url" alt="视频封面预览" referrerpolicy="no-referrer" @error="coverPreviewFailed = true" /><span v-else>未设置可用封面</span></div>
            <div class="cover-controls"><input ref="coverFileInput" class="cover-file-input" type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择封面图片" :disabled="busy" @change="uploadCover" /><el-button :loading="uploadingCover" @click="coverFileInput?.click()">上传封面</el-button><p>支持 JPG、PNG、WebP，最大 5 MB，建议使用 16:9 图片。上传后点击保存生效。</p></div>
          </div>
          <el-input v-model="form.cover_url" class="cover-url" placeholder="也可粘贴 B 站封面图片链接" maxlength="2048" aria-label="封面图片链接" />
        </el-form-item>
        <el-form-item label="展示顺序（数值越小越靠前）"><el-input-number v-model="form.sort_order" :min="0" :max="99999" :precision="0" /></el-form-item>
        <el-form-item label="资源中心展示"><el-switch v-model="form.is_published" active-text="上架" inactive-text="下架" /></el-form-item>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </el-form>
      <template #footer><el-button :disabled="busy" @click="editor = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="fetching || uploadingCover" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.tip-management { padding: 24px; }header { display: flex; justify-content: space-between; align-items: center; gap: 18px; margin-bottom: 20px; }h2 { margin: 0 0 10px; }header p, .description { font-size: 13px; line-height: 1.7; color: #64748b; }.description { margin: 6px 0; white-space: pre-wrap; overflow-wrap: anywhere; }.actions, .url-input { display: flex; gap: 8px; }.actions { flex-shrink: 0; }.actions .el-button, .url-input .el-button { margin: 0; }.url-input { width: 100%; }.url-input .el-input { min-width: 0; }.el-alert { margin-bottom: 18px; }a { color: #0e7490; text-decoration: none; }a:hover { text-decoration: underline; }.form-error { color: #b45309; font-size: 13px; }
.table-cover { width: 104px; height: 59px; border-radius: 6px; }.cover-hint { font-size: 12px; color: #94a3b8; }.cover-editor { display: flex; align-items: center; gap: 16px; width: 100%; }.cover-preview { flex: 0 0 180px; aspect-ratio: 16 / 9; border-radius: 8px; overflow: hidden; background: #f1f5f9; display: grid; place-items: center; color: #94a3b8; font-size: 12px; }.cover-preview img { width: 100%; height: 100%; object-fit: cover; }.cover-controls { min-width: 0; }.cover-controls p { margin: 8px 0 0; font-size: 12px; color: #64748b; line-height: 1.7; }.cover-file-input { display: none; }.cover-url { margin-top: 12px; }
@media(max-width: 480px) { .cover-editor { align-items: flex-start; flex-direction: column; gap: 10px; }.cover-preview { flex-basis: auto; width: 180px; } }
@media(max-width: 760px) { .tip-management { padding: 16px; }header { align-items: flex-start; flex-direction: column; }.url-input { flex-wrap: wrap; } }
</style>
