// Run after python -m scripts.verify_junior_physics; exercise the real Vue UI.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.resolve(process.env.PHYSICS_UI_OUTPUT || 'backend/outputs/junior-physics-directory');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'catalog.json'), 'utf8'));
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch({headless: true, channel: 'msedge'});
  try {
    for (const fixture of fixtures) {
      const context = await browser.newContext({viewport: {width: 1440, height: 1080}});
      await context.addInitScript(({book}) => {
        localStorage.setItem('token', 'physics-directory-test');
        localStorage.setItem('user', JSON.stringify({id: 1, name: '目录检查', user_code: 'fixture', role: 'student', is_default_password: false}));
        if (!localStorage.getItem('ai_generator_state')) localStorage.setItem('ai_generator_state', JSON.stringify({
          form: {subject: book.subject, grade: book.grade, topic: '', duration: 15, use_textbook: true, textbook_id: book.id},
          templateType: 'default', content: '',
        }));
      }, fixture);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/v1/**', async route => {
        const pathname = new URL(route.request().url()).pathname.replace('/api/v1', '');
        let result = {success: true, data: []};
        if (pathname === '/textbooks') result.data = [fixture.book];
        else if (pathname.endsWith('/chapters')) result.data = fixture.chapters;
        else if (pathname === '/ai/status') result = {enabled: true};
        else if (pathname === '/chat/contacts' || pathname === '/submissions/my') result = [];
        else if (pathname.includes('list')) result = {items: [], total: 0};
        else if (pathname === '/notices/public/latest') result = null;
        await route.fulfill({contentType: 'application/json', body: JSON.stringify(result)});
      });
      await page.goto(base + '/student/ai-generator');
      const select = page.locator('.textbook-selector .el-select').nth(1);
      await select.click();
      const dropdown = page.locator('.el-select-dropdown:visible');
      await dropdown.getByRole('option').first().waitFor();
      const expected = [];
      let currentUnit = '';
      for (const chapter of fixture.chapters) {
        if (chapter.is_unit && chapter.unit_title === currentUnit) continue;
        currentUnit = chapter.unit_title || '';
        expected.push(chapter.display_title || chapter.title);
      }
      const visibleRows = dropdown.locator('.el-select-group__title, .chapter-directory-title');
      const labels = (await visibleRows.allTextContents()).filter(label => label.trim());
      assert.deepEqual(labels, expected);
      assert.equal(await dropdown.getByRole('option').count(), fixture.chapters.filter(c => !c.is_unit).length);
      assert.equal(await dropdown.locator('.chapter-directory-row--nested').count(), fixture.chapters.filter(c => c.is_nested).length);
      assert.equal(await dropdown.locator('img, .chapter-directory-page').count(), 0);
      if (fixture.book.grade.startsWith('高中')) assert.equal(labels[0], fixture.chapters[0].title);
      const title = fixture.book.id === 68 ? '第二章 机械运动' : fixture.chapters.find(c => c.is_unit).title;
      const group = dropdown.locator('.el-select-group__wrap').filter({has: page.locator('.el-select-group__title', {hasText: title})});
      const heading = group.locator('.el-select-group__title');
      await heading.scrollIntoViewIfNeeded();
      await heading.evaluate(element => {
        const wrap = element.closest('.el-select-dropdown__wrap');
        wrap.scrollTop += element.getBoundingClientRect().top - wrap.getBoundingClientRect().top;
      });
      const headingBox = await heading.boundingBox();
      const option = group.getByRole('option').first();
      const optionBox = await option.boundingBox();
      assert.equal(headingBox.x, optionBox.x);
      const styles = await group.evaluate(element => [...element.querySelectorAll('.el-select-group__title, .el-select-dropdown__item')].map(row => {
        const style = getComputedStyle(row);
        return [style.paddingLeft, style.fontSize, style.fontWeight];
      }));
      assert.ok(styles.every(style => JSON.stringify(style) === JSON.stringify(styles[0])), JSON.stringify(styles));
      const headingTextX = headingBox.x + Number.parseFloat(styles[0][0]);
      const sectionTitleBox = await option.locator('.chapter-directory-title').boundingBox();
      assert.equal(sectionTitleBox.x - headingTextX, 28);
      const review = group.getByRole('option', {name: '整理与复习', exact: true});
      if (await review.count()) {
        const reviewTitleBox = await review.locator('.chapter-directory-title').boundingBox();
        assert.equal(reviewTitleBox.x, sectionTitleBox.x);
      }
      await page.screenshot({path: path.join(output, `book-${fixture.book.id}.png`), fullPage: true, animations: 'disabled'});
      if (fixture.book.id === 68) await dropdown.screenshot({path: path.join(output, 'mechanical-motion-directory.png'), animations: 'disabled'});
      if (fixture.book.id === 70) await dropdown.screenshot({path: path.join(output, 'highschool-directory.png'), animations: 'disabled'});
      // A chapter header labels the list; a real section remains selectable.
      await heading.click();
      assert.equal(await dropdown.getByRole('option', {name: title, exact: true}).count(), 0);
      const target = group.getByRole('option', {name: '整理与复习', exact: true});
      const chosen = await target.count() ? target : option;
      const chosenTitle = (await chosen.innerText()).trim();
      await chosen.click();
      assert.equal(await page.locator('.el-form-item').filter({hasText: '课题名称'}).locator('input').inputValue(), chosenTitle);
      if (fixture.book.grade.startsWith('高中')) {
        await page.evaluate(id => {
          const state = JSON.parse(localStorage.getItem('ai_generator_state'));
          state.form.textbook_chapter_id = id;
          localStorage.setItem('ai_generator_state', JSON.stringify(state));
        }, fixture.chapters[0].id);
        await page.reload();
        await select.click();
        await dropdown.getByRole('option').first().waitFor();
        assert.equal(await select.locator('.el-select__placeholder').innerText(), '选择章节');
      }
      if (fixture.book.id === 68) {
        await page.setViewportSize({width: 390, height: 844});
        await select.click();
        await group.getByRole('option', {name: '第一节 运动与静止', exact: true}).scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(output, 'grade8-mobile.png'), fullPage: true, animations: 'disabled'});
      }
      assert.deepEqual(errors, []);
      console.log(`${fixture.book.title}: order, alignment, chapter headers and selection passed`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
