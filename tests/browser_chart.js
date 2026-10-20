// Owner signed in after browser_reference.js. The seed survey has 1 no-path + 2 yes-path responses.
async (page) => {
  const card=page.locator('#survey-list article').filter({has:page.getByRole('heading',{name:'校园服务体验问卷',exact:true})});
  await card.getByRole('button',{name:'管理问卷',exact:true}).click();
  await page.getByRole('button',{name:'查看统计与答卷',exact:true}).click();
  await page.getByText('共 3 份有效答卷，按答卷份数计数。',{exact:true}).waitFor();
  const cards=page.locator('#stats-content article');
  const row=(card,name)=>card.getByRole('row').filter({has:page.getByRole('rowheader',{name,exact:true})});
  const yes=row(cards.nth(0),'使用');
  if(!(await yes.innerText()).includes('66.7%'))throw new Error('Single denominator incorrect');
  for(const label of ['图书馆','食堂']){
    const r=row(cards.nth(1),label);
    if(!(await r.innerText()).includes('100.0%'))throw new Error('Multiple must use question answer count');
    if(await r.locator('meter').getAttribute('max')!=='2')throw new Error('Chart max should be 2, not survey count 3');
  }
  await page.getByText('平均值：4',{exact:true}).waitFor();
  await cards.nth(1).screenshot({path:'reports/images/statistics.png'});
  await page.screenshot({path:'output/playwright/reference-statistics.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile horizontal overflow');
  await page.screenshot({path:'output/playwright/reference-statistics-mobile.png',fullPage:true});
  await page.setViewportSize({width:1280,height:900});
  return {passed:true,total:3, singlePercentage:66.7,multiplePercentages:[100,100,0],average:4,mobileOverflow:false};
}
