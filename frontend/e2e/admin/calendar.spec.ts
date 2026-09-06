import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Admin interview calendar (#247 phase 2) in a real browser. Rule 12: this
 * screen's failure modes — a dead download control, a select that lies after a
 * rejected PATCH, a zoneless page that never repaints — are exactly the ones
 * unit specs have missed before (#276, #290), so the browser run is not
 * optional. Backend is mocked with page.route like the sibling pipeline spec.
 */
const ROUND = {
    id: 'iv-1',
    opportunity_id: 'op-1',
    scheduled_at: '2026-09-10T09:00:00Z',
    duration_minutes: 60,
    kind: 'video',
    location_or_link: 'https://meet.example/round1',
    interviewer: 'Ada Interviewer',
    notes: null,
    outcome: 'pending',
    company: 'Agency GmbH',
    role_title: 'Staff Engineer',
    stage: 'interviewing',
};

const ICS_BODY = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'BEGIN:VEVENT',
    'UID:iv-1',
    'DTSTART:20260910T090000Z',
    'DTEND:20260910T100000Z',
    'SUMMARY:Interview',
    'END:VEVENT',
    'END:VCALENDAR',
].join('\r\n');

test.describe('Admin interview calendar', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);
    });

    test('renders the upcoming rounds with company context and repaints zonelessly', async ({
        page,
    }) => {
        await page.route(`**${API_PREFIX}/admin/interviews/upcoming*`, (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([ROUND]),
            }),
        );

        await page.goto('/calendar');
        // The subscribe callback must repaint on its own — the app is zoneless,
        // and "Loading…" forever is this screen's frozen-UI shape.
        await expect(page.getByText('Agency GmbH')).toBeVisible();
        await expect(page.getByText('Staff Engineer')).toBeVisible();
        await expect(page.getByText('Ada Interviewer')).toBeVisible();
        await expect(page.getByText('Loading the calendar…')).toHaveCount(0);
    });

    test('downloads the .ics through an AUTHENTICATED request', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/interviews/upcoming*`, (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([ROUND]),
            }),
        );
        let sawAuth = false;
        await page.route(`**${API_PREFIX}/admin/interviews/iv-1.ics`, (route) => {
            // The round-1 blocker: a bare <a href> carries no Bearer token and
            // this endpoint answers 401. Assert the header is actually there.
            sawAuth = /^Bearer .+/.test(route.request().headers()['authorization'] ?? '');
            return route.fulfill({
                status: 200,
                contentType: 'text/calendar',
                body: ICS_BODY,
            });
        });

        await page.goto('/calendar');
        await expect(page.getByText('Agency GmbH')).toBeVisible();

        const downloadPromise = page.waitForEvent('download');
        await page.getByRole('button', { name: 'Add to calendar (.ics)' }).click();
        const download = await downloadPromise;
        expect(download.suggestedFilename()).toBe('interview-iv-1.ics');
        expect(sawAuth).toBe(true);
    });

    test('records an outcome and repaints; a rejected outcome snaps back', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/interviews/upcoming*`, (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([ROUND]),
            }),
        );
        let patches = 0;
        await page.route(`**${API_PREFIX}/admin/interviews/iv-1`, (route) => {
            patches += 1;
            if (patches === 1) {
                return route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ ...ROUND, outcome: 'passed' }),
                });
            }
            return route.fulfill({
                status: 422,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'Invalid outcome' }),
            });
        });

        await page.goto('/calendar');
        const select = page.locator('select.outcome');
        await expect(select).toHaveValue('pending');

        // Accepted PATCH: the select keeps the new value after the repaint.
        await select.selectOption('passed');
        await expect(select).toHaveValue('passed');

        // Rejected PATCH: the DOM must snap BACK to the model value — a select
        // that keeps the rejected choice is lying about persisted state.
        await select.selectOption('failed');
        await expect(page.getByText('Failed to update the outcome')).toBeVisible();
        await expect(select).toHaveValue('passed');
    });

    test('shows the error state when the window fails to load', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/interviews/upcoming*`, (route) =>
            route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'boom' }),
            }),
        );
        await page.goto('/calendar');
        await expect(page.getByText('Failed to load the calendar')).toBeVisible();
    });
});
