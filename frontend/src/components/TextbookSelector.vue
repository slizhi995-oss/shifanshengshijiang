<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { textbookApi, type Textbook, type Chapter } from '@/api/textbooks'
import { compareTextbooks } from '@/constants/textbooks'
import { sectionEnglishChapters } from '@/constants/textbookChapters'
import { isPrimaryChineseSupplement } from '@/constants/textbookChapters'
import { formatMathChapterTitle, formatPrimaryMathChapterTitle, getMathNestedChapterIds, getNestedChapterIds, groupTextbookChapters, isRemovedMathChapter, isAppendix, isPhysicsAppendix, isHistorySupplement, isGeographySupplement, isHighschoolPhysicsSupplement, isJuniorChemistrySupplement, isHighschoolChemistrySupplement, isUnitHeading, sectionMathChapters, sectionTextbookChapters, sectionHistoryChapters, sectionGeographyChapters, sectionBiologyChapters } from '@/constants/textbookChapters'

const props = defineProps<{ modelValue?: number; bookId?: number; subject: string; grade: string; topic: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: number | undefined): void
  (e: 'update:bookId', value: number | undefined): void
  (e: 'update:topic', value: string): void
}>()
const books = ref<Textbook[]>([])
const chapters = ref<Chapter[]>([])
const booksLoading = ref(false)
const chaptersLoading = ref(false)
const booksFailed = ref(false)
const chaptersFailed = ref(false)
let bookRevision = 0
let chapterRevision = 0
const book = computed(() => books.value.find(item => item.id === props.bookId))
const mathDirectory = computed(() => book.value?.subject === '数学')
const physicsDirectory = computed(() => book.value?.subject === '物理')
const historyDirectory = computed(() => book.value?.subject === '历史')
const geographyDirectory = computed(() => book.value?.subject === '地理')
const juniorChemistryDirectory = computed(() => book.value?.subject === '化学' && book.value.grade.startsWith('初中'))
const highschoolChemistryDirectory = computed(() => book.value?.subject === '化学' && book.value.grade.startsWith('高中'))
const juniorBiologyDirectory = computed(() => book.value?.subject === '生物' && book.value.grade.startsWith('初中'))
const highschoolBiologyDirectory = computed(() => book.value?.subject === '生物' && book.value.grade.startsWith('高中'))
const highschoolEnglishDirectory = computed(() => book.value?.subject === '英语' && book.value.grade.startsWith('高中'))
const juniorEnglishDirectory = computed(() => book.value?.subject === '英语' && book.value.grade.startsWith('初中')
  && chapters.value.some(chapter => chapter.directory_layout === 'sections' || /^Section [AB]:/u.test(chapter.section_title || '')))
const primaryEnglishDirectory = computed(() => book.value?.subject === '英语' && book.value.grade.startsWith('小学')
  && chapters.value.some(chapter => chapter.is_unit === false && !!chapter.unit_title && /^Lesson\s+\d+$/i.test(chapter.display_title || chapter.title)))
const flatPrimaryEnglishDirectory = computed(() => book.value?.subject === '英语' && book.value.grade.startsWith('小学')
  && chapters.value.some(chapter => chapter.directory_layout === 'flat'))
const englishDirectory = computed(() => highschoolEnglishDirectory.value || juniorEnglishDirectory.value || primaryEnglishDirectory.value || flatPrimaryEnglishDirectory.value)
const biologyDirectory = computed(() => juniorBiologyDirectory.value || highschoolBiologyDirectory.value)
const primaryMathDirectory = computed(() => mathDirectory.value && book.value?.grade.startsWith('小学'))
const primaryChineseDirectory = computed(() => book.value?.subject === '语文' && book.value.grade.startsWith('小学'))
const politicsRequiredOneDirectory = computed(() => book.value?.subject === '政治' && book.value.grade.startsWith('高中') && book.value.title === '必修一')
const plainChapterGroup = (title: string) => primaryMathDirectory.value || flatPrimaryEnglishDirectory.value || ((primaryChineseDirectory.value || physicsDirectory.value || historyDirectory.value || geographyDirectory.value || juniorChemistryDirectory.value || highschoolChemistryDirectory.value || biologyDirectory.value || politicsRequiredOneDirectory.value) && !title)
const inlineMathColumns = computed(() => mathDirectory.value && !primaryMathDirectory.value)
const sharedLessonNumbers = computed(() => book.value?.subject === '语文' && book.value.grade.startsWith('高中'))
const chapterGroups = computed(() => {
  if (primaryMathDirectory.value || flatPrimaryEnglishDirectory.value) {
    const rows = chapters.value.map(chapter => ({ ...chapter, title: chapter.display_title || chapter.title }))
    return [{ title: '', chapters: rows, sections: [{ title: '', chapters: rows }] }]
  }
  const rows = mathDirectory.value || physicsDirectory.value || highschoolChemistryDirectory.value || biologyDirectory.value || geographyDirectory.value || englishDirectory.value
    ? chapters.value.map(chapter => ({ ...chapter, title: chapter.display_title || chapter.title })) : chapters.value
  return groupTextbookChapters(rows, sharedLessonNumbers.value).map(group => ({
    ...group, sections: englishDirectory.value ? sectionEnglishChapters(group.chapters)
      : mathDirectory.value ? sectionMathChapters(group.chapters, inlineMathColumns.value)
      : biologyDirectory.value ? sectionBiologyChapters(group.chapters)
      : historyDirectory.value ? sectionHistoryChapters(group.chapters, book.value?.grade.startsWith('高中'))
      : geographyDirectory.value ? sectionGeographyChapters(group.chapters, book.value?.grade.startsWith('初中'), book.value?.grade.startsWith('高中'))
      : sectionTextbookChapters(group.chapters, book.value?.subject === '语文' && book.value.grade.startsWith('初中')),
  }))
})
const nestedChapterIds = computed(() => new Set(chapterGroups.value.flatMap(
  group => englishDirectory.value ? []
    : physicsDirectory.value ? group.chapters.filter(chapter => chapter.is_nested).map(chapter => chapter.id)
    : mathDirectory.value ? [...getMathNestedChapterIds(group.chapters, inlineMathColumns.value)]
    : group.sections.flatMap(section => [...getNestedChapterIds(section.chapters, sharedLessonNumbers.value)]),
)))
const sectionDepth = (groupTitle: string) => plainChapterGroup(groupTitle) ? 0 : 1
function chapterDepth(groupTitle: string, sectionTitle: string, chapter: Chapter) {
  const grouped = !plainChapterGroup(groupTitle)
  // Physics marks the direct children of a chapter as nested already.
  const nested = nestedChapterIds.value.has(chapter.id) && !(physicsDirectory.value && grouped)
  return Number(grouped) + Number(!!sectionTitle) + Number(nested)
}
const selectableChapters = computed(() => biologyDirectory.value
  ? chapterGroups.value.flatMap(group => group.sections.flatMap(section => section.chapters))
  : chapters.value.filter(item => !isUnitHeading(item)))
const selected = computed(() => selectableChapters.value.find(item => item.id === props.modelValue))
const bookTitle = (item: Textbook) => item.display_title || item.title
const chapterTitle = (title: string) => {
  if (primaryChineseDirectory.value) return title.replace(
    /^([\s*＊◎○●◆◇]*\d+(?:[.．]\d+)*[*＊]*)[ \t\u3000]+(?=\S)/u, '$1\u3000\u3000',
  )
  if (flatPrimaryEnglishDirectory.value) return title
  if (/^实验活动/u.test(title.trim())) return title.trim().replace(/^(实验活动\s*\d*)\s*(?=\S)/u,
    (_match, prefix: string) => prefix.replace(/\s+/g, '') + '  ')
  if (primaryMathDirectory.value) {
    if (book.value?.title === '四年级上册' && /^1\s*亿有多大$/u.test(title)) return `☘  ${title}`
    return formatPrimaryMathChapterTitle(title)
  }
  if (mathDirectory.value) return formatMathChapterTitle(title, inlineMathColumns.value)
  if (highschoolChemistryDirectory.value) return title.replace(/\s+/g, ' ').trim()
  if (biologyDirectory.value) return title.replace(/\s+/g, ' ').trim()
  if (geographyDirectory.value) return (book.value?.grade.startsWith('初中')
    ? title.replace(/^【?\s*跨学科主题学习\s*】?\s*/u, '【跨学科主题学习】 ') : title).replace(/\s+/g, ' ').trim()
  if (physicsDirectory.value) return title
  const label = title.replace(
    /^([\s*＊◎○●◆◇]*(?:(?:(?:Starter\s+)?(?:Unit|Module|Lesson|Section|Chapter|Topic)|课题|实验活动|跨学科实践活动|跨学科实践|活动|专题|单元)\s*)?(?:\d+(?:[.．]\d+)*|[一二三四五六七八九十百零〇两]+)[*＊]*)([ \t]+)(?=\S)/i,
    '$1$2 ',
  )
  return sharedLessonNumbers.value ? label.replace(/\s*\/\s*/g, ' / ') : label
}
function chapterRowParts(title: string) {
  const label = chapterTitle(title)
  const match = sharedLessonNumbers.value ? label.match(/^\s*(\d+(?:[.．]\d+)*[*＊]*)[ \t]+(.+)$/u) : null
  return { number: match?.[1] || '', title: match?.[2] || label }
}

watch(selected, chapter => {
  if (chapter && !props.topic.trim()) emit('update:topic', chapter.title)
})

async function loadBooks() {
  const revision = ++bookRevision
  ++chapterRevision
  books.value = []; chapters.value = []; chaptersLoading.value = false
  booksFailed.value = false; booksLoading.value = false
  if (!props.subject || !props.grade) return
  booksLoading.value = true
  try {
    const result = await textbookApi.books({ subject: props.subject, stage: props.grade, catalog_only: true })
    if (revision !== bookRevision) return
    books.value = result.data.filter(item => item.is_published).sort(compareTextbooks)
    if (props.bookId && !books.value.some(item => item.id === props.bookId)) {
      emit('update:bookId', undefined); emit('update:modelValue', undefined)
    } else if (!props.bookId && props.modelValue) {
      const chapter = (await textbookApi.chapter(props.modelValue)).data
      if (revision === bookRevision && books.value.some(item => item.id === chapter.book_id)) emit('update:bookId', chapter.book_id)
      else if (revision === bookRevision) emit('update:modelValue', undefined)
    }
  } catch {
    if (revision === bookRevision) {
      booksFailed.value = true
      emit('update:bookId', undefined); emit('update:modelValue', undefined)
    }
  } finally {
    if (revision === bookRevision) booksLoading.value = false
  }
}

watch(() => [props.subject, props.grade], (value, previous) => {
  if (previous?.some(Boolean) && value.some((item, i) => item !== previous[i])) {
    if (selected.value && props.topic === selected.value.title) emit('update:topic', '')
    emit('update:modelValue', undefined); emit('update:bookId', undefined)
  }
  loadBooks()
}, { immediate: true })

async function loadChapters() {
  const revision = ++chapterRevision
  chapters.value = []; chaptersFailed.value = false; chaptersLoading.value = false
  if (!book.value) return
  chaptersLoading.value = true
  try {
    const result = await textbookApi.chapters(book.value.id)
    if (revision !== chapterRevision) return
    chapters.value = result.data.filter(item => item.is_published
      && !(mathDirectory.value && isRemovedMathChapter(item.title))
      && !(primaryChineseDirectory.value && isPrimaryChineseSupplement(item.title))
      && !(book.value?.subject === '物理' && isPhysicsAppendix(item.title))
      && !(physicsDirectory.value && book.value?.grade.startsWith('高中') && isHighschoolPhysicsSupplement(item.title))
      && !(juniorChemistryDirectory.value && isJuniorChemistrySupplement(item.title))
      && !(highschoolBiologyDirectory.value && isAppendix(item.title))
      && !(historyDirectory.value && isHistorySupplement(item.title))
      && !(geographyDirectory.value && isGeographySupplement(item.title, book.value?.grade.startsWith('初中')))
      && !(highschoolChemistryDirectory.value && isHighschoolChemistrySupplement(item.title)))
    if (props.modelValue && !selected.value) emit('update:modelValue', undefined)
  } catch {
    if (revision === chapterRevision) {
      chaptersFailed.value = true; emit('update:modelValue', undefined)
    }
  } finally {
    if (revision === chapterRevision) chaptersLoading.value = false
  }
}
watch(book, loadChapters)

function selectBook(id: number) {
  if (selected.value && props.topic === selected.value.title) emit('update:topic', '')
  emit('update:modelValue', undefined)
  emit('update:bookId', id)
}
function selectChapter(id: number) {
  const chapter = chapters.value.find(item => item.id === id)
  if (!chapter || isUnitHeading(chapter) || !selectableChapters.value.some(item => item.id === id)) return
  if (!props.topic.trim() || props.topic === selected.value?.title) emit('update:topic', chapter.title)
  emit('update:modelValue', id)
}
</script>

<template>
  <div class="textbook-selector">
    <div class="selector-field">
      <label>教材</label>
      <el-select :model-value="book?.id" @update:model-value="selectBook" aria-label="教材" filterable class="w-full"
        :loading="booksLoading" :disabled="!subject || !grade || booksLoading || !books.length"
        :placeholder="!subject || !grade ? '请先选择科目和学段' : booksLoading ? '正在加载教材…' : '选择教材'">
        <el-option v-for="item in books" :key="item.id" :value="item.id" :label="bookTitle(item)" />
      </el-select>
      <p v-if="booksFailed" class="hint" role="status">教材加载失败。<el-button link type="primary" @click="loadBooks">重试</el-button></p>
      <p v-else-if="!booksLoading && subject && grade && !books.length" class="hint" role="status">当前科目和学段暂无教材。</p>
    </div>
    <div class="selector-field">
      <label>章节</label>
      <el-select :model-value="selected?.id" @update:model-value="selectChapter" aria-label="章节" filterable fit-input-width class="w-full" popper-class="textbook-chapter-dropdown" :fallback-placements="['bottom-start', 'top-start']"
        :loading="chaptersLoading" :disabled="!book || chaptersLoading || !selectableChapters.length"
        :placeholder="!book ? '请先选择教材' : chaptersLoading ? '正在加载章节…' : '选择章节'">
        <el-option-group v-for="(group, index) in chapterGroups" :key="index" :label="plainChapterGroup(group.title) ? '' : group.title || '其他章节'" :class="{ 'chapter-directory-group--plain': plainChapterGroup(group.title), 'chapter-directory-group--physics': physicsDirectory, 'chapter-directory-group--chemistry': highschoolChemistryDirectory, 'chapter-directory-group--biology': biologyDirectory, 'chapter-directory-group--highschool-biology': highschoolBiologyDirectory, 'chapter-directory-group--geography': geographyDirectory, 'chapter-directory-group--english': englishDirectory }">
          <template v-for="(section, sectionIndex) in group.sections" :key="sectionIndex">
            <li v-if="section.title" class="chapter-directory-section" :style="{ '--chapter-depth': sectionDepth(group.title) }" role="presentation">{{ section.title }}</li>
            <el-option v-for="chapter in section.chapters" :key="chapter.id" :value="chapter.id" :label="chapterTitle(chapter.title)" :aria-label="mathDirectory ? chapterTitle(chapter.title) : chapter.title" :style="{ '--chapter-depth': chapterDepth(group.title, section.title, chapter) }">
              <span class="chapter-directory-row" :class="{ 'chapter-directory-row--parallel': sharedLessonNumbers }">
                <span v-if="chapterRowParts(chapter.title).number" class="chapter-directory-number">{{ chapterRowParts(chapter.title).number }}</span>
                <span class="chapter-directory-title">{{ chapterRowParts(chapter.title).title }}</span>
              </span>
            </el-option>
          </template>
        </el-option-group>
      </el-select>
      <p v-if="chaptersFailed" class="hint" role="status">章节加载失败。<el-button link type="primary" @click="loadChapters">重试</el-button></p>
      <p v-else-if="book && !chaptersLoading && !selectableChapters.length" class="hint" role="status">{{ book.status === 'needs_ocr' ? '此教材需要识别扫描正文，章节暂不可用于生成。' : '此教材章节正在整理，核对发布后即可选择。' }}</p>
    </div>
  </div>
</template>

<style scoped>
.textbook-selector { width: 100%; }
.selector-field + .selector-field { margin-top: 18px; }
.selector-field > label { display: block; margin-bottom: 8px; line-height: 22px; color: #606266; }
.hint { margin: 8px 0 0; color: #64748b; font-size: 13px; line-height: 1.6; }
:global(.textbook-chapter-dropdown) {
  --chapter-base: 20px;
  --chapter-indent: 40px;
  max-width: calc(100vw - 24px);
  border-radius: 10px;
}
:global(.textbook-chapter-dropdown .el-select-dropdown__wrap) { max-height: min(400px, calc(50vh - 32px)); }
:global(.textbook-chapter-dropdown .el-select-group__wrap) { margin: 0; padding: 0; }
:global(.textbook-chapter-dropdown .el-select-group__wrap:not(:last-of-type)) { margin-bottom: 8px; padding-bottom: 8px; }
:global(.textbook-chapter-dropdown .el-select-group__wrap:not(:last-of-type)::after) { left: var(--chapter-base); right: var(--chapter-base); bottom: 0; background: #eef2f7; }
:global(.textbook-chapter-dropdown .el-select-group__title) {
  height: auto;
  min-height: 0;
  padding: 10px var(--chapter-base) 6px;
  color: #475569;
  font-size: 14px;
  font-weight: 500;
  line-height: 24px;
  white-space: normal;
  overflow-wrap: anywhere;
  cursor: default;
}
:global(.textbook-chapter-dropdown .chapter-directory-group--plain > .el-select-group__title) { display: none; }
:global(.textbook-chapter-dropdown .chapter-directory-group--english > .el-select-group__title) { font-weight: 400; }
:global(.textbook-chapter-dropdown .chapter-directory-section),
:global(.textbook-chapter-dropdown .el-select-group .el-select-dropdown__item) {
  box-sizing: border-box;
  height: auto;
  padding: 9px var(--chapter-base);
  padding-inline-start: calc(var(--chapter-base) + var(--chapter-depth, 0) * var(--chapter-indent));
  color: #334155;
  font-size: 14px;
  font-weight: 400;
  line-height: 24px;
  white-space: normal;
  overflow-wrap: anywhere;
}
:global(.textbook-chapter-dropdown .chapter-directory-section) { padding-top: 8px; padding-bottom: 6px; color: #64748b; list-style: none; }
:global(.textbook-chapter-dropdown .el-select-dropdown__item) { min-height: 42px; transition: background-color 0.15s ease; }
:global(.textbook-chapter-dropdown .el-select-dropdown__item.is-hovering) { background-color: #f4f7fc; }
:global(.textbook-chapter-dropdown .el-select-dropdown__item.is-selected) { color: #2563eb; background-color: #eff6ff; font-weight: 400; box-shadow: inset 2px 0 #3b82f6; }
.chapter-directory-row { display: flex; align-items: baseline; min-width: 0; gap: 0; }
.chapter-directory-number { flex: 0 0 var(--chapter-indent); font-variant-numeric: tabular-nums; }
.chapter-directory-title { flex: 1; min-width: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  :global(.textbook-chapter-dropdown) { --chapter-base: 16px; --chapter-indent: 24px; }
}
</style>
