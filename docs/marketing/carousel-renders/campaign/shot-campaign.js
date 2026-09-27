
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args:['--no-sandbox'] });
  const page = await browser.newPage({ viewport:{width:1200,height:1500}, deviceScaleFactor: 2 });
  await page.goto('file://' + __dirname + '/campaign.html');
  await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(400);
  for (let n=1;n<=7;n++){ await page.locator('#s'+n).screenshot({ path: `campaign-0${n}.png` }); }
  await browser.close(); console.log('done');
})();