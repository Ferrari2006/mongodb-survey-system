// Uses the already installed Playwright runtime; no @playwright/test runner needed.
const fs=require('fs'),path=require('path');
const {chromium}=require(process.argv[2]||'playwright');
(async()=>{
  fs.mkdirSync('output/playwright',{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    const flow=eval('('+fs.readFileSync(path.join(__dirname,'browser_library.js'),'utf8')+')');
    const result=await flow(page);
    result.executed_at_utc=new Date().toISOString();
    fs.writeFileSync('tests/results/stage2-browser.json',JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
