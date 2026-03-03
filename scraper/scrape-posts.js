import { chromium } from 'playwright';
import { config } from 'dotenv';
import { writeFileSync, existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

config();

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_FILE = join(__dirname, 'posts_data.json');
const SESSION_FILE = join(__dirname, 'session.json');

const LINKEDIN_EMAIL = process.env.LINKEDIN_EMAIL;
const LINKEDIN_PASSWORD = process.env.LINKEDIN_PASSWORD;
const PROFILE_URL = process.env.PROFILE_URL || 'https://www.linkedin.com/in/smavrov/';

async function login(page, context) {
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
        await page.waitForTimeout(1000);
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

    for (let i = 0; i < itemsToProcess.length; i++) {
        const item = itemsToProcess[i];
        try {
            const post = {
                id: `post-${i}`
            };

            // Extract post text/content
            try {
                // Find the "see more" button if it exists within this post and click it
                const seeMoreBtn = item.locator('.feed-shared-inline-show-more-text__see-more-less-toggle');
                if (await seeMoreBtn.count() > 0) {
                    // check if it's "see more" or "see less", if it's "see more" click it.
                    const text = await getText(seeMoreBtn);
                    if (text.toLowerCase().includes('more')) {
                        await seeMoreBtn.click({ timeout: 1000 }).catch(() => { });
                        await page.waitForTimeout(200);
                    }
                }

                post.content = await getText(item.locator('.update-components-text'));
                if (!post.content) {
                    // fallback
                    post.content = await getText(item.locator('.feed-shared-update-v2__description-wrapper'));
                }
            } catch (e) {
                console.log(`Text extraction failed for item ${i}`, e.message);
            }

            // Extract image URL
            try {
                const imgLocator = item.locator('.update-components-image__image, .ivm-view-attr__img--centered').first();
                if (await imgLocator.count() > 0) {
                    post.imageUrl = await imgLocator.getAttribute('src', { timeout: 1000 });
                }
            } catch { }

            // Extract post URL/urn if possible
            try {
                // Try getting it from the urn
                const urn = await item.getAttribute('data-urn', { timeout: 500 });
                if (urn) {
                    post.urn = urn;
                    // A basic standard share url
                    const activityId = urn.split(':').pop();
                    if (activityId) {
                        post.url = `https://www.linkedin.com/feed/update/urn:li:activity:${activityId}/`;
                    }
                }
            } catch { }

            // Get the Date/Time posted
            try {
                const timeLocator = item.locator('.update-components-actor__sub-description .visually-hidden').first();
                if (await timeLocator.count() > 0) {
                    post.time = await getText(timeLocator);
                }
            } catch { }

            // Only add to list if it actually has content
            if (post.content && post.content.length > 5) {
                posts.push(post);
            }

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
    const browser = await chromium.launch({ headless: isHeadless, slowMo: 30 });
    const context = await browser.newContext({
        viewport: { width: 1280, height: 900 },
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });
    const page = await context.newPage();

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
        await browser.close();
    }
}

main();
