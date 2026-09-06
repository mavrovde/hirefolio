import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Admin Inbox (#69) in a real browser — the receiving half of the recruiter
 * flow. Unit tests cover the component; this covers the composed admin app:
 * routing, the filter round trip, expand-to-read, the inline status control,
 * and the promote hand-off into the pipeline (#247).
 */
const INTERACTION = {
    id: 'ix-1',
    source: 'contact_form',
    status: 'new',
    name: 'Rita Recruiter',
    email: 'rita@agency.example',
    company: 'Agency GmbH',
    message: 'We have a Staff Engineer role that fits your profile.',
    payload: null,
    created_at: '2026-09-06T09:00:00Z',
    updated_at: '2026-09-06T09:00:00Z',
};

const page1 = (items: unknown[]) => ({ items, total: items.length, page: 1, pages: 1 });

test.describe('Admin Inbox', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);
    });

    test('shows the empty state on a fresh deployment', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([])) })
        );
        await page.goto('/inbox');
        await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible();
        await expect(page.getByText(/No interactions yet/)).toBeVisible();
    });

    test('lists interactions, expands the message, and filters by status', async ({ page }) => {
        const seen: string[] = [];
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) => {
            seen.push(route.request().url());
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([INTERACTION])) });
        });

        await page.goto('/inbox');
        await expect(page.getByTestId('row-ix-1')).toBeVisible();
        await expect(page.getByText('rita@agency.example')).toBeVisible();

        // The message body is behind the expand interaction, not in the row.
        await expect(page.getByText(/Staff Engineer role/)).toHaveCount(0);
        await page.getByTestId('row-ix-1').click();
        await expect(page.getByText(/Staff Engineer role/)).toBeVisible();

        // Filtering re-queries the API with the chosen status.
        await page.getByLabel('filter by status').selectOption('contacted');
        await expect.poll(() => seen.some((u) => u.includes('status=contacted'))).toBe(true);
    });

    test('changes a status inline through the API', async ({ page }) => {
        let patched: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([INTERACTION])) })
        );
        // Separate pattern on purpose: a glob `*` does NOT cross `/`, so the
        // list route above never matches `/admin/interactions/{id}` — without
        // this the PATCH would escape to the real backend and the assertion
        // would silently observe nothing (caught by running the spec).
        await page.route(`**${API_PREFIX}/admin/interactions/*`, (route) => {
            patched = route.request().postDataJSON();
            return route.fulfill({
                status: 200, contentType: 'application/json',
                body: JSON.stringify({ ...INTERACTION, status: 'contacted' }),
            });
        });

        await page.goto('/inbox');
        await page.getByLabel('status of Rita Recruiter').selectOption('contacted');
        await expect.poll(() => patched).toMatchObject({ status: 'contacted' });
    });

    test('promotes an interaction into the pipeline', async ({ page }) => {
        let promoted: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([INTERACTION])) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities/promote`, (route) => {
            promoted = route.request().postDataJSON();
            return route.fulfill({
                status: 201, contentType: 'application/json',
                body: JSON.stringify({
                    id: 'op-1', company: 'Agency GmbH', role_title: 'Unknown role',
                    stage: 'lead', source: 'recruiter_outreach', recruiter_name: 'Rita Recruiter',
                    recruiter_email: 'rita@agency.example', link: null, salary_note: null,
                    next_action: null, next_action_date: null, notes: [],
                    created_at: '2026-09-06T09:05:00Z', updated_at: '2026-09-06T09:05:00Z',
                }),
            });
        });

        await page.goto('/inbox');
        await page.getByTestId('row-ix-1').click();
        await page.getByLabel('promote Rita Recruiter to pipeline').click();
        await expect.poll(() => promoted).toMatchObject({ interaction_id: 'ix-1' });
    });
});
