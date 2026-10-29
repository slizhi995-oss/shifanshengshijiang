// Display real synchronized API rows through the existing textbook selector.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve('backend/outputs/english-refresh-20261021');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'api-fixtures.json'), 'utf8'));
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5176';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const report = [];
  try {
    for (const fixture of fixtures) {
      for (const width of [1440, 580]) {
        const context = await browser.newContext({ viewport: { width, height: 1080 } });
        await context.addInitScript(({ book }) => {
          localStorage.setItem('token', 'english-refresh-ui-test');
          localStorage.setItem('user', JSON.stringify({ id: 1, name: '界面验证', user_code: 'fixture', role: 'student', is_default_password: false }));
          localStorage.setItem('ai_generator_state', JSON.stringify({ form: { subject: book.subject, grade: book.grade.startsWith('小学') ? '小学' : '初中', topic: '', duration: 15, key_point: '', difficulty: '', modelId: null, use_textbook: true, textbook_id: book.id }, templateType: 'default', content: '' }));
        }, fixture);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/api/v1/**', async route => {
          const pathname = new URL(route.request().url()).pathname.replace('/api/v1', '');
          let data = { success: true, data: [] };
          if (pathname === '/textbooks') data.data = fixture.books;
          else if (pathname.endsWith('/chapters')) data.data = fixture.chapters;
          else if (pathname === '/ai/status') data = { enabled: true };
          else if (pathname === '/chat/contacts' || pathname === '/submissions/my') data = [];
          else if (pathname.includes('list')) data = { items: [], total: 0 };
          else if (pathname === '/notices/public/latest') data = null;
          await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
        });
        await page.goto(base + '/student/ai-generator');
        const selects = page.locator('.textbook-selector .el-select');
        await selects.nth(0).click();
        let dropdown = page.locator('.el-select-dropdown:visible');
        await dropdown.getByRole('option', { name: fixture.book.title, exact: true }).waitFor();
        const labels = await dropdown.getByRole('option').allTextContents();
        assert(!labels.some(label => label.includes('九年级全一册')));
        assert.equal(labels.filter(label => label.trim() === fixture.book.title).length, 1);
        await page.keyboard.press('Escape');
        await dropdown.waitFor({ state: 'hidden' });
        await selects.nth(1).click();
        dropdown = page.locator('.textbook-chapter-dropdown:visible .el-select-dropdown');
        const options = dropdown.getByRole('option');
        await dropdown.locator('.chapter-directory-title').first().waitFor();
        const expected = fixture.chapters.filter(row => !row.is_unit);
        assert.equal(await options.count(), expected.length);
        const visibleTitles = await dropdown.locator('.chapter-directory-title').allTextContents();
        assert.deepEqual(visibleTitles, expected.map(row => row.display_title || row.title));
        assert(!visibleTitles.some(title => /^(?:Appendix|Revision|Recycle|Vocabulary A-Z|Listening Scripts)/i.test(title)));
        const primary = fixture.book.grade.startsWith('小学');
        if (primary) {
          assert.equal(await dropdown.locator('.el-select-group__title:visible').count(), 0);
          assert.equal(await dropdown.locator('.chapter-directory-section').count(), 0);
        } else {
          assert.equal(await dropdown.locator('.el-select-group__title').count(), 8);
          assert.equal(await dropdown.locator('.chapter-directory-section').count(), 0);
          assert(expected.every(row => /^Section [AB]:/.test(row.title)));
          assert((await dropdown.innerText()).includes('Section A: What changes have taken place around you?'));
          assert((await dropdown.innerText()).includes('Section B: How do changes influence us?'));
        }
        const style = await options.first().evaluate(element => {
          const css = getComputedStyle(element);
          const title = element.querySelector('.chapter-directory-title');
          return { padding: parseFloat(css.paddingLeft), weight: css.fontWeight,
            overflow: title.scrollWidth > title.clientWidth + 1 };
        });
        const small = width <= 600;
        assert.equal(style.padding, primary ? (small ? 16 : 20) : (small ? 40 : 60));
        assert.equal(style.weight, '400');
        assert.equal(style.overflow, false);
        await page.screenshot({ path: path.join(output, `book-${fixture.book.id}-${width}.png`), fullPage: true, animations: 'disabled' });
        const selected = expected[0];
        await options.first().click();
        assert.equal(await page.locator('.el-form-item').filter({ hasText: '课题名称' }).locator('input').inputValue(), selected.title);
        assert.deepEqual(errors, []);
        report.push({ book: fixture.book.title, id: fixture.book.id, width, options: expected.length, ...style });
        await context.close();
      }
    }
    fs.writeFileSync(path.join(output, 'ui-verification.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
