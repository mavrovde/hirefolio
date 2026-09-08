import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Admin engagement dashboard (#249) in a REAL browser (rule 12): unit coverage
 * proves the component's logic, it cannot prove the screen renders — the
 * lesson #248's review left behind. The API is stubbed at the network boundary
 * (rule 10 keeps every E2E off real services), so what is under test here is
 * routing, the zoneless repaint after each async callback, and the chart the
 * jsdom unit tests can only see as attributes.
 */
const SUMMARY = {
    kinds: ['cv_request', 'cv_download', 'contact_submitted'],
    totals: { cv_request: 4, cv_download: 9, contact_submitted: 2 },
    weeks: [
        { week_start: '2026-08-24', counts: { cv_request: 1, cv_download: 0, contact_submitted: 0 } },
        { week_start: '2026-08-31', counts: { cv_request: 3, cv_download: 9, contact_submitted: 2 } },
    ],
    recent: [
        {
            id: 'e1',
            kind: 'cv_download',
            subject_id: 'c1',
            label: 'Rita Recruiter (Agency GmbH)',
            payload: null,
            created_at: '2026-09-05T10:00:00+00:00',
        },
    ],
};

test.describe('Admin engagement dashboard', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);
    });

    test('renders totals, the weekly chart and the activity feed', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/analytics/engagement*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SUMMARY) })
        );

        await page.getByRole('link', { name: 'Engagement' }).click();
        await expect(page).toHaveURL(/\/analytics/);
        await expect(page.getByRole('heading', { name: 'Engagement', exact: true })).toBeVisible();

        const totals = page.getByTestId('analytics-totals');
        await expect(totals.locator('[data-kind="cv_download"] .total-value')).toHaveText('9');

        // The chart must be VISIBLE, not merely present: a bar with a computed
        // height of 0px is exactly what a unit test cannot tell apart.
        const busiest = page.locator('.chart-week[data-week="2026-08-31"] .bar[data-kind="cv_download"]');
        await expect(busiest).toBeVisible();
        const height = await busiest.evaluate((el) => el.getBoundingClientRect().height);
        expect(height).toBeGreaterThan(0);

        await expect(page.getByTestId('analytics-feed')).toContainText('Rita Recruiter (Agency GmbH)');
    });

    test('repaints the trend when the window changes (zoneless)', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/analytics/engagement*`, (route) => {
            const weeks = Number(new URL(route.request().url()).searchParams.get('weeks'));
            const body = {
                ...SUMMARY,
                weeks: Array.from({ length: weeks }, (_, i) => ({
                    week_start: `2026-0${(i % 9) + 1}-01`,
                    counts: { cv_request: i, cv_download: 0, contact_submitted: 0 },
                })),
            };
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        });

        await page.goto('/analytics');
        await expect(page.locator('.chart-week')).toHaveCount(8);
        await page.getByRole('button', { name: '12w' }).click();
        await expect(page.locator('.chart-week')).toHaveCount(12);
    });

    test('reports a skipped digest and a purge, and repaints after each', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/analytics/engagement*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SUMMARY) })
        );
        await page.route(`**${API_PREFIX}/admin/analytics/digest`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sent: false }) })
        );
        await page.route(`**${API_PREFIX}/admin/analytics/purge`, (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ deleted: 2, retention_days: 365 }),
            })
        );

        await page.goto('/analytics');
        await page.getByTestId('analytics-digest').click();
        await expect(page.getByTestId('analytics-action')).toContainText('SMTP is not configured');

        await page.getByTestId('analytics-purge').click();
        await expect(page.getByTestId('analytics-action')).toContainText('Purged 2 event(s)');
    });

    test('says so when the feature is switched off server-side', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/analytics/engagement*`, (route) =>
            route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'disabled' }) })
        );

        await page.goto('/analytics');
        await expect(page.getByTestId('analytics-disabled')).toContainText(
            'ENGAGEMENT_ANALYTICS_ENABLED'
        );
        await expect(page.getByTestId('analytics-totals')).toHaveCount(0);
    });
});
