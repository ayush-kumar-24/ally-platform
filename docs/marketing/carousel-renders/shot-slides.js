
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args:['--no-sandbox'] });
  const page = await browser.newPage({ viewport:{width:1200,height:1500}, deviceScaleFactor: 2 });
  await page.goto('file://' + __dirname + '/slides.html');
  await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(400);
  for (let n=1;n<=6;n++){ await page.locator('#s'+n).screenshot({ path: `slide-0${n}.png` }); console.log('slide',n); }
  await browser.close();
})();