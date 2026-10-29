export const subjectOptions = ['语文', '数学', '英语', '物理', '政治', '道德与法治', '化学', '生物', '地理', '历史']
export const stageOptions = ['小学', '初中', '高中']

export function stagesForSubject(subject: string) {
  if (!subjectOptions.includes(subject)) return []
  if (subject === '道德与法治') return ['初中']
  if (subject === '政治') return ['高中']
  return ['语文', '数学', '英语'].includes(subject) ? [...stageOptions] : ['初中', '高中']
}

function textbookNumbers(title: string) {
  const digits: Record<string, number> = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 }
  return title.replace(/[零〇一二两三四五六七八九十百]+/g, text => {
    let total = 0, digit = 0
    for (const char of text) {
      if (char === '十' || char === '百') { total += (digit || 1) * (char === '十' ? 10 : 100); digit = 0 }
      else digit = digits[char] ?? 0
    }
    return String(total + digit)
  })
}

export function compareTextbooks(a: { display_title?: string; title: string }, b: { display_title?: string; title: string }) {
  const key = (book: typeof a) => {
    const title = textbookNumbers(book.display_title || book.title)
    const category = /选择性必修|选修/.test(title) ? 2 : /必修/.test(title) ? 1 : 0
    const number = Number(title.match(/\d+/)?.[0] || 0)
    const volume = /上/.test(title) ? 0 : /中册|[（(]中[）)]/.test(title) ? 1 : /下/.test(title) ? 2 : 0
    return { title, category, number, volume }
  }
  const left = key(a), right = key(b)
  return left.category - right.category || left.number - right.number || left.volume - right.volume || left.title.localeCompare(right.title, 'zh-CN', { numeric: true })
}

export function schoolStage(grade: string) {
  return stageOptions.find(stage => grade?.startsWith(stage)) || ''
}
