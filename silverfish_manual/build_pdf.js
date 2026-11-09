// manual.html을 A4 PDF로 변환합니다.
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.join(__dirname, 'manual.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: path.join(__dirname, '좀벌레_퇴치_가정용_매뉴얼.pdf'),
    format: 'A4',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="width:100%;text-align:center;font-size:8pt;color:#888;font-family:NanumBarunGothic;">좀벌레 퇴치 가정용 매뉴얼 · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  });
  await browser.close();
})();
