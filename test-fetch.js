const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    // Route console messages to terminal
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', error => console.log('BROWSER ERROR:', error.message));
    page.on('requestfailed', request => console.log('REQUEST FAILED:', request.url(), request.failure().errorText));

    console.log('Navigating to login...');
    await page.goto('http://localhost:4200/admin/login');

    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    await page.waitForTimeout(2000);
    console.log('Navigating to LinkedIn Admin...');
    await page.goto('http://localhost:4200/admin/linkedin');
    await page.waitForTimeout(2000);

    console.log('Clicking Fetch...');
    await page.click('text=Fetch Posts');

    await page.waitForTimeout(10000);
    console.log('Done.');
    await browser.close();
})();
