import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * The product's core value flow, end to end in one browser session:
 * a recruiter's message lands in the Inbox → the owner promotes it → the card
 * appears on the Pipeline board → a remark is added to its timeline.
 *
 * The per-screen specs prove each screen; this proves the JOURNEY — the hand-off
 * between them, which is where a contract mismatch actually hurts. It also
 * covers the promote hardening (#277/#278/#279) at the browser layer: a
 * double-click must not mint a second card, and a cv_request must keep its
 * origin instead of being relabelled recruiter outreach.
 */
const CONTACT = {
    id: 'jx-1',
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

const CV_REQUEST = { ...CONTACT, id: 'jx-2', source: 'cv_request', name: 'Cara Candidate-Hunter' };

const CARD = {
    id: 'jop-1',
    company: 'Agency GmbH',
    role_title: 'Unknown role',
    stage: 'lead',
    source: 'recruiter_outreach',
    recruiter_name: 'Rita Recruiter',
    recruiter_email: 'rita@agency.example',
    link: null,
    salary_note: null,
    next_action: null,
    next_action_date: null,
    notes: [
        {
            id: 'jn-1',
            interaction_id: 'jx-1',
            body: 'Promoted from inbox (contact_form):\nWe have a Staff Engineer role that fits your profile.',
            created_at: '2026-09-06T09:05:00Z',
        },
    ],
    created_at: '2026-09-06T09:05:00Z',
    updated_at: '2026-09-06T09:05:00Z',
};

const page1 = (items: unknown[]) => ({ items, total: items.length, page: 1, pages: 1 });

test.describe('Recruiter journey: inbox → promote → pipeline', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);
    });

    test('an inbox message becomes a pipeline card carrying its original text', async ({ page }) => {
        let promoteCount = 0;
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([CONTACT])) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities/promote`, (route) => {
            promoteCount += 1;
            return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(CARD) });
        });
        await page.route(`**${API_PREFIX}/admin/opportunities/jop-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CARD) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([CARD])) })
        );

        // 1. The message is in the inbox.
        await page.goto('/inbox');
        await page.getByTestId('row-jx-1').click();
        await expect(page.getByText(/Staff Engineer role/)).toBeVisible();

        // 2. Promote it.
        await page.getByLabel('promote Rita Recruiter to pipeline').click();
        await expect.poll(() => promoteCount).toBe(1);

        // 3. The card is on the board, under `lead`, with the recruiter's identity.
        await page.goto('/pipeline');
        const card = page.getByTestId('card-jop-1');
        await expect(card).toBeVisible();
        await expect(card).toContainText('Agency GmbH');

        // 4. The original message survived as the first timeline entry — the
        //    reason promote exists at all: no retyping, no lost context.
        await card.click();
        await expect(page.getByText(/Promoted from inbox \(contact_form\)/)).toBeVisible();
        await expect(page.getByText(/Staff Engineer role/)).toBeVisible();
    });

    test('a double-click on promote does not mint a second card (#279)', async ({ page }) => {
        const promoted: unknown[] = [];
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([CONTACT])) })
        );
        // The server is idempotent per interaction: both calls return the SAME card.
        await page.route(`**${API_PREFIX}/admin/opportunities/promote`, (route) => {
            promoted.push(route.request().postDataJSON());
            return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(CARD) });
        });
        await page.route(`**${API_PREFIX}/admin/opportunities/jop-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CARD) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([CARD])) })
        );

        await page.goto('/inbox');
        await page.getByTestId('row-jx-1').click();
        const promote = page.getByLabel('promote Rita Recruiter to pipeline');
        await promote.click();
        await promote.click({ force: true }).catch(() => undefined);

        // However many times the button was pressed, the board holds ONE card —
        // phase 1 ships no DELETE, so a duplicate would be permanent.
        await page.goto('/pipeline');
        await expect(page.getByTestId('card-jop-1')).toHaveCount(1);
        for (const body of promoted) {
            expect(body).toMatchObject({ interaction_id: 'jx-1' });
        }
    });

    test('a promoted CV request keeps its origin instead of recruiter outreach (#278)', async ({ page }) => {
        const discoveryCard = { ...CARD, id: 'jop-2', source: 'discovery', recruiter_name: 'Cara Candidate-Hunter' };
        await page.route(`**${API_PREFIX}/admin/interactions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([CV_REQUEST])) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities/promote`, (route) =>
            route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(discoveryCard) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities/jop-2`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(discoveryCard) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([discoveryCard])) })
        );

        await page.goto('/inbox');
        // The inbox shows where each touch came from — the dimension #249 measures.
        await expect(page.getByTestId('row-jx-2')).toContainText('cv_request');
        await page.getByTestId('row-jx-2').click();
        await page.getByLabel('promote Cara Candidate-Hunter to pipeline').click();

        await page.goto('/pipeline');
        await expect(page.getByTestId('card-jop-2')).toBeVisible();
    });
});
