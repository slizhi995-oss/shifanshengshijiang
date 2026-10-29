// Check the source biology catalog through the actual Vue chapter selector.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.resolve('backend/outputs/highschool-biology-directory');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'catalog.json'), 'utf8'));
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  try {
    for (const fixture of fixtures) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
      await context.addInitScript(({ book }) => {
        localStorage.setItem('token', 'biology-directory-check');
        localStorage.setItem('user', JSON.stringify({ id: 1, name: '目录检查', user_code: 'fixture', role: 'student', is_default_password: false }));
        localStorage.setItem('ai_generator_state', JSON.stringify({ form: {
          subject: book.subject, grade: book.grade, topic: '', duration: 15,
          use_textbook: true, textbook_id: book.id,
        }, templateType: 'default', content: '' }));
      }, fixture);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/v1/**', async route => {
        const pathname = new URL(route.request().url()).pathname.replace('/api/v1', '');
        let result = { success: true, data: [] };
        if (pathname === '/textbooks') result.data = [fixture.book];
        else if (pathname.endsWith('/chapters')) result.data = fixture.chapters;
        else if (pathname === '/ai/status') result = { enabled: true };
        else if (pathname === '/chat/contacts' || pathname === '/submissions/my') result = [];
        else if (pathname.includes('list')) result = { items: [], total: 0 };
        else if (pathname === '/notices/public/latest') result = null;
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) });
      });
      await page.goto(base + '/student/ai-generator');
      await page.locator('.textbook-selector .el-select').nth(1).click();
      const dropdown = page.locator('.el-select-dropdown:visible');
      await dropdown.getByRole('option').first().waitFor();
      const labels = await dropdown.locator('.chapter-directory-section, .chapter-directory-title').allTextContents();
      assert.deepEqual(labels, fixture.chapters.map(row => row.title));
      assert.equal(await dropdown.locator('.el-select-group__title:visible').count(), 0);
      assert.ok(!labels.some(title => /其他章节|附\s*录|[.．…]{2,}\s*\d+$/.test(title)));
      assert.equal(await dropdown.locator('.chapter-directory-row--nested').count(), fixture.chapters.filter(row => row.is_nested).length);
      const chapter = dropdown.locator('.chapter-directory-section').first();
      const section = dropdown.getByRole('option').filter({ hasText: /^第1节 / }).first().locator('.chapter-directory-title');
      const column = dropdown.locator('.chapter-directory-row--nested .chapter-directory-title').first();
      const chapterX = await chapter.evaluate(el => el.getBoundingClientRect().x + parseFloat(getComputedStyle(el).paddingLeft));
      const sectionX = (await section.boundingBox()).x;
      const columnX = (await column.boundingBox()).x;
      assert.equal(sectionX - chapterX, 40);
      assert.equal(columnX - sectionX, 40);
      await dropdown.screenshot({ path: path.join(output, `book-${fixture.book.id}.png`), animations: 'disabled' });
      const target = fixture.chapters.find(row => row.is_nested);
      await dropdown.getByRole('option', { name: target.title, exact: true }).click();
      assert.equal(await page.locator('.el-form-item').filter({ hasText: '课题名称' }).locator('input').inputValue(), target.title);
      assert.deepEqual(errors, []);
      console.log(`${fixture.book.title}: ${labels.length} entries, 40px hierarchy, column selection passed`);
      await context.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
