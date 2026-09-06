import { test, expect } from '@playwright/test';

/**
 * Hire-me CTA + availability indicator (#271, AC5 of #69, split by review).
 * The criterion's own words: "Public site renders the indicator + hire-me CTA
 * linked to the contact form (SSR + hydrated, zoneless-safe); E2E asserts the
 * CTA renders." Runs against the composed stack; the backend serves the real
 * /config/site with the seeded default ('listening').
 */
test.describe('Availability indicator + hire-me CTA', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            window.localStorage.setItem('cookie_consent', 'true');
        });
    });

    test('renders the indicator and the CTA on the hero', async ({ page }) => {
        await page.goto('/');
        const indicator = page.getByTestId('availability');
        await expect(indicator).toBeVisible();
        // The default state, translated — never the raw i18n key.
        await expect(indicator).toContainText(/Listening to offers|Offen für Gespräche/);
        await expect(indicator).not.toContainText('AVAILABILITY.');

        const cta = page.getByTestId('hire-me-cta');
        await expect(cta).toBeVisible();
        await expect(cta).not.toContainText('SECTION.HIRE_ME');
    });

    test('the CTA scrolls to the contact form', async ({ page }) => {
        await page.goto('/');
        await page.getByTestId('hire-me-cta').click();
        // The contact section must end up in view — the whole point of the CTA.
        await expect(page.locator('#contact')).toBeInViewport();
    });

    test('flipping the state in the admin API changes the public hero', async ({ page, request }) => {
        // NOT route-mocked: /config/site is fetched SERVER-side and
        // transfer-cached, so a browser-side route never sees the request
        // (measured — the mock was silently unused). This is the real flow:
        // admin PUT -> public page. Serial worker + finally-restore keep the
        // shared backend clean for other specs.
        const backend = process.env['BACKEND_URL'] || 'http://localhost:8000';
        const login = await request.post(`${backend}/api/app/auth/login`, {
            form: { username: 'admin', password: 'admin123' },
        });
        test.skip(!login.ok(), 'admin login unavailable on this stack');
        const token = (await login.json()).access_token;
        const put = await request.put(
            `${backend}/api/app/admin/site-settings/availability`,
            { headers: { Authorization: `Bearer ${token}` }, data: { value: 'open' } },
        );
        // A pre-#271 backend image has no such route — skip VISIBLY rather
        // than fake-green; CI builds the branch, so it runs for real there.
        test.skip(put.status() === 404, 'backend image predates #271');
        expect(put.ok()).toBe(true);
        try {
            await page.goto('/');
            await expect(page.getByTestId('availability')).toContainText(
                /Open to offers|Offen für Angebote/,
            );
        } finally {
            await request.put(
                `${backend}/api/app/admin/site-settings/availability`,
                { headers: { Authorization: `Bearer ${token}` }, data: { value: 'listening' } },
            );
        }
    });
});
