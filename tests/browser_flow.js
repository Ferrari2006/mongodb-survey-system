// Run via Playwright CLI run-code after seed_demo.py and opening its share URL.
// Replace the synthetic names below if using a newly generated demo.
async (page) => {
  const base = 'http://127.0.0.1:5052';
  const share = base + '/survey/863f40087d804ad3a4afb28c7e762080';
  const password = 'Demo-only-123';
  const login = async name => {
    await page.getByRole('textbox', {name:'用户名',exact:true}).fill(name);
    await page.getByRole('textbox', {name:'密码',exact:true}).fill(password);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await page.locator('#identity').getByText(name,{exact:false}).waitFor();
  };
  const waitText = async text => {
    await page.getByText(text,{exact:true}).waitFor({state:'visible'});
  };
  await page.goto(share);
  await login('demo_reader_38a5fb');
  await page.getByRole('radio',{name:'不使用',exact:true}).waitFor();
  await page.getByRole('radio',{name:'不使用',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('你的建议（可不填）（选答）');
  if (await page.getByText('满意度评分（0～10整数）（必答）',{exact:true}).isVisible()) throw new Error('Branch did not skip numeric question');
  await page.getByRole('textbox',{name:'填写答案',exact:true}).fill('希望延长开放时间');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('回答已完成，请确认提交');
  await page.getByRole('checkbox',{name:'匿名提交（对创建者隐藏账号）',exact:true}).check();
  await page.getByRole('button',{name:'提交问卷',exact:true}).click();
  await waitText('提交成功，感谢填写');
  await page.goto(share);
  await page.getByRole('radio',{name:'使用',exact:true}).waitFor();
  await page.getByRole('radio',{name:'使用',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await page.getByRole('checkbox',{name:'图书馆',exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'图书馆',exact:true}).check();
  await page.getByRole('checkbox',{name:'食堂',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('满意度评分（0～10整数）（必答）');
  await page.getByRole('spinbutton',{name:'填写答案',exact:true}).fill('11');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('数字不在允许范围内');
  await page.getByRole('spinbutton',{name:'填写答案',exact:true}).fill('8');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('你的建议（可不填）（选答）');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await waitText('回答已完成，请确认提交');
  await page.getByRole('button',{name:'提交问卷',exact:true}).click();
  await waitText('提交成功，感谢填写');
  await page.getByRole('button',{name:'退出',exact:true}).click();
  await login('demo_owner_38a5fb');
  // A share link keeps its purpose after login; go to the workbench for ownership management.
  await page.goto(base);
  await page.getByRole('button',{name:'管理问卷',exact:true}).click();
  await page.getByRole('button',{name:'查看统计与答卷',exact:true}).click();
  await waitText('共 2 份有效答卷，按答卷份数计数。');
  await waitText('平均值：8');
  const answers = await page.locator('#response-list').innerText();
  if (!answers.includes('匿名') || !answers.includes('demo_reader_38a5fb')) throw new Error('Missing anonymous or named response');
  await page.screenshot({path:'output/playwright/stage1-statistics.png',fullPage:true});
  const options = await page.locator('#stats-question option').allTextContents();
  await page.locator('#stats-question').selectOption('q3');
  await page.waitForFunction(() => document.querySelectorAll('#stats-content article').length===1);
  await waitText('平均值：8');
  console.log(JSON.stringify({result:'passed',responses:2,average:8,questionFilterOptions:options.length,
    paths:['single jump to q4','normal q1 q2 q3 q4'],anonymous:true,named:true,numericInvalidRejected:true}));
}
