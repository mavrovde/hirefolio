import { chromium } from 'playwright';
import { config } from 'dotenv';
import { writeFileSync, existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

config();

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_FILE = join(__dirname, 'profile_data.json');
const SESSION_FILE = join(__dirname, 'session.json');

const LINKEDIN_EMAIL = process.env.LINKEDIN_EMAIL;
const LINKEDIN_PASSWORD = process.env.LINKEDIN_PASSWORD;
const PROFILE_URL = process.env.PROFILE_URL || 'https://www.linkedin.com/in/smavrov/';

async function login(page, context) {
  if (existsSync(SESSION_FILE)) {
    console.log('Restoring session...');
    const cookies = JSON.parse(readFileSync(SESSION_FILE, 'utf-8'));
    await context.addCookies(cookies);
    await page.goto('https://www.linkedin.com/feed/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    if (page.url().includes('/feed')) {
      console.log('✓ Session restored');
      return;
    }
  }

  console.log('Logging in...');
  await page.goto('https://www.linkedin.com/login');
  await page.waitForTimeout(1000);
  await page.fill('input[name="session_key"]', LINKEDIN_EMAIL);
  await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD);
  await page.click('button[type="submit"]');

  const maxWait = 180000;
  const startTime = Date.now();
  while (Date.now() - startTime < maxWait) {
    if (page.url().includes('/feed')) {
      const cookies = await context.cookies();
      writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
      console.log('✓ Logged in & session saved');
      return;
    }
    if (page.url().includes('checkpoint') || page.url().includes('challenge')) {
      console.log('⚠️  Complete MFA in browser...');
    }
    await page.waitForTimeout(1000);
  }
  throw new Error('Login timeout');
}

async function scrollPage(page, times = 5) {
  for (let i = 0; i < times; i++) {
    await page.evaluate(() => window.scrollBy(0, 1000));
    await page.waitForTimeout(500);
  }
}

// Get text from first matching element safely
async function getText(locator, timeout = 1000) {
  try {
    if (await locator.count() > 0) {
      return (await locator.first().innerText({ timeout })).trim();
    }
  } catch { }
  return '';
}

// Get all texts from matching elements
async function getAllTexts(locator, timeout = 500) {
  try {
    const elements = await locator.all();
    const texts = [];
    for (const el of elements) {
      const txt = (await el.innerText({ timeout }).catch(() => '')).trim();
      if (txt) texts.push(txt);
    }
    return texts;
  } catch { }
  return [];
}

function deduplicate(arr, key) {
  const seen = new Set();
  return arr.filter(item => {
    const k = typeof key === 'function' ? key(item) : item[key];
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

// Parse duration string like "Mar 2025 - Present · 11 mos" into separate fields
function parseDuration(durationStr) {
  if (!durationStr) return {};

  const result = {};

  // Split by · to get date range and duration
  const parts = durationStr.split(' · ');
  if (parts.length >= 2) {
    result.durationText = parts[1].trim();
  }

  // Parse the date range (first part)
  const dateRange = parts[0].trim();
  const dateParts = dateRange.split(' - ');
  if (dateParts.length >= 2) {
    result.startDate = dateParts[0].trim();
    result.endDate = dateParts[1].trim();
  } else if (dateParts.length === 1) {
    result.startDate = dateParts[0].trim();
  }

  return result;
}

// Parse company string like "adesso SE · Full-time" into company name and employment type
function parseCompany(companyStr) {
  if (!companyStr) return {};

  const result = {};

  // Split by · to get company and employment type
  const parts = companyStr.split(' · ');
  result.company = parts[0].trim();
  if (parts.length >= 2) {
    result.employmentType = parts[1].trim();
  }

  return result;
}

// Parse location string like "Hamburg, Germany · Remote" into location and work type
function parseLocation(locationStr) {
  if (!locationStr) return {};

  const result = {};
  const workTypes = ['Remote', 'Hybrid', 'On-site', 'Onsite'];

  // Split by · to check for work type
  const parts = locationStr.split(' · ');

  // Check each part for work type
  for (let i = parts.length - 1; i >= 0; i--) {
    const part = parts[i].trim();
    if (workTypes.some(wt => part.toLowerCase() === wt.toLowerCase())) {
      result.workType = part;
      parts.splice(i, 1); // Remove work type from parts
    }
  }

  // Remaining parts are the location
  if (parts.length > 0) {
    result.location = parts.join(' · ').trim();
  }

  return result;
}

async function extractProfile(page) {
  console.log(`\nNavigating to: ${PROFILE_URL}`);
  await page.goto(PROFILE_URL);
  await page.waitForTimeout(3000);

  const profile = {};

  // ==================== BASIC INFO ====================
  console.log('Extracting basic info...');
  profile.name = await getText(page.locator('h1'));
  profile.headline = await getText(page.locator('.text-body-medium'));
  profile.location = await getText(page.locator('span.text-body-small.inline.t-black--light'));

  // Scroll to load sections
  await scrollPage(page, 8);

  // ==================== ABOUT ====================
  console.log('Extracting About...');
  profile.about = '';
  try {
    const aboutSection = page.locator('section:has(#about)');
    if (await aboutSection.count() > 0) {
      // Click see more if exists to expand
      const seeMoreBtn = aboutSection.locator('button.inline-show-more-text__button');
      if (await seeMoreBtn.count() > 0) {
        await seeMoreBtn.click({ timeout: 2000 }).catch(() => { });
        await page.waitForTimeout(500);
      }

      // Try multiple selectors in order of preference
      const selectors = [
        'div[class*="inline-show-more-text"] span[aria-hidden="true"]',
        '.display-flex.ph5 span[aria-hidden="true"]',
        '.full-width span[aria-hidden="true"]',
      ];

      for (const sel of selectors) {
        try {
          const el = aboutSection.locator(sel).first();
          if (await el.count() > 0) {
            const txt = await el.innerText({ timeout: 2000 });
            // Make sure we got actual About text (not just "About" header)
            if (txt && txt.length > 50 && !txt.toLowerCase().startsWith('about')) {
              profile.about = txt.trim();
              break;
            }
          }
        } catch { }
      }
    }
  } catch (e) {
    console.log(`  About section error: ${e.message}`);
  }

  // ==================== EXPERIENCE ====================
  console.log('Extracting Experience...');
  profile.experience = [];
  try {
    await page.goto(PROFILE_URL + 'details/experience/');
    await page.waitForTimeout(4000);
    await scrollPage(page, 8);

    // Updated selector: use scaffold-finite-scroll__content
    const items = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${items.length} experience items`);

    for (const item of items) {
      const exp = {};

      // Title (bold text)
      exp.title = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      // Get all normal texts (company, duration info)
      const normalTexts = await getAllTexts(item.locator(':scope > div .t-14.t-normal span[aria-hidden="true"]'));
      if (normalTexts.length >= 1) {
        // Parse company into name and employment type
        const companyData = parseCompany(normalTexts[0]);
        exp.company = companyData.company;
        if (companyData.employmentType) exp.employmentType = companyData.employmentType;
      }

      // Get light texts (duration, location)
      const lightTexts = await getAllTexts(item.locator(':scope > div .t-14.t-normal.t-black--light span[aria-hidden="true"], :scope > div .pvs-entity__caption-wrapper[aria-hidden="true"]'));
      if (lightTexts.length >= 1) {
        // Parse duration into start, end, and duration text
        const durationData = parseDuration(lightTexts[0]);
        if (durationData.startDate) exp.startDate = durationData.startDate;
        if (durationData.endDate) exp.endDate = durationData.endDate;
        if (durationData.durationText) exp.duration = durationData.durationText;
      }
      if (lightTexts.length >= 2) {
        // Parse location into location and work type
        const locationData = parseLocation(lightTexts[1]);
        if (locationData.location) exp.location = locationData.location;
        if (locationData.workType) exp.workType = locationData.workType;
      }

      // Get description from sub-components (longer text blocks)
      try {
        const descEl = item.locator('.pvs-entity__sub-components .t-14.t-normal.t-black span[aria-hidden="true"]');
        const descTexts = await getAllTexts(descEl, 2000);
        for (const txt of descTexts) {
          if (txt.startsWith('Skills:')) {
            // Convert skills string to array
            const skillsStr = txt.replace('Skills:', '').trim();
            exp.skills = skillsStr.split(' · ').map(s => s.trim()).filter(s => s.length > 0);
          } else if (txt.length > 80 && !exp.description) {
            exp.description = txt;
          }
        }
      } catch { }

      // Also check for skills in the entire item (they may be outside sub-components)
      try {
        const allTexts = await getAllTexts(item.locator('span[aria-hidden="true"]'));
        for (const txt of allTexts) {
          if (txt.startsWith('Skills:') && !exp.skills) {
            const skillsStr = txt.replace('Skills:', '').trim();
            exp.skills = skillsStr.split(' · ').map(s => s.trim()).filter(s => s.length > 0);
            break;
          }
        }
      } catch { }

      // Extract company LinkedIn URL
      try {
        const companyLink = item.locator('a[href*="/company/"]').first();
        if (await companyLink.count() > 0) {
          const href = await companyLink.getAttribute('href', { timeout: 500 });
          if (href) {
            exp.companyLinkedInUrl = href.startsWith('http') ? href : 'https://www.linkedin.com' + href;
          }
        }
      } catch { }

      if (exp.title && exp.company) {
        profile.experience.push(exp);
      }
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== EDUCATION ====================
  console.log('Extracting Education...');
  profile.education = [];
  try {
    await page.goto(PROFILE_URL + 'details/education/');
    await page.waitForTimeout(4000);
    await scrollPage(page, 3);

    const eduItems = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${eduItems.length} education items`);

    for (const item of eduItems) {
      const edu = {};
      edu.school = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      const normalTexts = await getAllTexts(item.locator('.t-14.t-normal span[aria-hidden="true"]'));
      if (normalTexts.length >= 1) edu.degree = normalTexts[0];
      if (normalTexts.length >= 2) edu.years = normalTexts[1];

      // Activities
      const lightTexts = await getAllTexts(item.locator('.t-14.t-normal.t-black--light span[aria-hidden="true"]'));
      for (const txt of lightTexts) {
        if (txt.startsWith('Activities')) {
          edu.activities = txt;
          break;
        }
      }

      // Get skills from sub-components
      try {
        const subTexts = await getAllTexts(item.locator('.pvs-entity__sub-components span[aria-hidden="true"]'));
        for (const txt of subTexts) {
          if (txt.startsWith('Skills:')) {
            edu.skills = txt.replace('Skills:', '').trim();
          }
        }
      } catch { }

      if (edu.school) profile.education.push(edu);
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== SKILLS ====================
  console.log('Extracting Skills...');
  profile.skills = [];
  try {
    await page.goto(PROFILE_URL + 'details/skills/');
    await page.waitForTimeout(4000);
    await scrollPage(page, 10);

    // Get all skill names - they are in bold text within list items
    const skillItems = await page.locator('main .scaffold-finite-scroll__content li .t-bold span[aria-hidden="true"]').all();
    console.log(`  Found ${skillItems.length} skill elements`);

    for (const item of skillItems) {
      const skill = (await item.innerText({ timeout: 500 }).catch(() => '')).trim();
      if (skill && skill.length < 100 && !profile.skills.includes(skill)) {
        profile.skills.push(skill);
      }
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== CERTIFICATIONS ====================
  console.log('Extracting Certifications...');
  profile.certifications = [];
  try {
    await page.goto(PROFILE_URL + 'details/certifications/');
    await page.waitForTimeout(4000);
    await scrollPage(page, 5);

    const certItems = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${certItems.length} certification items`);

    for (const item of certItems) {
      const cert = {};
      cert.name = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      const normalTexts = await getAllTexts(item.locator('.t-14.t-normal span[aria-hidden="true"]'));
      if (normalTexts.length >= 1) cert.issuer = normalTexts[0];
      if (normalTexts.length >= 2) cert.date = normalTexts[1];

      // Extract credential URL ("Show credential" link)
      try {
        const credentialLink = item.locator('a[href*="credly"], a[href*="credential"], a:has-text("Show credential"), a[aria-label*="credential"]');
        if (await credentialLink.count() > 0) {
          cert.credentialUrl = await credentialLink.first().getAttribute('href', { timeout: 500 });
        }
      } catch { }

      // Also try to get the external link from the item
      try {
        const externalLink = item.locator('a[target="_blank"][href^="http"]');
        if (await externalLink.count() > 0 && !cert.credentialUrl) {
          cert.credentialUrl = await externalLink.first().getAttribute('href', { timeout: 500 });
        }
      } catch { }

      if (cert.name) profile.certifications.push(cert);
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== LANGUAGES ====================
  console.log('Extracting Languages...');
  profile.languages = [];
  try {
    await page.goto(PROFILE_URL + 'details/languages/');
    await page.waitForTimeout(4000);

    const langItems = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${langItems.length} language items`);

    for (const item of langItems) {
      const lang = {};
      lang.name = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      const normalTexts = await getAllTexts(item.locator('.t-14.t-normal span[aria-hidden="true"]'));
      if (normalTexts.length >= 1) lang.proficiency = normalTexts[0];

      if (lang.name) profile.languages.push(lang);
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== PROJECTS ====================
  console.log('Extracting Projects...');
  profile.projects = [];
  try {
    await page.goto(PROFILE_URL + 'details/projects/');
    await page.waitForTimeout(4000);

    const projItems = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${projItems.length} project items`);

    for (const item of projItems) {
      const proj = {};
      proj.name = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      const normalTexts = await getAllTexts(item.locator('.t-14.t-normal span[aria-hidden="true"]'));
      if (normalTexts.length >= 1) proj.date = normalTexts[0];

      // Description
      try {
        const descTexts = await getAllTexts(item.locator('.pvs-entity__sub-components span[aria-hidden="true"]'));
        for (const txt of descTexts) {
          if (txt.length > 30) {
            proj.description = txt;
            break;
          }
        }
      } catch { }

      if (proj.name) profile.projects.push(proj);
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== RECOMMENDATIONS (RECEIVED ONLY) ====================
  console.log('Extracting Recommendations...');
  profile.recommendations = [];
  try {
    // Go to recommendations page
    await page.goto(PROFILE_URL + 'details/recommendations/');
    await page.waitForTimeout(3000);

    // Explicitly click "Received" tab to be sure
    try {
      const receivedTab = page.locator('button[role="tab"]:has-text("Received")');
      if (await receivedTab.count() > 0) {
        console.log('Clicking "Received" tab...');
        await receivedTab.click();
        await page.waitForTimeout(3000);
      }
    } catch (e) {
      console.log('Could not click Received tab: ' + e.message);
    }

    await scrollPage(page, 5);

    // Expand all recommendations
    const expandBtns = await page.locator('button.inline-show-more-text__button').all();
    for (const btn of expandBtns.slice(0, 20)) {
      await btn.click({ timeout: 300 }).catch(() => { });
    }
    await page.waitForTimeout(1000);

    const recItems = await page.locator('main .scaffold-finite-scroll__content > ul > li.pvs-list__paged-list-item').all();
    console.log(`  Found ${recItems.length} recommendation items`);

    for (const item of recItems) {
      const rec = {};
      rec.author = await getText(item.locator('.t-bold span[aria-hidden="true"]'));

      // Get author's title
      const normalTexts = await getAllTexts(item.locator('.t-14.t-normal span[aria-hidden="true"]'));
      for (const txt of normalTexts) {
        if (txt.length > 10 && !txt.includes('· 1st') && !txt.includes('received')) {
          rec.authorTitle = txt;
          break;
        }
      }

      // Get author's LinkedIn profile URL
      try {
        const authorLink = item.locator('a[href*="/in/"]').first();
        if (await authorLink.count() > 0) {
          const href = await authorLink.getAttribute('href', { timeout: 500 });
          if (href) {
            rec.authorLinkedInUrl = href.startsWith('http') ? href : 'https://www.linkedin.com' + href;
          }
        }
      } catch { }

      // Get recommendation text - try multiple selectors
      try {
        // Try visually-hidden first (full expanded text)
        const hiddenText = await item.locator('.pv-shared-text-with-see-more span.visually-hidden').first().innerText({ timeout: 1000 }).catch(() => '');
        if (hiddenText && hiddenText.length > 50) {
          rec.text = hiddenText.trim();
        }

        // Fallback: try inline-show-more-text
        if (!rec.text) {
          const inlineText = await item.locator('div[class*="inline-show-more-text"] span[aria-hidden="true"]').first().innerText({ timeout: 1000 }).catch(() => '');
          if (inlineText && inlineText.length > 50) {
            rec.text = inlineText.trim();
          }
        }

        // Fallback: try any long text in the item
        if (!rec.text) {
          const allTexts = await getAllTexts(item.locator('span[aria-hidden="true"]'));
          for (const txt of allTexts) {
            if (txt.length > 100 && !txt.includes(rec.author) && !txt.includes(rec.authorTitle || '')) {
              rec.text = txt;
              break;
            }
          }
        }
      } catch { }

      // Include recommendations with author (text is optional but preferred)
      if (rec.author && rec.text) {
        // Safety check 1: Author is not profile owner
        if (rec.author === profile.name) return;

        // Safety check 2: Heuristic to detect "Given" recommendations
        // In "Given" list, the name shown is the recipient (e.g., "David Green")
        // but the text praises them ("David is great").
        // Received recommendations praise the profile owner ("Sergii is great").

        const textLower = rec.text.toLowerCase();
        const authorFirst = rec.author.split(' ')[0].toLowerCase();

        // Define profile owner name variations
        const ownerNames = ['sergii', 'sergey', 'sergei', 'mavrov'];
        const mentionsOwner = ownerNames.some(n => textLower.includes(n));
        const mentionsAuthor = textLower.includes(authorFirst);

        // If it mentions the "author" (recipient) but NOT the owner, it's likely "Given"
        if (mentionsAuthor && !mentionsOwner) {
          // console.log(`  Skipping "Given" recommendation for: ${rec.author}`);
          continue; // Skip this one
        }

        // Safety check 3: Exclude pending requests and "ask for recommendation" messages
        if (rec.text.includes('Pending') ||
          rec.text.includes('Request sent') ||
          rec.authorTitle?.includes('Pending') ||
          rec.text.includes('linkedin.com/recs/give')) {
          // console.log(`  Skipping request/pending item for: ${rec.author}`);
          continue;
        }

        profile.recommendations.push(rec);
      }
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }

  // ==================== DEDUPLICATE ====================
  profile.experience = deduplicate(profile.experience, item => item.title + '|' + item.company);
  profile.education = deduplicate(profile.education, 'school');
  profile.certifications = deduplicate(profile.certifications, 'name');
  profile.recommendations = deduplicate(profile.recommendations, 'author');

  return profile;
}

async function main() {
  if (!LINKEDIN_EMAIL || !LINKEDIN_PASSWORD) {
    console.error('Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env');
    process.exit(1);
  }

  console.log('LinkedIn Profile Scraper v3');
  console.log('===========================\n');

  const isHeadless = process.env.HEADLESS !== 'false';
  const browser = await chromium.launch({ headless: isHeadless, slowMo: 30 });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  const page = await context.newPage();

  try {
    await login(page, context);
    const profile = await extractProfile(page);

    writeFileSync(OUTPUT_FILE, JSON.stringify(profile, null, 2), 'utf-8');

    console.log('\n========== RESULT ==========');
    console.log(`Name: ${profile.name}`);
    console.log(`Headline: ${profile.headline?.substring(0, 50)}...`);
    console.log(`Location: ${profile.location}`);
    console.log(`About: ${profile.about ? profile.about.length + ' chars' : 'No'}`);
    console.log(`Experience: ${profile.experience.length}`);
    console.log(`Education: ${profile.education.length}`);
    console.log(`Skills: ${profile.skills.length}`);
    console.log(`Certifications: ${profile.certifications.length}`);
    console.log(`Languages: ${profile.languages.length}`);
    console.log(`Projects: ${profile.projects.length}`);
    console.log(`Recommendations: ${profile.recommendations.length}`);
    console.log(`\n✓ Saved to ${OUTPUT_FILE}`);

  } catch (e) {
    console.error('Error:', e.message);
  } finally {
    await browser.close();
  }
}

main();
