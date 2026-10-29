// Exercise the built UI with deterministic API fixtures; no provider calls.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const base = process.env.TEXTBOOK_UI_URL || 'http://127.0.0.1:5176';
const output = path.resolve('backend/outputs/textbook-ui');
const book = { id: 1, title: '普通高中教科书 物理 必修第一册', edition: '人教版', volume: '必修第一册',
  subject: '物理', grade: '高中一年级', stage: '高中', display_title: '必修第一册', publisher: '人民教育出版社', page_count: 134, status: 'ready', is_published: true };
const chapter = { id: 1, book_id: 1, title: '牛顿第一定律', start_page: 88, end_page: 92, printed_pages: '83–87', is_published: true, score: 106 };
const secondBook = { ...book, id: 2, title: '普通高中教科书 物理 必修第二册', display_title: '必修第二册', volume: '必修第二册' };
const secondChapter = { ...chapter, id: 2, book_id: 2, title: '圆周运动', start_page: 20, end_page: 24 };
const titles = ['滑冰运动员', '伽利略斜面实验频闪照片', '牛顿肖像', '小钢球与纸片'];
const files = ['01_滑冰运动员.png', '02_图4.1-1_伽利略斜面实验.png', '03_牛顿肖像.png', '04_图4.1-2_小钢球与纸片.png'];
const assets = titles.map((title, i) => ({asset_id: 'tb-' + String(i+1).padStart(32, '0'), book_id: 1, chapter_id: 1,
  title, pdf_page: 88+i, figure_number: i===1?'图4.1-1':i===3?'图4.1-2':'', description: title+'，用于观察教材实验。',
  tags: [title], conditions: '以教材说明为准', width: 240, height: 140, is_reviewed: true}));
const lesson = '# 教学过程\n\n观察伽利略斜面实验频闪照片，讨论真实实验中的摩擦。\n\n![' + titles[1] + '](/api/v1/textbooks/assets/' + assets[1].asset_id + '/image)\n\n视频待插入，请自行查找并补充。';
let generated;

async function pageFor(browser, role, formOverrides = {}, wordFixture = 'fixture.docx') {
  const context = await browser.newContext({viewport: {width: 1440, height: 1080}});
  await context.addInitScript(({role, formOverrides}) => {
    localStorage.setItem('token','isolated-ui-test');
    localStorage.setItem('user',JSON.stringify({id:1,name:'界面验证',user_code:'fixture',role,is_default_password:false,is_super_admin:role==='admin'}));
    if (!localStorage.getItem('ai_generator_state')) localStorage.setItem('ai_generator_state',JSON.stringify({form:{subject:'物理',grade:'高中一年级',topic:'牛顿第一定律',duration:15,key_point:'',difficulty:'',modelId:null,use_textbook:true,...formOverrides},templateType:'default',content:''}));
  },{role, formOverrides});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname.replace('/api/v1','');
    if (pathname.startsWith('/ai/lesson-documents/')) return route.fulfill({contentType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',body:fs.readFileSync(path.resolve('backend/outputs/lesson-word',wordFixture))});
    if (pathname.includes('/assets/') && pathname.endsWith('/image')) {
      const index = assets.findIndex(a=>pathname.includes(a.asset_id));
      assert.ok(index>=0);
      return route.fulfill({contentType:'image/png',body:fs.readFileSync(path.resolve('必修第一册图片',files[index]))});
    }
    let data = {};
    if (pathname==='/textbooks') data={success:true,data:[book,secondBook].filter(item=>(!url.searchParams.get('subject')||item.subject===url.searchParams.get('subject'))&&(!url.searchParams.get('stage')||item.stage===url.searchParams.get('stage')))};
    else if (pathname.endsWith('/chapters')) data={success:true,data:pathname==='/textbooks/2/chapters'?[secondChapter]:[chapter]};
    else if (pathname==='/textbooks/recommend') data={success:true,data:[chapter]};
    else if (pathname.endsWith('/assets')) data={success:true,data:assets};
    else if (pathname==='/ai/status') data={enabled:true};
    else if (pathname==='/ai/generate') {
      generated=route.request().postDataJSON();
      data={success:true,data:{content:lesson,lesson_id:1,document_id:'a'.repeat(32),document_format:'docx',sources:{chapter_id:1},asset_ids:[assets[1].asset_id]}};
    }
    else if (pathname==='/ai/lesson-documents') data={success:true,data:{document_id:'a'.repeat(32),document_filename:'牛顿第一定律_教案.docx'}};
    else if (pathname.includes('models')) data={success:true,data:[]};
    else if (pathname==='/chat/contacts') data=[];
    else if (pathname==='/submissions/my') data=[];
    else if (pathname.includes('list')) data={items:[],total:0};
    else if (pathname==='/notices/public/latest') data=null;
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  return {context,page,errors};
}

(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.TEXTBOOK_UI_BROWSER || 'msedge'});
  try {
    const emptyTopic=await pageFor(browser,'student',{topic:'   '});
    await emptyTopic.page.goto(base+'/student/ai-generator');
    const emptyGenerate=emptyTopic.page.getByRole('button',{name:'生成教案',exact:true});
    await emptyTopic.page.getByText('请先填写课题名称、选择章节',{exact:true}).waitFor();
    assert.ok(await emptyGenerate.isDisabled());
    await emptyTopic.page.locator('.el-form-item').filter({has:emptyTopic.page.locator('label').filter({hasText:'科目'})}).locator('.el-select').click();
    await emptyTopic.page.getByRole('option',{name:'语文',exact:true}).waitFor();
    assert.deepEqual(await emptyTopic.page.locator('.el-select-dropdown:visible').getByRole('option').allTextContents(),['语文','数学','英语','物理','政治','道德与法治','化学','生物','地理','历史']);
    await emptyTopic.page.keyboard.press('Escape');
    await emptyTopic.page.getByRole('option',{name:'历史',exact:true}).waitFor({state:'hidden'});
    await emptyTopic.page.locator('.el-form-item').filter({has:emptyTopic.page.locator('label').filter({hasText:'学段'})}).locator('.el-select').click();
    await emptyTopic.page.getByRole('option',{name:'初中',exact:true}).waitFor();
    assert.deepEqual(await emptyTopic.page.locator('.el-select-dropdown:visible').getByRole('option').allTextContents(),['初中','高中']);
    await emptyTopic.page.keyboard.press('Escape');
    await emptyTopic.page.getByRole('option',{name:'初中',exact:true}).waitFor({state:'hidden'});
    await emptyTopic.page.locator('.textbook-selector .el-select').nth(0).click();
    await emptyTopic.page.getByRole('option',{name:book.display_title,exact:true}).click();
    await emptyTopic.page.locator('.textbook-selector .el-select').nth(1).click();
    await emptyTopic.page.getByRole('option',{name:chapter.title,exact:true}).click();
    assert.equal(await emptyTopic.page.locator('.el-form-item').filter({hasText:'课题名称'}).locator('input').inputValue(),chapter.title);
    assert.ok(await emptyGenerate.isEnabled());
    assert.equal(await emptyTopic.page.locator('.form-container .el-select').count(),4);
    assert.equal(await emptyTopic.page.getByRole('button',{name:'确认章节',exact:true}).count(),0);
    assert.equal(await emptyTopic.page.getByRole('button',{name:'推荐章节',exact:true}).count(),0);
    for (const removed of ['快捷填充','教材依据','教案模板','通用教案','时长']) assert.equal(await emptyTopic.page.getByText(removed,{exact:true}).count(),0);
    await emptyTopic.page.locator('.form-container').getByRole('heading',{name:'AI 教案生成',exact:true}).click();
    await emptyTopic.page.getByRole('option',{name:chapter.title,exact:true}).waitFor({state:'hidden'});
    await emptyTopic.page.screenshot({path:path.join(output,'简化教案生成页面.png'),fullPage:true});
    await emptyGenerate.click();
    await emptyTopic.page.getByRole('button',{name:'下载 Word',exact:true}).waitFor();
    assert.equal(generated.topic,chapter.title);
    assert.equal(generated.textbook_chapter_id,chapter.id);
    assert.equal(generated.use_textbook,true);
    assert.equal(generated.template_type,'default');
    assert.equal(generated.duration,15);
    assert.deepEqual(emptyTopic.errors,[]);
    await emptyTopic.context.close();

    const restored=await pageFor(browser,'student',{topic:'',textbook_id:1,textbook_chapter_id:1});
    await restored.page.goto(base+'/student/ai-generator');
    await restored.page.locator('.textbook-selector').getByText(chapter.title,{exact:true}).waitFor();
    assert.equal(await restored.page.locator('.el-form-item').filter({hasText:'课题名称'}).locator('input').inputValue(),chapter.title);
    assert.ok(await restored.page.getByRole('button',{name:'生成教案',exact:true}).isEnabled());
    const topicInput=restored.page.locator('.el-form-item').filter({hasText:'课题名称'}).locator('input');
    await topicInput.fill('   ');
    await restored.page.getByText('请先填写课题名称',{exact:true}).waitFor();
    assert.ok(await restored.page.getByRole('button',{name:'生成教案',exact:true}).isDisabled());
    await topicInput.fill('惯性在生活中的应用');
    assert.ok(await restored.page.getByRole('button',{name:'生成教案',exact:true}).isEnabled());
    const gradeField=restored.page.locator('.el-form-item').filter({has:restored.page.locator('label').filter({hasText:'学段'})});
    const subjectField=restored.page.locator('.el-form-item').filter({has:restored.page.locator('label').filter({hasText:'科目'})});
    await subjectField.locator('.el-select').click();
    await restored.page.getByRole('option',{name:'数学',exact:true}).click();
    await gradeField.locator('.el-select').click();
    await restored.page.getByRole('option',{name:'小学',exact:true}).click();
    await restored.page.getByText('当前科目和学段暂无教材。',{exact:true}).waitFor();
    assert.ok(await restored.page.getByRole('button',{name:'生成教案',exact:true}).isDisabled());
    await subjectField.locator('.el-select').click();
    await restored.page.getByRole('option',{name:'物理',exact:true}).click();
    await gradeField.locator('.el-select').click();
    await restored.page.getByRole('option',{name:'高中',exact:true}).click();
    await restored.page.locator('.textbook-selector .el-select').nth(0).click();
    await restored.page.getByRole('option',{name:secondBook.display_title,exact:true}).click();
    await restored.page.locator('.textbook-selector .el-select').nth(1).click();
    await restored.page.getByRole('option',{name:secondChapter.title,exact:true}).click();
    assert.ok(await restored.page.getByRole('button',{name:'生成教案',exact:true}).isEnabled());
    assert.equal(await topicInput.inputValue(),'惯性在生活中的应用');
    await restored.page.getByRole('button',{name:'生成教案',exact:true}).click();
    await restored.page.getByRole('button',{name:'下载 Word',exact:true}).waitFor();
    assert.equal(generated.textbook_chapter_id,secondChapter.id);
    assert.deepEqual(restored.errors,[]);
    await restored.context.close();

    const student=await pageFor(browser,'student',{topic:'惯性在生活中的应用'});
    await student.page.goto(base+'/student/ai-generator');
    await student.page.getByText('请先选择章节',{exact:true}).waitFor();
    assert.ok(await student.page.getByRole('button',{name:'生成教案',exact:true}).isDisabled());
    await student.page.locator('.textbook-selector .el-select').nth(0).click();
    await student.page.getByRole('option',{name:book.display_title,exact:true}).click();
    await student.page.locator('.textbook-selector .el-select').nth(1).click();
    await student.page.getByRole('option',{name:chapter.title,exact:true}).click();
    await student.page.locator('.el-form-item').filter({hasText:'教学重点'}).locator('textarea').fill('理解惯性');
    await student.page.locator('.el-form-item').filter({hasText:'教学难点'}).locator('textarea').fill('区分惯性与力');
    await student.page.getByRole('option',{name:chapter.title,exact:true}).waitFor({state:'hidden'});
    await student.page.screenshot({path:path.join(output,'章节选择.png'),fullPage:true});
    await student.page.getByRole('button',{name:'生成教案',exact:true}).click();
    await student.page.getByRole('button',{name:'下载 Word',exact:true}).waitFor();
    const image=student.page.locator('.lesson-word-preview img');
    await image.waitFor();
    await image.evaluate(img=>img.decode());
    await student.page.locator('.lesson-word-preview').getByText(titles[1],{exact:false}).first().waitFor();
    assert.equal(await student.page.locator('.lesson-word-preview table').count(),1);
    assert.ok(await student.page.locator('.lesson-word-preview math').count()>=3);
    const previewText=await student.page.locator('.lesson-word-preview').innerText();
    assert.ok(!previewText.includes('\\frac')&&!previewText.includes('**')&&!previewText.includes('| ---'));
    const wordDownload=student.page.getByRole('button',{name:'下载 Word',exact:true});
    await wordDownload.isEnabled();
    const downloadEvent=student.page.waitForEvent('download');
    await wordDownload.click();
    const download=await downloadEvent;
    assert.ok(download.suggestedFilename().endsWith('.docx'));
    const downloaded=fs.readFileSync(await download.path());
    assert.equal(downloaded.subarray(0,2).toString(),'PK');
    assert.deepEqual(downloaded,fs.readFileSync(path.resolve('backend/outputs/lesson-word/fixture.docx')));
    assert.equal(generated.textbook_chapter_id,1);
    assert.equal(generated.use_textbook,true);
    assert.equal(generated.topic,'惯性在生活中的应用');
    assert.equal(generated.key_point,'理解惯性');
    assert.equal(generated.difficulty,'区分惯性与力');
    assert.equal(await student.page.locator('.lesson-word-preview img').count(),1);
    await student.page.reload();
    await student.page.locator('.lesson-word-preview img').waitFor();
    await student.page.waitForFunction(()=>Array.from(document.querySelectorAll('button')).some(button=>button.textContent.includes('下载 Word')&&!button.disabled));
    await student.page.screenshot({path:path.join(output,'Word教案预览.png'),fullPage:true});
    assert.deepEqual(student.errors,[]);
    await student.context.close();
    const longLesson=await pageFor(browser,'student',{},'real-lesson.docx');
    await longLesson.context.addInitScript(()=>{
      const form={subject:'物理',grade:'高中一年级',topic:'自由落体运动',duration:15,key_point:'',difficulty:'',use_textbook:true};
      localStorage.setItem('ai_generator_history',JSON.stringify([{id:'long',title:'自由落体运动',createdAt:Date.now(),form,templateType:'default',content:'历史教案正文',documentId:'a'.repeat(32)}]));
      localStorage.setItem('ai_generator_state',JSON.stringify({form,content:'历史教案正文',currentRecordId:'long',templateType:'default'}));
    });
    await longLesson.page.goto(base+'/student/ai-generator');
    await longLesson.page.locator('.lesson-word-preview img').first().waitFor();
    const scroller=longLesson.page.getByRole('region',{name:'教案预览',exact:true});
    const sizes=await scroller.evaluate(el=>({height:el.clientHeight,scroll:el.scrollHeight}));
    assert.ok(sizes.height>100&&sizes.scroll>sizes.height*2,JSON.stringify(sizes));
    const text=await scroller.innerText();
    assert.ok(!text.includes('教材依据'));
    const preparation=text.split('三、教学准备')[1]?.split('四、教学过程')[0];
    assert.ok(preparation&&!/图\s*\d/.test(preparation),preparation);
    const toolbarBefore=await longLesson.page.locator('.result-toolbar').boundingBox();
    await scroller.hover();await longLesson.page.mouse.wheel(0,1200);
    await longLesson.page.waitForFunction(()=>document.querySelector('.word-pages').scrollTop>200);
    const toolbarAfter=await longLesson.page.locator('.result-toolbar').boundingBox();
    assert.equal(toolbarBefore.y,toolbarAfter.y);
    await scroller.focus();await scroller.press('End');
    await longLesson.page.waitForFunction(()=>{const el=document.querySelector('.word-pages');return el.scrollTop+el.clientHeight>=el.scrollHeight-5});
    await longLesson.page.screenshot({path:path.join(output,'长教案滚动到底部.png')});
    await scroller.press('Home');
    await longLesson.page.waitForFunction(()=>document.querySelector('.word-pages').scrollTop===0);
    await longLesson.page.screenshot({path:path.join(output,'长教案页面顶部.png')});
    await longLesson.page.goto(base+'/student/ai-assistant');
    await longLesson.page.locator('.history-item').filter({hasText:'自由落体运动'}).click();
    const assistantScroller=longLesson.page.getByRole('region',{name:'教案预览',exact:true});
    await longLesson.page.locator('.lesson-word-preview img').first().waitFor();
    await assistantScroller.hover();await longLesson.page.mouse.wheel(0,1200);
    await longLesson.page.waitForFunction(()=>document.querySelector('.word-pages').scrollTop>200);
    await assistantScroller.focus();await assistantScroller.press('End');
    await longLesson.page.waitForFunction(()=>{const el=document.querySelector('.word-pages');return el.scrollTop+el.clientHeight>=el.scrollHeight-5});
    await longLesson.page.screenshot({path:path.join(output,'备课助手长教案滚动.png')});
    assert.deepEqual(longLesson.errors,[]);
    await longLesson.context.close();
    const choices=await pageFor(browser,'student',{topic:''});
    const catalog=JSON.parse(fs.readFileSync('backend/outputs/textbook-audit-current.json','utf8'));
    await choices.page.route('**/api/v1/textbooks?*',route=>{
      const params=new URL(route.request().url()).searchParams;
      const data=catalog.filter(book=>book.is_published&&book.subject===params.get('subject')&&book.grade.startsWith(params.get('stage')))
        .map(book=>({...book,display_title:book.title,stage:params.get('stage')}));
      return route.fulfill({contentType:'application/json',body:JSON.stringify({success:true,data})});
    });
    await choices.page.goto(base+'/student/ai-generator');
    const chooseSubject=choices.page.locator('.el-form-item').filter({has:choices.page.locator('label').filter({hasText:'科目'})}).locator('.el-select');
    const chooseStage=choices.page.locator('.el-form-item').filter({has:choices.page.locator('label').filter({hasText:'学段'})}).locator('.el-select');
    for (const [subject,stages] of Object.entries({'语文':['小学','初中','高中'],'数学':['小学','初中','高中'],'英语':['小学','初中','高中'],'物理':['初中','高中'],'化学':['初中','高中'],'生物':['初中','高中'],'地理':['初中','高中'],'历史':['初中','高中'],'政治':['高中'],'道德与法治':['初中']})) {
      await chooseSubject.click();await choices.page.getByRole('option',{name:subject,exact:true}).click();
      await choices.page.getByRole('option',{name:subject,exact:true}).waitFor({state:'hidden'});
      await chooseStage.click();
      await choices.page.getByRole('option',{name:stages[0],exact:true}).waitFor();
      assert.deepEqual(await choices.page.locator('.el-select-dropdown:visible').getByRole('option').allTextContents(),stages);
      await choices.page.keyboard.press('Escape');
      await choices.page.locator('.el-select-dropdown:visible').waitFor({state:'hidden'});
    }
    for (const [subject,stage,expected] of [
      ['物理','初中',['八年级上册','八年级下册','九年级上册','九年级下册']],
      ['数学','高中',['必修一','必修二','选择性必修一','选择性必修二','选择性必修三']],
      ['语文','高中',['必修上','必修下','选择性必修上册','选择性必修中册','选择性必修下册']],
    ]) {
      await chooseSubject.click();await choices.page.getByRole('option',{name:subject,exact:true}).click();
      await choices.page.getByRole('option',{name:subject,exact:true}).waitFor({state:'hidden'});
      await chooseStage.click();await choices.page.getByRole('option',{name:stage,exact:true}).click();
      await choices.page.getByRole('option',{name:stage,exact:true}).waitFor({state:'hidden'});
      const bookSelect=choices.page.getByRole('combobox',{name:'教材',exact:true});
      await choices.page.waitForFunction(()=>!document.querySelector('.textbook-selector .el-select').classList.contains('is-disabled'));
      await bookSelect.click();
      await choices.page.getByRole('option',{name:expected[0],exact:true}).waitFor();
      assert.deepEqual(await choices.page.locator('.el-select-dropdown:visible').getByRole('option').allTextContents(),expected);
      await choices.page.keyboard.press('Escape');
      await choices.page.locator('.el-select-dropdown:visible').waitFor({state:'hidden'});
    }
    await choices.context.close();
    const admin=await pageFor(browser,'admin');
    await admin.page.goto(base+'/admin/textbooks');
    await admin.page.getByText(book.title,{exact:true}).click();
    await admin.page.locator('.asset-card').first().waitFor();
    assert.equal(await admin.page.locator('.asset-card').count(),4);
    for (const img of await admin.page.locator('.asset-card img').all()) await img.evaluate(img=>img.decode());
    await admin.page.screenshot({path:path.join(output,'管理员素材核对.png'),fullPage:true});
    await admin.page.getByRole('button',{name:'补充教材裁图',exact:true}).click();
    await admin.page.getByRole('dialog',{name:'补充教材裁图',exact:true}).waitFor();
    assert.deepEqual(admin.errors,[]);
    await admin.context.close();
    console.log(JSON.stringify({passed:true,checks:['科目→学段→教材→章节四级选择','教材按文件名显示','选择章节即生效并补全空白课题','恢复旧年级和已选章节','保留手动课题及教学重点难点','切换学段清空旧教材章节','无章节时禁止生成','不同教材章节隔离并正确提交','默认教案设置','Word表格公式原图预览','下载内容与预览Word文件一致','历史Word预览恢复','两个教案入口滚轮键盘滚动到末尾','教材依据与准备插图移除','管理员核对原图','裁图上传入口'],screenshots:output}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
