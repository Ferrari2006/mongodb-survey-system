// Playwright CLI run-code, after opening seed_demo.py URL with ?reader=<respondent>.
async (page) => {
  const start = new URL(page.url());
  const reader = start.searchParams.get('reader');
  if (!reader || !reader.startsWith('demo_reader_')) throw new Error('Use synthetic seed reader in URL');
  const share = start.origin + start.pathname;
  const visible = text => page.getByText(text,{exact:true}).waitFor({state:'visible'});
  await page.getByRole('textbox',{name:'用户名',exact:true}).fill(reader);
  await page.getByRole('textbox',{name:'密码',exact:true}).fill('Demo-only-123');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.getByRole('radio',{name:'使用',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await page.getByRole('checkbox',{name:'图书馆',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await visible('满意度评分（0～10整数）（必答）');
  await visible('请输入整数，最小 0，最大 10。');
  await page.reload();
  await visible('满意度评分（0～10整数）（必答）');
  await page.getByRole('spinbutton',{name:'填写答案',exact:true}).fill('0');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await visible('你的建议（可不填）（选答）');
  for (const title of ['满意度评分（0～10整数）（必答）','你使用哪些服务？（至少1项）（必答）','你是否使用校园服务？（必答）']) {
    await page.getByRole('button',{name:'上一题',exact:true}).click();
    await visible(title);
  }
  await page.getByRole('radio',{name:'不使用',exact:true}).check();
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await visible('你的建议（可不填）（选答）');
  await page.reload();
  await visible('你的建议（可不填）（选答）');
  await page.getByRole('textbox',{name:'填写答案',exact:true}).fill('刷新恢复及切换分支测试');
  await page.getByRole('button',{name:'下一题',exact:true}).click();
  await visible('回答已完成，请确认提交');
  await page.getByRole('checkbox',{name:'匿名提交（对创建者隐藏账号）',exact:true}).check();
  await visible('匿名设置及已确认进度已保存。');
  await page.reload();
  await visible('回答已完成，请确认提交');
  if (!await page.getByRole('checkbox',{name:'匿名提交（对创建者隐藏账号）',exact:true}).isChecked()) throw new Error('Anonymous preference lost');
  await page.getByRole('button',{name:'提交问卷',exact:true}).click();
  await visible('提交成功，感谢填写');
  await page.goto(share);
  await visible('你是否使用校园服务？（必答）');
  await page.getByRole('button',{name:'退出',exact:true}).click();
  await page.getByRole('textbox',{name:'用户名',exact:true}).fill(reader.replace('demo_reader_','demo_owner_'));
  await page.getByRole('textbox',{name:'密码',exact:true}).fill('Demo-only-123');
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await page.locator('#identity').getByText(reader.replace('demo_reader_','demo_owner_'),{exact:false}).waitFor();
  await page.goto(start.origin);
  await page.getByRole('button',{name:'管理问卷',exact:true}).click();
  await page.getByRole('button',{name:'查看统计与答卷',exact:true}).click();
  await visible('共 1 份有效答卷，按答卷份数计数。');
  const stats = await page.locator('#stats-content').innerText();
  if (!stats.includes('不使用：1') || !stats.includes('平均值：暂无数据')) throw new Error('Hidden branch polluted statistics');
  if (!(await page.locator('#response-list').innerText()).includes('匿名')) throw new Error('Anonymous result missing');
  const responseText=await page.locator('#response-list').innerText();
  if (!responseText.includes('你是否使用校园服务？：不使用') || responseText.includes('question_id')) throw new Error('Answers must show titles and option labels');
  return {passed:true, checks:['refresh','zero','backtracking','branch cleanup','anonymous restore','submit cleanup','repeat fresh start','statistics']};
}
