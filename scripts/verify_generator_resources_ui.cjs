// Isolated browser fixtures: no production data, paid searches, or external videos.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const JSZip = require(require.resolve('jszip', { paths: [path.resolve('frontend')] }));
const base = process.env.VIDEO_UI_URL || 'http://127.0.0.1:5173';
const output = path.resolve('backend/outputs/generator-resource-ui');
fs.mkdirSync(output, { recursive: true });
const form = { subject: '英语', grade: '小学', topic: 'Unit 1 My classroom · Lesson 3', duration: 15,
  key_point: '', difficulty: '', use_textbook: true, textbook_id: 1, textbook_chapter_id: 1 };
const lesson = { id: 1, title: form.topic, subject: '英语', grade: '小学', created_at: '2026-10-23T10:00:00',
  source: { book_title: '三年级下册', chapter_title: 'Lesson 3', printed_pages: '8-9' }, content: '# 教案预览验收', audio_count: 1, match_status: 'matched' };
const audio = { resource_id: 'audio-1', title: 'Lesson 3 · 听力练习', unit_title: 'Unit 1 My classroom',
  stage: '小学', series: '人教精通', volume: '三年级下册', audio_kind: '听力练习', available: true,
  reason: '对应教材页的配套音频', printed_page: 8, textbook_excerpt: 'Listen and say.' };
const video = { id: 'candidate-1', bvid: 'BV1B7411m7LV', page: 1, title: '课堂导入素材（界面验收）',
  section: '导入', purpose: '引入课堂主题', url: 'https://www.bilibili.com/video/BV1B7411m7LV/', cover_url: '' };
const names = { 2: '空结果教案', 3: '仅视频教案', 4: '已保存视频教案', 5: '后台失败教案', 6: '延迟结果教案', 7: '站外无效结果教案' };
const records = Object.entries(names).map(([id, title]) => ({ id: `fixture-${id}`, title,
  createdAt: Number(id), form: { ...form, topic: title }, templateType: 'default', content: '# 教案预览验收',
  resourceLessonId: Number(id) === 3 ? undefined : Number(id), lessonId: Number(id) === 3 ? 103 : undefined,
  documentId: 'fixture-document' }));

async function wordFixture() {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
  zip.file('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
  zip.file('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>教案预览验收</w:t></w:r></w:p><w:p><w:r><w:t>一、教学目标：学习课堂用语。</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:bottom="1440" w:left="1440" w:right="1440"/></w:sectPr></w:body></w:document>');
  return zip.generateAsync({ type: 'nodebuffer' });
}

(async () => {
  const document = await wordFixture();
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const report = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1050 } });
      await context.addInitScript(({ form, records }) => {
        localStorage.setItem('token', 'generator-resource-fixture');
        localStorage.setItem('user', JSON.stringify({ id: 1, name: '界面验收', role: 'student', user_code: 'fixture', is_default_password: false }));
        if (!localStorage.getItem('ai_generator_history')) localStorage.setItem('ai_generator_history', JSON.stringify(records));
        if (!localStorage.getItem('ai_generator_state')) localStorage.setItem('ai_generator_state', JSON.stringify({ form, templateType: 'default', content: '', currentRecordId: null }));
      }, { form, records });
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let searches = 0, polls = 0, generated = 0, delayedGets = 0, tipRequests = 0;
      let releaseDelayed;
      const delayed = new Promise(resolve => { releaseDelayed = resolve; });
      await page.route('**/api/v1/**', async route => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname.replace('/api/v1', '');
        let data = [];
        if (pathname === '/ai/status') data = { enabled: true };
        else if (pathname === '/ai/generate') {
          generated++;
          data = { success: true, data: { content: '# 教案预览验收', resource_lesson_id: 1, lesson_id: 101, document_id: 'fixture-document' } };
        } else if (pathname === '/ai/lesson-documents') data = { success: true, data: { document_id: 'fixture-document', document_filename: '教案.docx' } };
        else if (pathname.startsWith('/ai/lesson-documents/')) return route.fulfill({ contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: document });
        else if (pathname === '/textbooks') data = { success: true, data: [{ id: 1, title: '三年级下册', subject: '英语', grade: '小学', is_published: true, status: 'ready' }] };
        else if (pathname === '/textbooks/1/chapters') data = { success: true, data: [{ id: 1, book_id: 1, title: 'Lesson 3', parent_title: 'Unit 1 My classroom', is_published: true }] };
        else if (pathname.startsWith('/resources/audio-lessons/by-textbook/')) data = { ...lesson, id: 3, textbook_lesson_id: 103 };
        else if (/\/audio\/audio-1\/file$/.test(pathname)) {
          const wav = Buffer.alloc(1644); wav.write('RIFF'); wav.writeUInt32LE(1636, 4); wav.write('WAVEfmt ', 8); wav.writeUInt32LE(16, 16);
          wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(1600, 40);
          return route.fulfill({ contentType: 'audio/wav', body: wav });
        } else if (pathname.endsWith('/metadata')) data = { availability: 'available', title: '', cover_url: '' };
        else if (/\/audio-lessons\/\d+\/videos(?:\/search)?$/.test(pathname)) {
          const id = Number(pathname.match(/audio-lessons\/(\d+)/)[1]);
          if (id === 5) return route.fulfill({ status: 503, json: { detail: 'isolated background failure' } });
          if (id === 6) { delayedGets++; await delayed; }
          let status = 'ready', items = [], selected = [];
          if (id === 1) {
            if (pathname.endsWith('/search')) { searches++; status = 'queued'; }
            else if (!searches) status = 'idle';
            else { polls++; status = polls < 2 ? 'searching' : 'ready'; }
            if (status === 'ready') items = [video];
          } else if (id === 3 || id === 6) items = [video];
          else if (id === 4) selected = [{ ...video, id: 8, source: 'manual' }];
          else if (id === 7) items = [{ ...video, url: 'https://example.org/video/1', bvid: '' }];
          else status = 'no_results';
          data = { lesson_id: id, configured: true, status, items, selected, query: '', needs: [],
            stale: false, next_search_at: null, searched_at: null, message: '', fallback_url: 'https://search.bilibili.com/all' };
        } else if (pathname === '/resources/audio-lessons') data = { items: [{ ...lesson, id: 20, title: '服务端历史教案' }], total: 1 };
        else if (/\/audio-lessons\/\d+(?:\/rematch)?$/.test(pathname)) {
          const id = Number(pathname.match(/audio-lessons\/(\d+)/)[1]);
          if (id === 5) return route.fulfill({ status: 503, json: { detail: 'isolated background failure' } });
          data = { ...lesson, id, title: id === 20 ? '服务端历史教案' : names[id] || lesson.title, audios: [1, 20].includes(id) ? [audio] : [] };
        } else if (pathname === '/resources/teaching-tips') { tipRequests++; data = { items: [] }; }
        else if (pathname.includes('notices/public')) data = null;
        else if (pathname.includes('unread')) data = { count: 0, unread_count: 0 };
        await route.fulfill({ json: data });
      });

      await page.goto(base + '/student/ai-generator');
      await page.getByRole('button', { name: '生成教案', exact: true }).click();
      const resources = page.getByRole('region', { name: '教案配套资源', exact: true });
      await resources.getByRole('heading', { name: audio.title, exact: true }).waitFor();
      await page.getByRole('region', { name: '教案预览', exact: true }).getByText('教案预览验收', { exact: true }).waitFor();
      await resources.getByRole('heading', { name: video.title, exact: true }).waitFor();
      assert.equal(generated, 1); assert.equal(searches, 1); assert.ok(polls >= 2);
      assert.equal(tipRequests, 0);
      await page.locator('.word-pages').hover();
      await page.mouse.wheel(0, 500);
      await page.waitForTimeout(300);
      assert.ok(await page.locator('.result-body').evaluate(element => element.scrollTop > 0), 'wheel over the Word preview must scroll the result page');
      await page.getByRole('button', { name: '配套资源', exact: true }).click();
      await resources.getByRole('button', { name: '试听音频', exact: true }).click();
      await resources.locator('audio').waitFor();
      assert.match(await resources.locator('audio').getAttribute('src'), /^blob:/);
      await resources.getByRole('button', { name: '关闭', exact: true }).click();
      const downloadPromise = page.waitForEvent('download');
      await resources.getByRole('button', { name: '下载', exact: true }).click();
      assert.match((await downloadPromise).suggestedFilename(), /\.mp3$/);
      assert.equal(await resources.locator('.video-title').getAttribute('href'), video.url);
      await page.screenshot({ path: path.join(output, `matched-${width}.png`), fullPage: true });

      async function select(title) { await page.locator('.history-item').filter({ hasText: title }).click(); }
      for (const id of [2, 5, 7]) {
        const loaded = page.waitForResponse(response => response.url().endsWith(`/audio-lessons/${id}/videos`));
        await select(names[id]);
        await loaded;
        await resources.waitFor({ state: 'hidden' });
        assert.equal(await page.getByRole('button', { name: '配套资源', exact: true }).count(), 0);
        assert.equal(await page.locator('.el-message--error').count(), 0);
      }
      for (const id of [3, 4]) {
        await select(names[id]);
        await resources.getByRole('heading', { name: video.title, exact: true }).waitFor();
        assert.equal(await resources.locator('.audio-card').count(), 0);
        assert.equal(await page.getByRole('region', { name: '试讲技巧视频' }).count(), 0);
      }
      await select(names[6]);
      await page.waitForFunction(() => document.querySelector('.result-toolbar .title')?.textContent === '延迟结果教案');
      await select(names[2]);
      releaseDelayed();
      await page.waitForTimeout(2200); // One polling interval verifies cleanup after the old response.
      await resources.waitFor({ state: 'hidden' });
      assert.equal(delayedGets, 1);
      const reloaded = page.waitForResponse(response => response.url().endsWith('/audio-lessons/2/videos'));
      await page.reload();
      await reloaded;
      await resources.waitFor({ state: 'hidden' });
      assert.equal(generated, 1, 'history must not regenerate a lesson');

      await page.goto(base + '/student/resources');
      await page.getByRole('region', { name: '试讲技巧视频' }).waitFor();
      assert.equal(await page.locator('.lesson-matched-resources').count(), 0);
      await page.getByRole('button', { name: '历史记录', exact: true }).click();
      await page.getByRole('button', { name: '查看教案：服务端历史教案', exact: true }).click();
      await page.waitForURL('**/student/ai-generator?resourceLesson=20');
      await resources.getByRole('heading', { name: audio.title, exact: true }).waitFor();
      assert.equal(await page.locator('.history-item').filter({ hasText: '服务端历史教案' }).count(), 1);
      await page.goto(base + '/student/resources?lesson=103');
      await page.waitForURL('**/student/ai-generator?lesson=103');
      await resources.getByRole('heading', { name: video.title, exact: true }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `page overflow at ${width}`);
      assert.deepEqual(errors, []);
      report.push(`${width}px: generation, polling, audio, empty/error hiding, legacy history, stale-response cleanup passed`);
      console.log(report.at(-1));
      await context.close();
    }
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
