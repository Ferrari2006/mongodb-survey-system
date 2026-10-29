// Render with the installed browser's actual Windows fonts, avoiding fontconfig fallback.
const path = require('path');
const fs = require('fs');
const {chromium} = require(process.argv[2]);
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    for (const [name,height] of [['stage2-data-flow-refined',530],['stage2-version-flow-refined',500]]) {
      const page = await browser.newPage({viewport:{width:1200,height},deviceScaleFactor:2.5});
      const base = path.resolve('第二阶段/images',name);
      await page.setContent('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+fs.readFileSync(base+'.svg','utf8'));
      await page.evaluate(() => document.fonts.ready);
      await page.locator('svg').screenshot({path:base+'.png'});
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
