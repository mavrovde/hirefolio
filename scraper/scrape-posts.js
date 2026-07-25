import { chromium } from 'playwright';
import { config } from 'dotenv';
import { writeFileSync, existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

import { parsePost } from './parse-post.js';

config();

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_FILE = join(__dirname, 'posts_data.json');
const SESSION_FILE = join(__dirname, 'session.json');
const USER_DATA_DIR = join(__dirname, '.chrome-profile');

const LINKEDIN_EMAIL = process.env.LINKEDIN_EMAIL;
const LINKEDIN_PASSWORD = process.env.LINKEDIN_PASSWORD;
const PROFILE_URL = process.env.PROFILE_URL || 'https://www.linkedin.com/in/smavrov/';
// Be gentle with LinkedIn (avoid anti-bot / account risk): cap posts per run and
// use small randomized scroll delays. Session is reused (never re-login per run).
const MAX_POSTS = parseInt(process.env.SCRAPE_MAX_POSTS || '50', 10);

async function login(page, context) {
    // Prefer the shared persistent profile session (same as scrape-linkedin.js).
    try {
        const liCookies = await context.cookies('https://www.linkedin.com');
        if (liCookies.some((c) => c.name === 'li_at' && c.value)) {
            console.log('✓ Already authenticated (persistent profile)');
            return;
        }
    } catch { }

    if (existsSync(SESSION_FILE)) {
        console.log('Restoring session...');
        const cookies = JSON.parse(readFileSync(SESSION_FILE, 'utf-8'));
        await context.addCookies(cookies);
        // Go directly to the feeds page to check auth
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
        // Randomized delay (800-1600ms) — gentler / less bot-like than a fixed cadence.
        await page.waitForTimeout(800 + Math.floor(Math.random() * 800));
    }
}

// Collect every image src under a set of locators (post media may have several).
async function collectImageSrcs(item, selector) {
    const srcs = [];
    try {
        const imgs = await item.locator(selector).all();
        for (const img of imgs) {
            const src = await img.getAttribute('src', { timeout: 500 }).catch(() => null);
            if (src) srcs.push(src);
        }
    } catch { }
    return srcs;
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

async function extractPosts(page) {
    const posts = [];

    // Find all post containers
    // Look for the main blocks in the recent activity feed
    const postLocators = await page.locator('.profile-creator-shared-feed-update__container').all();
    console.log(`Found ${postLocators.length} potential post items`);

    // Alternative fallback selector if the first one doesn't yield much
    let itemsToProcess = postLocators;
    if (itemsToProcess.length === 0) {
        itemsToProcess = await page.locator('.feed-shared-update-v2').all();
        console.log(`Fallback: Found ${itemsToProcess.length} feed update items`);
    }

    for (let i = 0; i < itemsToProcess.length && posts.length < MAX_POSTS; i++) {
        const item = itemsToProcess[i];
        try {
            const raw = { urn: '', content: '', imageCandidates: [], authorImageUrl: null, time: '' };

            // Expand truncated text ("see more") then read the post body.
            try {
                const seeMoreBtn = item.locator('.feed-shared-inline-show-more-text__see-more-less-toggle');
                if (await seeMoreBtn.count() > 0) {
                    const text = await getText(seeMoreBtn);
                    if (text.toLowerCase().includes('more')) {
                        await seeMoreBtn.click({ timeout: 1000 }).catch(() => { });
                        await page.waitForTimeout(200);
                    }
                }
                raw.content = await getText(item.locator('.update-components-text'));
                if (!raw.content) {
                    raw.content = await getText(item.locator('.feed-shared-update-v2__description-wrapper'));
                }
            } catch (e) {
                console.log(`Text extraction failed for item ${i}`, e.message);
            }

            // The author's avatar — captured ONLY so parsePost can exclude it (the
            // old scraper mistook this profile photo for the post's image).
            try {
                const avatar = item.locator('.update-components-actor__avatar img').first();
                if (await avatar.count() > 0) {
                    raw.authorImageUrl = await avatar.getAttribute('src', { timeout: 500 });
                }
            } catch { }

            // The post's OWN media (there may be several).
            raw.imageCandidates = await collectImageSrcs(
                item,
                '.update-components-image__image, .update-components-image img, .feed-shared-image img',
            );

            // URN (→ activity id, permalink and postedAt are derived in parsePost).
            try {
                raw.urn = (await item.getAttribute('data-urn', { timeout: 500 })) || '';
            } catch { }

            // Human-readable "time" string (kept alongside the derived ISO postedAt).
            try {
                const timeLocator = item.locator('.update-components-actor__sub-description .visually-hidden').first();
                if (await timeLocator.count() > 0) {
                    raw.time = await getText(timeLocator);
                }
            } catch { }

            const post = parsePost(raw);
            if (post) posts.push(post);

        } catch (e) {
            console.log(`  Error extracting post ${i}: ${e.message}`);
        }
    }

    return posts;
}

async function main() {
    if (!LINKEDIN_EMAIL || !LINKEDIN_PASSWORD) {
        console.error('Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env');
        process.exit(1);
    }

    console.log('LinkedIn Posts Scraper');
    console.log('===========================\n');

    // Parse command line arguments for number of scrolls (default to 10)
    const scrollsArg = process.argv.find(arg => arg.startsWith('--scrolls='));
    const numScrolls = scrollsArg ? parseInt(scrollsArg.split('=')[1], 10) : 10;
    console.log(`Will perform ${numScrolls} scrolls to load posts.`);

    const isHeadless = process.env.HEADLESS !== 'false';
    const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
        headless: isHeadless,
        slowMo: 30,
        channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
        viewport: { width: 1280, height: 900 },
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });
    const page = context.pages()[0] || await context.newPage();

    try {
        await login(page, context);

        const postsUrl = `${PROFILE_URL.replace(/\/$/, '')}/recent-activity/all/`;
        console.log(`\nNavigating to: ${postsUrl}`);
        await page.goto(postsUrl);
        await page.waitForTimeout(4000);

        console.log('Scrolling to load posts...');
        await scrollPage(page, numScrolls);

        const posts = await extractPosts(page);

        writeFileSync(OUTPUT_FILE, JSON.stringify(posts, null, 2), 'utf-8');

        console.log('\n========== RESULT ==========');
        console.log(`Extract ${posts.length} posts`);
        console.log(`\n✓ Saved to ${OUTPUT_FILE}`);

    } catch (e) {
        console.error('Error:', e.message);
    } finally {
        await context.close();
    }
}

main();
