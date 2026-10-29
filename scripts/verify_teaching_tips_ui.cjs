// Isolated UI fixtures; no production data or external video requests are used.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.VIDEO_UI_URL || 'http://127.0.0.1:5173';
const output = path.resolve('backend/outputs/teaching-tips-ui');
fs.mkdirSync(output, { recursive: true });
const bvid = 'BV1B7411m7LV';
const tip = { id: 1, bvid, page: 2, url: `https://www.bilibili.com/video/${bvid}/?p=2`, title: '试讲导入技巧（界面测试）',
  category: '导入设计', description: '从问题情境切入课堂，学习如何组织试讲开场。', cover_url: '', sort_order: 0, is_published: true };
const lesson = { id: 1, title: '自由落体运动', subject: '物理', grade: '高一', created_at: '2026-10-22T09:00:00', source: {}, audio_count: 0, match_status: 'unsupported_subject' };
const candidate = { id: 'candidate-1', bvid, page: 1, title: '课堂实验视频', section: '导入', purpose: '观察实验',
  url: `https://www.bilibili.com/video/${bvid}/`, cover_url: '', embed_url: '' };

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const report = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1050 } });
      await context.addInitScript(() => {
        localStorage.setItem('token', 'teaching-tips-fixture');
        if (!localStorage.getItem('user')) localStorage.setItem('user', JSON.stringify({ id: 1, name: '界面验收', role: 'student', user_code: 'fixture', is_default_password: false }));
      });
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let scenario = 'no-lesson';
      let tips = [tip, { ...tip, id: 2, title: '板书设计技巧', category: '板书设计' }];
      let tipsFailed = false;
      await context.route('https://www.bilibili.com/**', route => route.fulfill({ contentType: 'text/html', body: '原站跳转验收' }));
      await page.route('**/api/v1/**', async route => {
        const req = route.request();
        const pathname = new URL(req.url()).pathname.replace('/api/v1', '');
        let data = [];
        if (pathname === '/resources/teaching-tips' || pathname === '/admin/teaching-tips') {
          if (tipsFailed && pathname.startsWith('/resources/')) return route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"fixture failure"}' });
          if (req.method() === 'POST') { tips.push({ ...req.postDataJSON(), id: 3, bvid, page: 2 }); data = tips.at(-1); }
          else data = { items: tips };
        } else if (pathname === '/admin/teaching-tips/metadata') data = { title: '读取的视频标题', cover_url: '', availability: 'available' };
        else if (/\/admin\/teaching-tips\/\d+$/.test(pathname)) {
          const id = Number(pathname.split('/').pop());
          if (req.method() === 'PUT') { tips = tips.map(item => item.id === id ? { ...item, ...req.postDataJSON() } : item); data = tips.find(item => item.id === id); }
          else if (req.method() === 'DELETE') { tips = tips.filter(item => item.id !== id); return route.fulfill({ status: 204 }); }
        } else if (pathname === '/resources/audio-status') data = { ready: 18, book_count: 3 };
        else if (pathname === '/resources/audio-lessons') data = { items: scenario === 'no-lesson' ? [] : [lesson], total: scenario === 'no-lesson' ? 0 : 1 };
        else if (pathname === '/resources/audio-lessons/1') data = { ...lesson, audios: [] };
        else if (pathname.endsWith('/videos')) data = { lesson_id: 1, configured: false, status: scenario === 'busy' ? 'searching' : scenario === 'unconfigured' ? 'not_configured' : scenario === 'no-need' ? 'no_need' : 'no_results',
          items: scenario === 'matched' ? [candidate] : [], selected: scenario === 'saved' ? [{ ...candidate, id: 8 }] : [], needs: [],
          fallback_url: 'https://search.bilibili.com/all', stale: false, next_search_at: null, query: '', message: '' };
        else if (pathname.endsWith('/metadata')) data = { availability: 'unknown', title: '', cover_url: '' };
        else if (pathname.includes('notices/public')) data = null;
        else if (pathname.includes('unread')) data = { count: 0, unread_count: 0 };
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
      });
      for (const name of ['center']) {
        scenario = name;
        await page.goto(base + '/student/resources');
        await page.getByRole('heading', { name: 'AI 资源中心', exact: true }).waitFor();
        const fallback = page.getByRole('region', { name: '试讲技巧视频', exact: true });
        {
          await fallback.getByRole('heading', { name: tip.title, exact: true }).waitFor();
          assert.equal(await fallback.locator('.tip-card').count(), 2);
          await fallback.getByRole('button', { name: '板书设计', exact: true }).click();
          assert.equal(await fallback.locator('.tip-card').count(), 1);
          await fallback.getByRole('button', { name: '全部', exact: true }).click();
          const link = fallback.locator('.tip-card').first();
          assert.equal(await link.getAttribute('href'), tip.url);
          assert.equal(await link.getAttribute('target'), '_blank');
          if (name === 'center') {
            await fallback.scrollIntoViewIfNeeded();
            await page.screenshot({ path: path.join(output, `no-lesson-${width}.png`), fullPage: true });
            const popupPromise = page.waitForEvent('popup');
            await link.click();
            const popup = await popupPromise;
            await popup.waitForURL(tip.url);
            await popup.close();
          }
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `overflow in ${name} at ${width}`);
        report.push(`${width}px: ${name} passed`);
        console.log(report.at(-1));
      }
      scenario = 'no-lesson';
      tips = [];
      await page.goto(base + '/student/resources');
      await page.getByText('精选试讲技巧视频正在整理中，管理员添加并上架后将在这里展示。', { exact: true }).waitFor();
      tipsFailed = true;
      await page.reload();
      await page.getByRole('region', { name: '试讲技巧视频' }).getByRole('alert').waitFor();
      tipsFailed = false;
      tips = [tip];
      await page.getByRole('region', { name: '试讲技巧视频' }).getByRole('button', { name: '重试' }).click();
      await page.getByRole('heading', { name: tip.title, exact: true }).waitFor();
      await page.evaluate(() => {
        const user = JSON.parse(localStorage.getItem('user'));
        user.role = 'admin';
        localStorage.setItem('user', JSON.stringify(user));
      });
      await page.goto(base + '/admin/teaching-tips');
      await page.getByRole('button', { name: '添加视频', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await dialog.locator('input').nth(0).fill(tip.url);
      await dialog.getByRole('button', { name: '读取标题与封面' }).click();
      await page.waitForFunction(() => [...document.querySelectorAll('.el-dialog input')].some(input => input.value === '读取的视频标题'));
      await dialog.locator('.el-switch').click();
      await dialog.getByRole('button', { name: '保存', exact: true }).click();
      await dialog.waitFor({ state: 'hidden' });
      await page.getByRole('link', { name: '读取的视频标题 ↗', exact: true }).waitFor();
      assert.equal(tips.at(-1).is_published, true);
      const row = page.getByRole('row').filter({ hasText: '读取的视频标题' });
      await row.getByRole('button', { name: '编辑 / 上下架' }).click();
      await dialog.locator('.el-switch').click();
      await dialog.getByRole('button', { name: '保存', exact: true }).click();
      await dialog.waitFor({ state: 'hidden' });
      await row.getByText('已下架', { exact: true }).waitFor();
      await page.screenshot({ path: path.join(output, `admin-${width}.png`), fullPage: true });
      await row.getByRole('button', { name: '删除', exact: true }).click();
      await page.getByRole('button', { name: '确定', exact: true }).click();
      await page.getByRole('link', { name: '读取的视频标题 ↗', exact: true }).waitFor({ state: 'hidden' });
      assert.deepEqual(errors, [], `browser errors: ${errors.join(', ')}`);
      report.push(`${width}px: empty library, retry, admin create/metadata/unpublish/delete passed`);
      await context.close();
    }
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(report.join('\n'));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
