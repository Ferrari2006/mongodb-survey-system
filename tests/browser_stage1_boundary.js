// Playwright CLI run-code. Open the app in a dedicated, isolated test database first.
// Creates a fresh synthetic account and two surveys; does not delete existing data.
async (page) => {
  const origin=new URL(page.url()).origin;
  if(!['127.0.0.1','localhost','[::1]'].includes(new URL(origin).hostname))throw new Error('Use a local isolated test app');
  const suffix=Date.now().toString(36)+Math.random().toString(36).slice(2,8);
  const username='boundary_'+suffix,password='Boundary-check-123';
  const titleA='边界问卷A_'+suffix,titleB='边界问卷B_'+suffix;
  const textTitle='边界文本_'+suffix,numberTitle='边界数字_'+suffix,answerA='仅属于问卷A的答卷_'+suffix;
  const visible=text=>page.getByText(text,{exact:true}).waitFor({state:'visible'});
  const check=async(condition,message)=>{if(!await condition)throw new Error(message);};
  const call=(path,method='GET',body)=>page.evaluate(async({path,method,body})=>{
    const token=sessionStorage.getItem('survey_token');
    const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body)});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error?.message||'API fixture failed');
    return result;
  },{path,method,body});
  await page.goto(origin);
  await call('/auth/register','POST',{username,password});
  const login=await call('/auth/login','POST',{username,password});
  await page.evaluate(token=>sessionStorage.setItem('survey_token',token),login.token);
  await page.reload();
  await visible('我的问卷');

  // Delay the initial create request so two submit events hit the pending-save path.
  await page.getByRole('button',{name:'新建问卷',exact:true}).click();
  await page.locator('#survey-title').fill(titleA);
  let releaseCreate,createSeen,createRequests=0;
  const createGate=new Promise(resolve=>{releaseCreate=resolve;});
  const createStarted=new Promise(resolve=>{createSeen=resolve;});
  const createPattern='**/api/surveys';
  const createHandler=async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    createRequests++;createSeen();await createGate;await route.continue();
  };
  await page.route(createPattern,createHandler);
  try{
    await page.locator('#survey-form').evaluate(form=>{form.requestSubmit();form.requestSubmit();});
    await createStarted;
    await check(page.getByRole('button',{name:'保存基本信息',exact:true}).isDisabled(),'Save must be disabled while pending');
    releaseCreate();
    await visible('问卷已保存');
    await check(Promise.resolve(createRequests===1),'Duplicate submit sent more than one create request');
    await check(page.getByRole('button',{name:'保存基本信息',exact:true}).isEnabled(),'Save did not recover after success');
  }finally{releaseCreate();await page.unroute(createPattern,createHandler);}
  const owned=await call('/surveys');
  const matches=owned.items.filter(item=>item.title===titleA);
  if(matches.length!==1)throw new Error('Expected exactly one new draft');
  const surveyA=matches[0]._id;

  // Preserve incompatible rules visibly until the author explicitly removes them.
  await page.locator('#question-id').fill('branch');
  await page.locator('#question-title').fill(textTitle);
  await page.locator('#question-options').fill('a | 结束\nb | 继续');
  await page.locator('#jump-value').fill('a');
  await page.locator('#jump-target').fill('END');
  await page.getByRole('button',{name:'加入规则',exact:true}).click();
  await page.getByRole('button',{name:'保存题目',exact:true}).click();
  await visible('1. '+textTitle);
  await page.locator('#question-list article').first().getByRole('button',{name:'编辑',exact:true}).click();
  await page.locator('#question-type').selectOption('text');
  await check(page.locator('#jump-editor').isVisible(),'Existing incompatible rule became inaccessible');
  await check(Promise.resolve(await page.locator('#jump-list .rule-row').count()===1),'Type switch silently removed the rule');
  await check(page.getByRole('button',{name:'加入规则',exact:true}).isDisabled(),'Text question must not add rules');
  await page.locator('#question-type').selectOption('single');
  await check(Promise.resolve(await page.locator('#jump-list .rule-row').count()===1),'Switching back lost the rule');
  await page.locator('#question-type').selectOption('text');
  await page.getByRole('button',{name:'保存题目',exact:true}).click();
  await visible('文本填空不支持跳转，请先移除已有规则或切回原题型。');
  await page.locator('#jump-list').getByRole('button',{name:'移除',exact:true}).click();
  await check(page.locator('#jump-editor').isHidden(),'Text editor should hide after explicit rule removal');
  await page.getByRole('button',{name:'保存题目',exact:true}).click();
  await visible('题目已保存');
  const changed=await call('/surveys/'+surveyA);
  if(changed.questions[0].type!=='text'||changed.questions[0].jumps.length)throw new Error('Explicit type change was not saved');
  await page.locator('#question-id').fill('score');
  await page.locator('#question-title').fill(numberTitle);
  await page.locator('#question-type').selectOption('number');
  await page.locator('#question-min').fill('0');
  await page.locator('#question-max').fill('10');
  await page.getByRole('button',{name:'保存题目',exact:true}).click();
  await visible('2. '+numberTitle);
  // Publishing is fixture setup here; avoid a native confirm interrupting CLI run-code.
  const draftA=await call('/surveys/'+surveyA);
  await call('/surveys/'+surveyA+'/publish','POST',{revision:draftA.revision});
  await call('/public/surveys/'+surveyA+'/responses','POST',{answers:{branch:answerA,score:7},request_id:'boundary_request_'+suffix,anonymous:false});
  const createdB=await call('/surveys','POST',{title:titleB});
  await call('/surveys/'+createdB._id+'/questions','POST',{revision:createdB.revision,question:{id:'only',title:'仅属于问卷B_'+suffix,type:'text',required:false,validation:{},jumps:[]}});

  await page.reload();
  await page.locator('#survey-list article').filter({has:page.getByRole('heading',{name:titleA,exact:true})}).getByRole('button',{name:'管理问卷',exact:true}).click();
  await page.getByRole('button',{name:'查看统计与答卷',exact:true}).click();
  await visible('共 1 份有效答卷，按答卷份数计数。');
  await check(page.locator('#response-list').innerText().then(text=>text.includes(answerA)),'Missing initial response fixture');

  // Let an old filter response arrive after the new filter has rendered.
  let releaseFilter,filterSeen;
  const filterGate=new Promise(resolve=>{releaseFilter=resolve;});
  const filterStarted=new Promise(resolve=>{filterSeen=resolve;});
  const filterUrl=origin+'/api/surveys/'+surveyA+'/questions/branch/statistics';
  const filterHandler=async route=>{filterSeen();await filterGate;await route.continue();};
  await page.route(filterUrl,filterHandler);
  try{
    await page.locator('#stats-question').selectOption('branch');await filterStarted;
    await page.locator('#stats-question').selectOption('score');
    await page.locator('#stats-content').getByRole('heading',{name:numberTitle,exact:true}).waitFor();
    const lateResponse=page.waitForResponse(response=>response.url()===filterUrl);
    releaseFilter();await(await lateResponse).finished();
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));
    await check(page.locator('#stats-content').getByRole('heading',{name:numberTitle,exact:true}).isVisible(),'Older filter overwrote the current filter');
    await check(Promise.resolve(await page.locator('#stats-content article').count()===1),'Older filter appended extra content');
  }finally{releaseFilter();await page.unroute(filterUrl,filterHandler);}

  // A different survey failing to load must not inherit A's figures or answers.
  await page.getByRole('button',{name:'← 返回问卷',exact:true}).click();
  await page.getByRole('button',{name:'← 返回问卷列表',exact:true}).click();
  await page.locator('#survey-list article').filter({has:page.getByRole('heading',{name:titleB,exact:true})}).getByRole('button',{name:'管理问卷',exact:true}).click();
  const failurePatterns=[origin+'/api/surveys/'+createdB._id+'/statistics',origin+'/api/surveys/'+createdB._id+'/responses?page=1'];
  const failureHandler=route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{message:'合成测试：加载失败'}})});
  for(const pattern of failurePatterns)await page.route(pattern,failureHandler);
  try{
    await page.getByRole('button',{name:'查看统计与答卷',exact:true}).click();
    await visible('统计加载失败，请重新选择题目或返回后重试。');
    await visible('答卷加载失败，请返回后重试。');
    await check(Promise.resolve(await page.locator('#stats-content article').count()===0),'Failed statistics retained the previous survey');
    await check(Promise.resolve(await page.locator('#response-list article').count()===0),'Failed response list retained the previous survey');
    await check(page.locator('#stats-title').innerText().then(text=>text===titleB+' · 统计'),'Wrong survey title');
  }finally{for(const pattern of failurePatterns)await page.unroute(pattern,failureHandler);}

  return {passed:true,syntheticUser:username,surveyIds:[surveyA,createdB._id],checks:['single create while saving','explicit rule removal after type switch','latest statistics filter wins','failed new survey clears old statistics and responses']};
}
