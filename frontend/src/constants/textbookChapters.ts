import type { Chapter } from '@/api/textbooks'

const unitHeading = /^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*单\s*元|(?:Starter\s+)?(?:Unit|Module)\s*\d+\b)/i
const directorySection = /^(阅读|写作|口语交际|综合性学习|名著导读)(?:\s+|[：:]\s*)(.+)$/u
const mathDirectoryColumn = /^((?:文献阅读与数学写作|阅读与思考|探究与发现|信息技术应用|图说数学史|观察与猜想|实验与探究|综合与实践|数学探究|数学建模)[*＊]?)[\s:：]*(.+)$/u

export const isRemovedMathChapter = (title: string) => /^(?:小结|数学活动|复习(?:参考)?题[\s\d一二三四五六七八九十百零〇]*|部分中英文词汇索引)[\s.·…]*$/u.test(title.normalize('NFKC').trim())
export const isPrimaryChineseSupplement = (title: string) => /^(?:其他章节|识字表|写字表|词语表|笔画名称表|常用偏旁名称表)[.·…]*$/u.test(title.normalize('NFKC').trim()
  .replace(/^[*◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?/u, '').replace(/\s+/gu, ''))
export const isAppendix = (title: string) => /^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?附\s*录/u.test(title.normalize('NFKC').trim())
export const isPhysicsAppendix = isAppendix
export const isGeographySupplement = (title: string, junior = false) => /^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?(?:附\s*录|其\s*他\s*章\s*节|后\s*记)/u.test(title.normalize('NFKC').trim()) || title.trim() === '广东教育出版社有限公司'
  || (junior && /^[【\s]*主\s*题\s*活\s*动/u.test(title.normalize('NFKC').trim()))
export const isHistorySupplement = (title: string) => /^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?(?:附\s*录|其\s*他\s*章\s*节|(?:历\s*史\s*)?译\s*名\s*对\s*照\s*表\s*\(\s*下\s*\))/u.test(title.normalize('NFKC').trim())
export const isHighschoolPhysicsSupplement = (title: string) => /^(?:致同学|走进物理课堂之前|序言|前言|引言|编者的话|使用说明|目录|课题研究|学生实验|索引|学习资源|参考文献|参考资料|后记)/u.test(title.normalize('NFKC').trim().replace(/^[*＊\s]*(?:\d+[、.]?\s+)?/u, ''))
export const isJuniorChemistrySupplement = (title: string) => /^(?:其他章节|绪\s*论|整\s*理\s*与\s*(?:提\s*高|提\s*升)|复\s*习\s*与\s*提\s*高|附\s*录)/u.test(title.normalize('NFKC').trim()
  .replace(/^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?/u, '')
  .replace(/^第\s*[\d一二三四五六七八九十百零〇]+\s*(?:单\s*元|章)\s*/u, ''))
export const isHighschoolChemistrySupplement = (title: string) => !/^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*[章节]|实验活动)/u.test(title.normalize('NFKC').trim()
  .replace(/^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?/u, ''))

function directoryTitleParts(title: string) {
  const text = title.trim()
  const unit = text.match(unitHeading)
  const afterUnit = unit ? text.slice(unit[0].length).trim() : ''
  const embeddedUnit = unit && directorySection.test(afterUnit) ? unit[0] : ''
  const section = (embeddedUnit ? afterUnit : text).match(directorySection)
  return { unit: embeddedUnit, section: section?.[1] || '', title: section?.[2] || text }
}

export const isUnitHeading = (chapter: Chapter) => {
  // A scanned row can contain both the unit heading and its first real lesson.
  if (directoryTitleParts(chapter.title).unit) return false
  return chapter.is_unit ?? (
    unitHeading.test(chapter.title.trim()) && !/^(?:Starter\s+)?(?:Unit|Module).*\s+[·|]\s+/i.test(chapter.title)
  )
}

export function sectionTextbookChapters(chapters: Chapter[], withSections = true) {
  if (!withSections) return [{ title: '', chapters }]
  const sections: { title: string; chapters: Chapter[] }[] = []
  // A few directories omit “阅读” from the first row but retain the writing
  // boundary. Their preceding lessons still belong to the reading section.
  const hasReadingBlock = chapters.some(chapter => directoryTitleParts(chapter.title).section === '写作')
    && !chapters.some(chapter => /^任务[一二三四五六七八九十\d]/u.test(chapter.title.trim()))
  let reading = hasReadingBlock
  for (const chapter of chapters) {
    const parts = directoryTitleParts(chapter.title)
    const title = parts.section || (reading ? '阅读' : '')
    if (parts.section) reading = parts.section === '阅读'
    let section = sections[sections.length - 1]
    if (!section || section.title !== title || (parts.section && parts.section !== '阅读')) {
      section = { title, chapters: [] }
      sections.push(section)
    }
    section.chapters.push(parts.section ? { ...chapter, title: parts.title, is_unit: false } : chapter)
  }
  return sections
}

export function sectionEnglishChapters(chapters: Chapter[]) {
  // A merged English section is the selectable row itself, one level below Unit.
  if (chapters.some(chapter => chapter.directory_layout === 'sections')) return [{ title: '', chapters }]
  const sections: { title: string; chapters: Chapter[] }[] = []
  for (const chapter of chapters) {
    const title = chapter.section_title || ''
    let section = sections[sections.length - 1]
    if (!section || section.title !== title) {
      section = { title, chapters: [] }
      sections.push(section)
    }
    section.chapters.push(chapter)
  }
  return sections
}

// These unnumbered topics are labelled “活动课” in the five printed volumes.
const highschoolHistoryActivities = new Set([
  '家国情怀与统一多民族国家的演进',
  '放眼世界,推动构建人类命运共同体',
  '中国历史上的大一统国家治理',
  '信息革命与人类文化共享',
  '技术进步与社会生活的变化',
])

export function sectionHistoryChapters(chapters: Chapter[], highschool = false) {
  const sections: { title: string; chapters: Chapter[] }[] = []
  let inMethods = false
  for (const chapter of chapters) {
    const method = chapter.title.trim().match(/^学史方法[\s：:]*([（(][一二三四五六七八九十]+[）)].*)$/u)
    const continuation: boolean = inMethods && /^[（(][一二三四五六七八九十]+[）)]/u.test(chapter.title.trim())
    inMethods = !!method || continuation
    const activity = highschool && highschoolHistoryActivities.has(chapter.title.normalize('NFKC').trim())
    const title = inMethods ? '学史方法' : activity ? '活动课' : ''
    let section = sections[sections.length - 1]
    if (!section || section.title !== title) {
      section = { title, chapters: [] }
      sections.push(section)
    }
    section.chapters.push(inMethods || activity
      ? { ...chapter, title: method?.[1] || chapter.title.trim(), is_nested: false }
      : chapter)
  }
  return sections
}

export function sectionGeographyChapters(chapters: Chapter[], inlineCrossSubject = false, inlineResearch = false) {
  const sections: { title: string; chapters: Chapter[] }[] = []
  for (const chapter of chapters) {
    const column = chapter.title.trim().match(/^(?:【(跨学科主题学习)】\s*|((?:跨学科主题学习|主题活动|问题研究|活动课)(?:\s*[\d一二三四五六七八九十]+)?)[\s：:]+)(.+)$/u)
    if (column && !(inlineCrossSubject && (column[1] || column[2]).startsWith('跨学科主题学习'))
      && !(inlineResearch && (column[1] || column[2]).trim() === '问题研究')) {
      sections.push({ title: (column[1] || column[2]).trim(), chapters: [{ ...chapter, title: column[3], is_nested: false }] })
      continue
    }
    let section = sections[sections.length - 1]
    if (!section || section.title) {
      section = { title: '', chapters: [] }
      sections.push(section)
    }
    section.chapters.push(chapter)
  }
  return sections
}

export function sectionBiologyChapters(chapters: Chapter[]) {
  const heading = /^第\s*[\d一二三四五六七八九十百零〇]+\s*章/u
  const lesson = /^第\s*[\d一二三四五六七八九十百零〇]+\s*节/u
  const sections: { title: string; chapters: Chapter[] }[] = []
  for (let index = 0; index < chapters.length; index++) {
    const chapter = chapters[index]
    let section = sections[sections.length - 1]
    if (heading.test(chapter.title)) {
      const next = chapters.findIndex((row, position) => position > index && heading.test(row.title))
      const hasLessons = chapters.slice(index + 1, next < 0 ? undefined : next).some(row => lesson.test(row.title))
      section = { title: hasLessons ? chapter.title : '', chapters: [] }
      sections.push(section)
      // A chapter without section headings remains a selectable lesson.
      if (hasLessons) continue
    } else if (/^(?:综合实践项目|附录|学习还将继续)/u.test(chapter.title)) {
      section = { title: '', chapters: [] }
      sections.push(section)
    }
    if (!section) {
      section = { title: '', chapters: [] }
      sections.push(section)
    }
    section.chapters.push(chapter)
  }
  return sections
}

export function formatMathChapterTitle(title: string, inlineColumns = false) {
  let label = title.replace(/\uE012/g, '*').replace(/\uE011/g, '-')
    .replace(/[ \t]+[.·…]+[ \t]*$/u, '')
  if (inlineColumns) label = label.replace(mathDirectoryColumn, '$1  $2')
  // These numbers are part of the topic, not a lesson ordinal.
  if (/^\s*\d+\s+(?:[~～〜至]|以内|以下|以上|亿|万|千|百)/u.test(label)) return label
  return label.replace(/^([*＊]?\s*\d+(?:[.．]\d+)*)(?:[ \t]*([*＊]))?([ \t]+)(?=\S)/u,
    (_match, number: string, star: string | undefined, separator: string) => number + (star || '') + separator + ' ')
}

export function formatPrimaryMathChapterTitle(title: string) {
  const label = title.trim()
  if (/^(?:\d|[一二三四五六七八九十百零〇两]+[\s、.．])/u.test(label)) {
    return formatMathChapterTitle(label.replace(/^([一二三四五六七八九十百零〇两]+)[ \t]+/u, '$1  '))
  }
  const name = label.replace(/^[\p{P}\p{S}\s\uFE0E\uFE0F]+/u, '')
  return `☘  ${name}`
}

export function sectionMathChapters(chapters: Chapter[], inlineColumns = false) {
  if (inlineColumns) return [{ title: '', chapters }]
  const sections: { title: string; chapters: Chapter[] }[] = []
  for (const chapter of chapters) {
    const match = chapter.title.replace(/\uE012/g, '*').match(mathDirectoryColumn)
    const title = match?.[1] || ''
    let section = sections[sections.length - 1]
    // Each occurrence is a separate column at its original directory position.
    if (!section || title || section.title !== title) {
      section = { title, chapters: [] }
      sections.push(section)
    }
    section.chapters.push(match ? { ...chapter, title: match[2].trim() } : chapter)
  }
  return sections
}

export function getMathNestedChapterIds(chapters: Chapter[], indentColumns = false) {
  const number = (title: string) => title.replace(/\uE012/g, '*').match(/^[\s*＊]*(\d+(?:[.．]\d+)+)/u)?.[1].replace(/．/g, '.')
  const numbers = new Set(chapters.map(chapter => number(chapter.title)).filter(Boolean))
  return new Set(chapters.filter(chapter => {
    if (chapter.is_nested !== undefined) return chapter.is_nested
    if (indentColumns && mathDirectoryColumn.test(chapter.title) && !chapter.title.startsWith('综合与实践')) return true
    const ordinal = number(chapter.title)
    return ordinal && ordinal.split('.').length > 2 && numbers.has(ordinal.slice(0, ordinal.lastIndexOf('.')))
  }).map(chapter => chapter.id))
}

export function getNestedChapterIds(chapters: Chapter[], sharedLessonNumbers = false) {
  const numberedLesson = /^[\s*＊]*(?:\d+(?:[.．]\d+)*[*＊]?(?:\s|[、.．])|第\s*[\d一二三四五六七八九十百零〇]+\s*[章节课])/u
  const titleKey = (title: string) => title.replace(/\s+/g, '')
  const nestedIds = new Set(chapters.filter(chapter => chapters.some(parent => {
    if (parent.id === chapter.id || parent.book_id !== chapter.book_id || isUnitHeading(parent)) return false
    if (chapter.parent_title && titleKey(chapter.parent_title) === titleKey(parent.title)) return true
    // Some directories store the unit but omit the lesson/poem relationship.
    // An unnumbered entry within a numbered lesson's pages is a child entry.
    return numberedLesson.test(parent.title) && !numberedLesson.test(chapter.title)
      && !/^\s*(?:[◎○●◆◇]|阅读综合实践)/u.test(chapter.title)
      && parent.start_page <= chapter.start_page && chapter.end_page <= parent.end_page
  })).map(chapter => chapter.id))

  // A collection's stored end page may stop at its first piece. Once a child
  // is identified, keep subsequent pieces at that level until the next lesson,
  // unit, directory column or appendix, rather than relying on that end page.
  let inChildSequence = false
  let inSharedLesson = false
  for (const chapter of chapters) {
    const startsLesson = numberedLesson.test(chapter.title)
    if (isUnitHeading(chapter) || startsLesson
      || /^\s*(?:[◎○●◆◇]|阅读综合实践|单元(?:学习|研习)任务|(?:课外)?古诗词诵读|识字表|写字表|词语表|附录|附表|后记)/u.test(chapter.title)) {
      inChildSequence = false
      inSharedLesson = sharedLessonNumbers && startsLesson
      continue
    }
    // High-school Chinese lessons share one number across several parallel
    // works, even when each work starts on a different page.
    if (nestedIds.has(chapter.id) || inSharedLesson) inChildSequence = true
    if (inChildSequence) nestedIds.add(chapter.id)
  }
  // Reviewed hierarchy overrides inferred page containment and sequences.
  for (const chapter of chapters) {
    if (chapter.is_nested === true) nestedIds.add(chapter.id)
    else if (chapter.is_nested === false) nestedIds.delete(chapter.id)
  }
  return nestedIds
}

export function groupTextbookChapters(chapters: Chapter[], preferSourceUnits = false) {
  const groups: { title: string; chapters: Chapter[] }[] = []
  let currentUnit = ''
  for (const chapter of chapters) {
    const parts = directoryTitleParts(chapter.title)
    const unitTitle = preferSourceUnits || chapter.unit_title === undefined ? undefined
      : directoryTitleParts(chapter.unit_title).unit || chapter.unit_title
    if (isUnitHeading(chapter)) {
      const nextUnit = unitTitle || chapter.title
      // Prefer the actual source headings when all unit rows are available.
      // A repeated bare marker must not erase its full theme heading.
      const sameUnit = currentUnit.match(unitHeading)?.[0] === nextUnit.match(unitHeading)?.[0]
      currentUnit = preferSourceUnits && sameUnit && currentUnit.length > nextUnit.length ? currentUnit : nextUnit
    }
    else if (parts.unit) currentUnit = parts.unit
    const title = unitTitle ?? (parts.unit || chapter.parent_title || currentUnit)
    let group = groups[groups.length - 1]
    if (!group || group.title !== title) {
      group = { title, chapters: [] }
      groups.push(group)
    }
    if (!isUnitHeading(chapter)) group.chapters.push(chapter)
  }
  return groups
}
