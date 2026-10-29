const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
const source = fs.readFileSync('frontend/src/constants/textbooks.ts', 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const sandbox = { exports: {} }; vm.runInNewContext(output, sandbox);
const { stagesForSubject, compareTextbooks } = sandbox.exports;
for (const subject of ['语文', '数学', '英语']) assert.equal(stagesForSubject(subject).join(','), '小学,初中,高中');
for (const subject of ['物理', '化学', '生物', '地理', '历史']) assert.equal(stagesForSubject(subject).join(','), '初中,高中');
assert.equal(stagesForSubject('政治').join(','), '高中');
assert.equal(stagesForSubject('道德与法治').join(','), '初中');
const sorted = titles => titles.map(title => ({ title })).sort(compareTextbooks).map(book => book.title);
assert.deepEqual(sorted(['九年级下册', '七年级下册', '八年级上册', '七年级上册', '九年级上册', '八年级下册']), ['七年级上册', '七年级下册', '八年级上册', '八年级下册', '九年级上册', '九年级下册']);
assert.deepEqual(sorted(['选择性必修三', '必修二', '必修一', '选择性必修二', '选择性必修一']), ['必修一', '必修二', '选择性必修一', '选择性必修二', '选择性必修三']);
assert.deepEqual(sorted(['选择性必修下册', '必修下', '选择性必修上册', '必修上', '选择性必修中册']), ['必修上', '必修下', '选择性必修上册', '选择性必修中册', '选择性必修下册']);
assert.deepEqual(sorted(['第十一册', '第十册', '第九册', '第二册']), ['第二册', '第九册', '第十册', '第十一册']);
console.log('教材学段和版本排序检查通过');

const chapterSource = fs.readFileSync('frontend/src/constants/textbookChapters.ts', 'utf8');
const chapterOutput = ts.transpileModule(chapterSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const chapterSandbox = { exports: {} }; vm.runInNewContext(chapterOutput, chapterSandbox);
const { groupTextbookChapters, isUnitHeading } = chapterSandbox.exports;
const mergedEnglish = [{ id: 901, title: 'Section A: Why do you like animals?', parent_title: 'UNIT 1 Animal Friends', unit_title: 'UNIT 1 Animal Friends', is_unit: false, directory_layout: 'sections' },
  { id: 902, title: 'Section B: How are animals part of our lives?', parent_title: 'UNIT 1 Animal Friends', unit_title: 'UNIT 1 Animal Friends', is_unit: false, directory_layout: 'sections' }];
const mergedGroups = groupTextbookChapters(mergedEnglish);
assert.equal(mergedGroups.length, 1);
const mergedSections = chapterSandbox.exports.sectionEnglishChapters(mergedGroups[0].chapters);
assert.equal(mergedSections.length, 1);
assert.equal(mergedSections[0].title, '');
assert.equal(mergedSections[0].chapters.map(row => row.id).join(','), '901,902');
const row = (id, title, unit_title = '', parent_title = '') => ({ id, title, unit_title, parent_title });
const grouped = groupTextbookChapters([
  row(1, '第一单元·识字', '第一单元·识字'), row(2, '1. 天地人', '第一单元·识字'),
  row(3, '2. 金木水火土', '第一单元·识字'), row(4, '第二单元·汉语拼音', '第二单元·汉语拼音'),
  row(5, '1. a o e', '第二单元·汉语拼音'), row(6, '识字表'),
]);
assert.equal(grouped.map(group => group.title).join(','), '第一单元·识字,第二单元·汉语拼音,');
assert.equal(grouped.flatMap(group => group.chapters).map(chapter => chapter.id).join(','), '2,3,5,6');
assert.equal(isUnitHeading(row(7, 'Unit 1. Family · Lesson 1. Knowing My Family')), false);
assert.equal(isUnitHeading({ ...row(8, '第一单元'), is_unit: false }), false);
const legacy = groupTextbookChapters([{id:9,title:'牛顿第一定律',parent_title:'第四章 运动和力的关系'}]);
assert.equal(legacy[0].title, '第四章 运动和力的关系');
assert.equal(legacy[0].chapters[0].id, 9);
console.log('单元完整标题、章节分组和单元不可选择检查通过');
