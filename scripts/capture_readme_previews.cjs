// Actual UI captures, using a separate survey_test_ database behind the supplied URL.
const fs=require('fs');
const {chromium}=require(process.argv[2]);
const base=process.env.SURVEY_PREVIEW_BASE||'http://127.0.0.1:5056';
const out='第二阶段/images';
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const context=await browser.newContext({viewport:{width:1200,height:1000},deviceScaleFactor:1.5});
    const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
    const suffix=Date.now(),owner='preview_owner_'+suffix,reader='preview_reader_'+suffix;
    let token;
    async function api(method,path,data){
      const response=await page.request.fetch(base+'/api'+path,{method,data,headers:token?{Authorization:'Bearer '+token}:{}});
      const result=await response.json();if(!response.ok())throw Error(path+': '+JSON.stringify(result));return result;
    }
    for(const username of [owner,reader])await api('POST','/auth/register',{username,password:'Preview-only-123'});
    token=(await api('POST','/auth/login',{username:owner,password:'Preview-only-123'})).token;
    let survey=await api('POST','/surveys',{title:'校园服务体验问卷',description:'使用服务的同学继续评价；未使用的同学直接填写建议。',allow_anonymous:true});
    const qs=[
      {id:'q1',title:'你是否使用过校园服务？',type:'single',required:true,options:[{id:'yes',label:'使用过'},{id:'no',label:'未使用过'}],jumps:[{op:'eq',value:'no',target:'q4'}]},
      {id:'q2',title:'你使用过哪些服务？',type:'multiple',required:true,options:[{id:'library',label:'图书馆'},{id:'canteen',label:'食堂'},{id:'sports',label:'体育场馆'}],validation:{min_choices:1,max_choices:3}},
      {id:'q3',title:'请为校园服务评分（0～10分）',type:'number',required:true,validation:{min:0,max:10,integer:true}},
      {id:'q4',title:'你还有哪些建议？',type:'text',validation:{max_length:200}}
    ];
    for(const question of qs)survey=await api('POST',`/surveys/${survey._id}/questions`,{revision:survey.revision,question});
    const bank=await api('POST','/banks',{title:'校园服务常用题',description:'用于不同校园活动问卷的复用示例'});
    const item=(await api('POST','/library/questions',{bank_id:bank._id,question:{title:'校园服务满意度',type:'number',required:true,validation:{min:0,max:10,integer:true}}})).item;
    await api('PUT',`/library/questions/${item._id}/sharing`,{revision:item.revision,usernames:[reader]});
    await page.goto(base);await page.evaluate(t=>sessionStorage.setItem('survey_token',t),token);await page.reload();
    await page.locator('#identity').getByText(owner).waitFor();
    await page.locator('#survey-list article').filter({hasText:survey.title}).getByRole('button',{name:'管理问卷'}).click();
    await page.locator('#question-list article').filter({hasText:qs[0].title}).getByRole('button',{name:'编辑',exact:true}).click();
    await page.locator('#jump-list').getByText(/未使用过/).waitFor();
    await page.locator('#question-form').screenshot({path:out+'/stage2-editor-preview.png'});
    await page.locator('#back').click();await page.locator('#open-library').click();
    await page.locator('#library-list article').filter({hasText:'校园服务满意度'}).getByRole('button',{name:'查看版本与使用'}).click();
    await page.locator('#library-users').waitFor();
    if(await page.locator('#library-users').inputValue()!==reader)throw Error('Shared username missing');
    await page.locator('#library-detail').screenshot({path:out+'/stage2-sharing-preview.png'});
    survey=await api('POST',`/surveys/${survey._id}/publish`,{revision:survey.revision});
    await page.goto(base+'/survey/'+survey._id);
    await page.locator('#fill-input').getByLabel('未使用过',{exact:true}).check();
    await page.locator('#fill').screenshot({path:out+'/stage2-fill-preview.png'});
    await page.locator('#fill-next').click();await page.locator('#fill-question-title').getByText('你还有哪些建议？',{exact:false}).waitFor();
    if(errors.length)throw Error(errors.join('\n'));
    fs.mkdirSync('output/playwright',{recursive:true});
    fs.writeFileSync('output/playwright/readme-preview-capture.json',JSON.stringify({successful:true,captured_at_utc:new Date().toISOString(),
      scope:'isolated synthetic data; API fixtures and actual browser rendering',
      files:['stage2-editor-preview.png','stage2-sharing-preview.png','stage2-fill-preview.png'],
      checked:['saved jump rule rendered','sharing configuration rendered','fill answer selection rendered','no-use answer jumps to suggestion question'],pageErrors:errors},null,2));
    console.log('Three actual interface previews captured; jump path checked.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
