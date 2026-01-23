import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_FILE = join(__dirname, 'profile_data.json');
const PROFILE_URL = 'https://www.linkedin.com/in/smavrov/';

async function extractPublicProfile(page) {
  console.log(`Navigating to: ${PROFILE_URL}`);

  await page.goto(PROFILE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const profile = {};

  // Check if we hit an auth wall
  const authWall = await page.locator('.authwall-join-form').count();
  if (authWall > 0) {
    console.log('Auth wall detected, trying to extract visible data...');
  }

  // Try to extract whatever is visible
  try {
    profile.name = await page.locator('h1').first().innerText({ timeout: 3000 });
  } catch { profile.name = ''; }

  try {
    profile.headline = await page.locator('.top-card-layout__headline').innerText({ timeout: 3000 });
  } catch {
    try {
      profile.headline = await page.locator('[data-section="headline"]').innerText({ timeout: 2000 });
    } catch { profile.headline = ''; }
  }

  try {
    profile.location = await page.locator('.top-card-layout__first-subline').innerText({ timeout: 3000 });
  } catch {
    try {
      profile.location = await page.locator('[data-section="location"]').innerText({ timeout: 2000 });
    } catch { profile.location = ''; }
  }

  // About/Summary
  try {
    profile.about = await page.locator('.core-section-container__content p').innerText({ timeout: 3000 });
  } catch { profile.about = ''; }

  // Experience section
  profile.experience = [];
  try {
    const expItems = await page.locator('.experience__list > li').all();
    for (const item of expItems) {
      const exp = {};
      try {
        exp.title = await item.locator('.experience-item__title').innerText({ timeout: 1000 });
      } catch { continue; }
      try {
        exp.company = await item.locator('.experience-item__subtitle').innerText({ timeout: 1000 });
      } catch { exp.company = ''; }
      try {
        exp.duration = await item.locator('.experience-item__duration').innerText({ timeout: 1000 });
      } catch { exp.duration = ''; }
      try {
        exp.description = await item.locator('.experience-item__description').innerText({ timeout: 1000 });
      } catch { exp.description = ''; }

      if (exp.title) profile.experience.push(exp);
    }
  } catch {}

  // Education
  profile.education = [];
  try {
    const eduItems = await page.locator('.education__list > li').all();
    for (const item of eduItems) {
      const edu = {};
      try {
        edu.school = await item.locator('.education__item-school').innerText({ timeout: 1000 });
      } catch { continue; }
      try {
        edu.degree = await item.locator('.education__item-degree').innerText({ timeout: 1000 });
      } catch { edu.degree = ''; }

      if (edu.school) profile.education.push(edu);
    }
  } catch {}

  // Skills
  profile.skills = [];
  try {
    const skillItems = await page.locator('.skills__list .skill-item').all();
    for (const item of skillItems) {
      try {
        const skill = await item.innerText({ timeout: 500 });
        if (skill) profile.skills.push(skill.trim());
      } catch {}
    }
  } catch {}

  return profile;
}

async function main() {
  console.log('Starting LinkedIn public profile scraper...\n');

  const browser = await chromium.launch({
    headless: false
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });

  const page = await context.newPage();

  try {
    const profileData = await extractPublicProfile(page);

    writeFileSync(OUTPUT_FILE, JSON.stringify(profileData, null, 2), 'utf-8');

    console.log(`\n✓ Profile data saved to ${OUTPUT_FILE}`);
    console.log('\nExtracted:');
    console.log(`  - Name: ${profileData.name || 'N/A'}`);
    console.log(`  - Headline: ${profileData.headline || 'N/A'}`);
    console.log(`  - Location: ${profileData.location || 'N/A'}`);
    console.log(`  - About: ${profileData.about ? 'Yes' : 'N/A'}`);
    console.log(`  - Experience: ${profileData.experience?.length || 0}`);
    console.log(`  - Education: ${profileData.education?.length || 0}`);
    console.log(`  - Skills: ${profileData.skills?.length || 0}`);

    // Take screenshot for debugging
    await page.screenshot({ path: join(__dirname, 'profile_screenshot.png'), fullPage: true });
    console.log('\n✓ Screenshot saved to profile_screenshot.png');

  } catch (e) {
    console.error('Error:', e.message);
    await page.screenshot({ path: 'error_screenshot.png' });
  } finally {
    await browser.close();
  }
}

main();
