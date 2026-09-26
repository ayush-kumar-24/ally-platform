const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args:['--no-sandbox'] });
  const jobs = [
    ['hero','wide',2000,1125,'ally-hero-nyayasetu-16x9.png'],
    ['story','wide',2000,1125,'ally-story-nyayasetu-16x9.png'],
    ['story','portrait',1080,1350,'ally-story-nyayasetu-4x5.png'],
  ];
  for (const [variant,layout,w,h,out] of jobs) {
    const page = await browser.newPage({ viewport:{width:w,height:h}, deviceScaleFactor: 2 });
    await page.goto('file://' + __dirname + `/ally.html?layout=${layout}&variant=${variant}`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);
    await page.locator('#stage').screenshot({ path: out });
    console.log('wrote', out);
    await page.close();
  }
  await browser.close();
})();
