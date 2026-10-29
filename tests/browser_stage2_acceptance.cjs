// Two isolated browser sessions, against a dedicated acceptance database.
const fs=require('fs');
const {chromium}=require(process.argv[2]||'playwright');
const base=process.env.SURVEY_TEST_BASE||'http://127.0.0.1:5056';
const errors=[];
async function api(page,method,path,data){
  const token=await page.evaluate(()=>sessionStorage.getItem('survey_token'));
  const r=await page.request.fetch(base+'/api'+path,{method,data,headers:{Authorization:'Bearer '+token}});
  const result=await r.json();if(!r.ok())throw Error(`${path}: ${JSON.stringify(result)}`);return result;
}
async function register(page,name){
  await page.goto(base);await page.locator('#username').fill(name);await page.locator('#password').fill('Acceptance-test-123');
  await page.locator('#register').click();await page.getByText('注册成功，请点击登录。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'登录',exact:true}).click();await page.locator('#identity').getByText(name).waitFor();
}
async function newSurvey(page,title){
  await page.goto(base);await page.locator('#new-survey').click();await page.locator('#survey-title').fill(title);
  await page.locator('#survey-form button[type=submit]').click();await page.getByText('问卷已保存',{exact:true}).waitFor();
  await page.locator('#import-library').click();
}
async function openQuestion(page,title,shared=false){
  if(shared)await page.locator('#library-shared').click();else await page.locator('#library-mine').click();
  await page.locator('#library-list article').filter({hasText:title}).getByRole('button',{name:'查看版本与使用',exact:true}).click();
  await page.locator('#library-preview h3').waitFor();
}
async function importPublishFill(page,version,value){
  await page.locator('#library-version').selectOption(version);
  page.once('dialog',d=>d.accept('score'));await page.locator('#library-use').click();
  await page.getByText('指定版本已加入问卷，可返回调整顺序与跳转',{exact:true}).waitFor();
  await page.locator('#library-back').click();
  page.once('dialog',d=>d.accept());await page.locator('#publish-survey').click();
  await page.getByText('发布成功，可复制分享链接。',{exact:true}).waitFor();
  const share=await page.locator('#share-url').inputValue();await page.goto(share);
  await page.getByRole('spinbutton',{name:'填写答案',exact:true}).fill(String(value));
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await page.getByRole('button',{name:'提交问卷',exact:true}).click();
  await page.getByText('提交成功，感谢填写',{exact:true}).waitFor();return share.split('/').pop();
}
(async()=>{
  fs.mkdirSync('output/playwright',{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const a=await browser.newContext(),b=await browser.newContext();
    const owner=await a.newPage(),receiver=await b.newPage();
    for(const page of [owner,receiver])page.on('pageerror',e=>errors.push(e.message));
    const suffix=Date.now(),names=['owner_'+suffix,'receiver_'+suffix];
    await register(owner,names[0]);await register(receiver,names[1]);
    await owner.locator('#open-library').click();owner.once('dialog',d=>d.accept('连续验收题库'));await owner.locator('#bank-new').click();
    await owner.locator('#library-bank option').filter({hasText:'连续验收题库'}).waitFor({state:'attached'});
    await owner.locator('#library-new').click();await owner.locator('#library-title').fill('课程满意度评分');
    await owner.locator('#library-type').selectOption('number');await owner.locator('#library-min').fill('0');await owner.locator('#library-max').fill('10');
    await owner.locator('#library-required').check();await owner.locator('#library-save').click();
    await owner.getByText('已创建题目及首个版本',{exact:true}).waitFor();
    const first=await owner.locator('#library-version').inputValue();
    const library=(await api(owner,'GET','/library/questions')).items[0];
    await owner.locator('#library-users').fill(names[1]);await owner.locator('#library-share').click();
    await owner.getByText('共享权限已更新；对方可读取版本并导入，不能修改原题',{exact:true}).waitFor();
    await newSurvey(receiver,'接收者旧版本问卷');await openQuestion(receiver,'课程满意度评分',true);
    if(await receiver.locator('#library-form').isVisible())throw Error('Shared user can edit source');
    const receiverSid=await importPublishFill(receiver,first,2);
    const before=await api(receiver,'GET','/surveys/'+receiverSid);
    await owner.locator('#library-title').fill('课程满意度新版评分');await owner.locator('#library-commit').click();
    await owner.getByText('新版本已提交，旧版本与旧问卷保持原样',{exact:true}).waitFor();
    const second=await owner.locator('#library-version').inputValue();
    if(first===second)throw Error('Version did not advance');
    await owner.locator('#library-heading').scrollIntoViewIfNeeded();
    const detailBox=await owner.locator('#library-detail').boundingBox();
    const formBox=await owner.locator('#library-form').boundingBox();
    await owner.screenshot({path:'output/playwright/stage2-version-panel.png',clip:{
      x:detailBox.x,y:detailBox.y,width:detailBox.width,height:formBox.y-detailBox.y}});
    const unchanged=await api(receiver,'GET','/surveys/'+receiverSid);
    if(JSON.stringify(before.questions)!==JSON.stringify(unchanged.questions))throw Error('Published snapshot changed');
    await owner.locator('#library-usage').click();await owner.locator('#library-result').getByText(/外部引用数：1/).waitFor();
    if((await owner.locator('#library-result').textContent()).includes('接收者旧版本问卷'))throw Error('External title leaked');
    await owner.locator('#library-back').click();await newSurvey(owner,'作者新版问卷');await openQuestion(owner,'课程满意度新版评分');
    const ownerSid=await importPublishFill(owner,second,8);
    await receiver.goto(base);await receiver.locator('#open-library').click();await openQuestion(receiver,'课程满意度新版评分',true);
    await receiver.locator('#library-stats').click();await receiver.locator('#library-result').getByText('平均值：2；最小值：2；最大值：2',{exact:true}).waitFor();
    await owner.goto(base);await owner.locator('#open-library').click();await openQuestion(owner,'课程满意度新版评分');
    await owner.locator('#library-stats').click();await owner.locator('#library-result').getByText('平均值：8；最小值：8；最大值：8',{exact:true}).waitFor();
    await owner.locator('#library-result').screenshot({path:'output/playwright/stage2-cross-statistics.png'});
    await owner.screenshot({path:'output/playwright/stage2-owner-acceptance.png',fullPage:true});
    await receiver.goto(base);
    await receiver.locator('#survey-list article').filter({hasText:'接收者旧版本问卷'}).getByRole('button',{name:'管理问卷',exact:true}).click();
    await receiver.getByLabel('向题主公开本卷名称及题目使用位置',{exact:true}).check();
    await receiver.getByLabel('允许题主汇总本题统计（不含身份、链接及文本原文）',{exact:true}).check();
    await receiver.getByRole('button',{name:'保存题目共享范围',exact:true}).click();
    await receiver.getByText('题目共享范围已保存',{exact:true}).waitFor();
    await owner.locator('#library-usage').click();
    await owner.locator('#library-result').getByText(/已授权外部问卷：接收者旧版本问卷/).waitFor();
    await owner.locator('#library-stat-scope').selectOption('all');
    await owner.locator('#library-result').getByRole('heading',{name:'全部已授权问卷的跨卷统计',exact:true}).waitFor();
    await owner.locator('#library-result').getByText('平均值：2；最小值：2；最大值：2',{exact:true}).waitFor();
    await owner.locator('#library-result').getByText('平均值：8；最小值：8；最大值：8',{exact:true}).waitFor();
    await owner.locator('#library-result').screenshot({path:'output/playwright/stage2-authorized-statistics.png'});
    await receiver.getByLabel('向题主公开本卷名称及题目使用位置',{exact:true}).uncheck();
    await receiver.getByLabel('允许题主汇总本题统计（不含身份、链接及文本原文）',{exact:true}).uncheck();
    await receiver.getByRole('button',{name:'保存题目共享范围',exact:true}).click();
    await receiver.getByText('题目共享范围已保存',{exact:true}).waitFor();
    await owner.locator('#library-stats').click();
    await owner.locator('#library-result').getByText('平均值：8；最小值：8；最大值：8',{exact:true}).waitFor();
    await owner.locator('#library-result').getByText('平均值：2；最小值：2；最大值：2',{exact:true}).waitFor({state:'detached'});
    await owner.locator('#library-users').fill('');await owner.locator('#library-share').click();
    await owner.getByText('共享权限已更新；对方可读取版本并导入，不能修改原题',{exact:true}).waitFor();
    const receiverToken=await receiver.evaluate(()=>sessionStorage.getItem('survey_token'));
    const denied=await receiver.request.get(base+'/api/library/questions/'+library._id,{headers:{Authorization:'Bearer '+receiverToken}});
    if(denied.status()!==404)throw Error('Revoked access remained open');
    const retained=await api(receiver,'GET','/surveys/'+receiverSid);
    if(JSON.stringify(before.questions)!==JSON.stringify(retained.questions))throw Error('Revocation removed imported snapshot');
    await owner.locator('#library-version').selectOption(first);owner.once('dialog',d=>d.accept());await owner.locator('#library-restore').click();
    await owner.getByText('已恢复并生成新版本',{exact:true}).waitFor();
    await owner.locator('#library-preview').getByText('课程满意度评分',{exact:true}).waitFor();
    const final=await api(owner,'GET','/library/questions/'+library._id);
    if(final.versions.length!==3||final.versions[2].restored_from!==first)throw Error('History lost during restore');
    if(errors.length)throw Error(errors.join('\n'));
    fs.writeFileSync('tests/results/stage2-acceptance.json',JSON.stringify({successful:true,executed_at_utc:new Date().toISOString(),
      scope:'two independent browser sessions on isolated MongoDB',flows:['UI register/login','UI share','UI old-version import and publish','UI numeric submission',
      'source update preserves published snapshot','external usage privacy','owner/receiver statistics isolated','revoke preserves snapshot','UI restore preserves history','UI consent grants and revocation','authorized cross-user aggregates by version'],
      pageErrors:errors},null,2)+'\n');
    console.log('Two-account continuous browser acceptance passed');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
