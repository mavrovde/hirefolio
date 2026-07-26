import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Verifies the public site renders the profile served by the backend
 * (`GET /api/app/profile?lang=…`), and that a raw scraper JSON which omits
 * site-enriched fields (contact / recommendations) still renders cleanly.
 */
test.describe('Public profile display (from backend)', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/*analytics*', (route) => route.abort());
    await page.route('**/*googletagmanager*', (route) => route.abort());
    await page.addInitScript(() => window.localStorage.setItem('cookie_consent', 'true'));
    page.on('console', (msg) => console.log('BROWSER LOG:', msg.text()));
  });

  test('renders the backend profile in the hero', async ({ page }) => {
    const profile = {
      name: 'E2E Backend User',
      headline: 'Served from the database',
      location: 'Aachen',
      about: 'Loaded via /api/app/profile',
      experience: [],
      education: [],
      skills: ['Playwright'],
      certifications: [],
      languages: [],
      recommendations: [],
      contact: { email: 'e2e@example.com', linkedin: 'https://linkedin.com/in/e2e' },
    };

    await page.route(`**${API_PREFIX}/profile*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(profile),
      });
    });

    await page.goto('/');
    await expect(page.locator('text=E2E Backend User').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Served from the database').first()).toBeVisible();
  });

  test('renders cleanly when the scraper JSON omits contact and recommendations', async ({
    page,
  }) => {
    // A minimal raw scraper payload: no contact, no recommendations, no certs.
    const minimal = {
      name: 'Minimal Profile',
      headline: 'Only core fields',
      location: '',
      about: 'No contact block here',
      experience: [],
      education: [],
      skills: ['Resilience'],
    };

    await page.route(`**${API_PREFIX}/profile*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(minimal),
      });
    });

    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));

    await page.goto('/');
    await expect(page.locator('text=Minimal Profile').first()).toBeVisible({ timeout: 15000 });
    // The contact section guards on profile.contact, so its mailto link is absent.
    await expect(page.locator('a[href^="mailto:"]')).toHaveCount(0);
    // No client-side error from iterating absent arrays.
    expect(errors, `page errors: ${errors.join('; ')}`).toHaveLength(0);
  });
});
