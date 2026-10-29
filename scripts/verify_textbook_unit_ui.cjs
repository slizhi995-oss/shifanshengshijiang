// Exercise grouping against metadata recovered from the local textbook PDFs.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const fixtures = JSON.parse(fs.readFileSync('backend/outputs/unit-groups/catalog.json', 'utf8'));
const output = path.resolve('backend/outputs/unit-groups');
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch({headless:true,channel:'msedge'});
  try {
    for (const fixture of fixtures) {
      const context = await browser.newContext({viewport:{width:1440,height:1080}});
      await context.addInitScript(({book}) => {
        localStorage.setItem('token','unit-directory-ui-test');
        localStorage.setItem('user',JSON.stringify({id:1,name:'界面验证',user_code:'fixture',role:'student',is_default_password:false}));
        if (!localStorage.getItem('ai_generator_state')) localStorage.setItem('ai_generator_state',JSON.stringify({form:{subject:book.subject,grade:book.grade,topic:'',duration:15,key_point:'',difficulty:'',modelId:null,use_textbook:true,textbook_id:book.id},templateType:'default',content:''}));
      },fixture);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror',error => errors.push(error.message));
      await page.route('**/api/v1/**',async route => {
        const pathname = new URL(route.request().url()).pathname.replace('/api/v1','');
        let data = {success:true,data:[]};
        if (pathname === '/textbooks') data.data = [fixture.book];
        else if (pathname.endsWith('/chapters')) data.data = fixture.chapters;
        else if (pathname === '/ai/status') data = {enabled:true};
        else if (pathname === '/chat/contacts' || pathname === '/submissions/my') data = [];
        else if (pathname.includes('list')) data = {items:[],total:0};
        else if (pathname === '/notices/public/latest') data = null;
        await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
      });
      await page.goto(base+'/student/ai-generator');
      const select = page.locator('.textbook-selector .el-select').nth(1);
      await select.click();
      const dropdown = page.locator('.el-select-dropdown:visible');
      const firstUnit = fixture.chapters.find(chapter => chapter.unit_title)?.unit_title;
      await dropdown.locator('.el-select-group__title').filter({hasText:firstUnit}).first().waitFor();
      const headers = await dropdown.locator('.el-select-group__title').allTextContents();
      if (fixture.book.id === 111) {
        for (const [title, names, pages] of [
          ['第二单元·汉语拼音',['1 a o e','2 i u ü','3 b p m f','4 d t n l','◎ 语文园地二'],['20','22','24','26','28']],
          ['第三单元·汉语拼音',['5 g k h','6 j q x','7 z c s','8 zh ch sh r','9 y w','◎ 语文园地三'],['32','34','36','38','40','42']],
        ]) {
          const group = dropdown.locator('.el-select-group__wrap').filter({has:page.locator('.el-select-group__title',{hasText:title})});
          assert.deepEqual(await group.locator('.chapter-directory-title').allTextContents(),names);
          assert.deepEqual(await group.locator('.chapter-directory-page').allTextContents(),pages);
        }
      }
      for (const unit of new Set(fixture.chapters.map(chapter => chapter.unit_title).filter(Boolean))) assert.ok(headers.includes(unit),unit);
      assert.equal(await dropdown.getByRole('option').count(),fixture.chapters.filter(chapter => !chapter.is_unit && chapter.is_published).length);
      const header = dropdown.locator('.el-select-group__title').filter({hasText:firstUnit}).first();
      await header.click();
      assert.equal(await select.locator('.el-select__selected-item').filter({hasText:'选择章节'}).count(),1);
      assert.equal(await dropdown.getByRole('option',{name:firstUnit,exact:true}).count(),0);
      const option = fixture.chapters.find(chapter => !chapter.is_unit && chapter.unit_title === firstUnit && chapter.is_published);
      await dropdown.getByRole('option',{name:option.title,exact:true}).first().click();
      assert.equal(await page.locator('.el-form-item').filter({hasText:'课题名称'}).locator('input').inputValue(),option.title);
      await select.click();
      await page.keyboard.press('ArrowDown');
      const hovering = dropdown.locator('.el-select-dropdown__item.is-hovering');
      await hovering.waitFor();
      assert.ok(!headers.includes((await hovering.innerText()).trim()));
      await page.keyboard.press('Escape');
      // A restored unit heading must be cleared instead of becoming a selection.
      const unitRow = fixture.chapters.find(chapter => chapter.is_unit && chapter.is_published);
      if (unitRow) {
        await page.evaluate(id => {
          const state = JSON.parse(localStorage.getItem('ai_generator_state'));
          state.form.textbook_chapter_id = id;
          localStorage.setItem('ai_generator_state',JSON.stringify(state));
        },unitRow.id);
        await page.reload();
        await page.locator('.textbook-selector .el-select').nth(1).click();
        await dropdown.getByRole('option').first().waitFor();
        assert.equal(await page.locator('.textbook-selector .el-select').nth(1).locator('.el-select__placeholder').innerText(),'选择章节');
      }
      const chapterSelect = page.locator('.textbook-selector .el-select').nth(1);
      if (await chapterSelect.getByRole('combobox').getAttribute('aria-expanded') !== 'true') await chapterSelect.click();
      await dropdown.getByRole('option').first().waitFor();
      if (fixture.book.id === 111) {
        await dropdown.getByRole('option',{name:'1 a o e',exact:true}).scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(output,'grade1-unit2.png'),fullPage:true,animations:'disabled'});
        await dropdown.getByRole('option',{name:'5 g k h',exact:true}).scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(output,'grade1-unit3.png'),fullPage:true,animations:'disabled'});
      }
      await page.screenshot({path:path.join(output,`book-${fixture.book.id}.png`),fullPage:true,animations:'disabled'});
      assert.deepEqual(errors,[]);
      console.log(`教材 ${fixture.book.id}：单元标题、不可选、章节选择和键盘检查通过`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
