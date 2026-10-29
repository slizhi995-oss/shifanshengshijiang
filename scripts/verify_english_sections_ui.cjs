// Check the actual selector with fixtures exported from student HTTP responses.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve('backend/outputs/english-sections');
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5173';

(async () => {
  const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'api-fixtures.json'), 'utf8'));
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const report = [];
  try {
    for (const fixture of fixtures) {
      for (const width of [1440, 580]) {
        const context = await browser.newContext({ viewport: { width, height: 1080 } });
        await context.addInitScript(({ book }) => {
          localStorage.setItem('token', 'english-sections-ui-test');
          localStorage.setItem('user', JSON.stringify({ id: 1, name: '界面验证', user_code: 'fixture', role: 'student', is_default_password: false }));
          localStorage.setItem('ai_generator_state', JSON.stringify({ form: {
            subject: '英语', grade: book.grade.startsWith('初中') ? '初中' : '高中',
            topic: '', duration: 15, modelId: null, use_textbook: true, textbook_id: book.id,
          }, templateType: 'default', content: '' }));
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
        const selector = page.locator('.textbook-selector .el-select').nth(1);
        await selector.click();
        const dropdown = page.locator('.textbook-chapter-dropdown:visible .el-select-dropdown');
        await dropdown.locator('.chapter-directory-title').first().waitFor();
        const choices = fixture.chapters.filter(row => !row.is_unit);
        const options = dropdown.getByRole('option');
        assert.deepEqual(await dropdown.locator('.chapter-directory-title').allTextContents(), choices.map(row => row.display_title || row.title));
        assert.equal(await dropdown.locator('.chapter-directory-section').count(), 0);
        const sectionRows = choices.filter(row => row.directory_layout === 'sections');
        if (fixture.book.grade.startsWith('初中')) {
          assert(sectionRows.every(row => /^Section [AB]:/.test(row.title)));
          assert.equal(sectionRows.length, choices.length);
        }
        const style = await options.first().evaluate(element => {
          const css = getComputedStyle(element);
          const title = element.querySelector('.chapter-directory-title');
          return { padding: parseFloat(css.paddingLeft), weight: css.fontWeight,
            overflow: title.scrollWidth > title.clientWidth + 1 };
        });
        assert.equal(style.padding, width <= 600 ? 40 : 60);
        assert.equal(style.weight, '400');
        assert.equal(style.overflow, false);
        await page.screenshot({ path: path.join(output, `book-${fixture.book.id}-${width}.png`), fullPage: true, animations: 'disabled' });
        await options.first().click();
        const topic = page.locator('.el-form-item').filter({ hasText: '课题名称' }).locator('input');
        assert.equal(await topic.inputValue(), choices[0].title);
        // The section remains individually filterable and selectable.
        await selector.click();
        const search = selector.locator('input').first();
        await search.fill(choices[0].title);
        await dropdown.getByRole('option', { name: choices[0].title, exact: true }).first().waitFor();
        assert.deepEqual(errors, []);
        report.push({ id: fixture.book.id, title: fixture.book.title, width, sections: sectionRows.length, options: choices.length, ...style });
        await context.close();
      }
    }
    fs.writeFileSync(path.join(output, 'ui-verification.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ cases: report.length, books: fixtures.length, allPassed: true }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
