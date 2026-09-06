import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Admin Pipeline board (#247 phase 1) in a real browser. The #274 review
 * closed with this exact residual: "the board has never rendered in a real
 * browser under CI". Covers the board's own jobs — cards land in their stage
 * column, the detail panel opens, a stage move and a timeline note reach the
 * API, and the zoneless admin app repaints after each async callback.
 */
const OPP = {
    id: 'op-1',
    company: 'Agency GmbH',
    role_title: 'Staff Engineer',
    stage: 'lead',
    source: 'recruiter_outreach',
    recruiter_name: 'Rita Recruiter',
    recruiter_email: 'rita@agency.example',
    link: null,
    salary_note: null,
    next_action: null,
    next_action_date: null,
    notes: [] as unknown[],
    sent_cv_id: null as string | null,
    sent_cv_at: null as string | null,
    created_at: '2026-09-06T09:00:00Z',
    updated_at: '2026-09-06T09:00:00Z',
};

const page1 = (items: unknown[]) => ({ items, total: items.length, page: 1, pages: 1 });

test.describe('Admin Pipeline board', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="username"]', 'admin');
        await page.fill('input[name="password"]', 'admin123');
        await page.click('button[type="submit"]');
        await expect(page).toHaveURL(/\/dashboard/);
    });

    test('renders every stage column and places a card in its stage', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([OPP])) })
        );

        await page.goto('/pipeline');
        await expect(page.getByRole('heading', { name: 'Pipeline', exact: true })).toBeVisible();
        const ALL_STAGES = ['lead', 'contacted', 'screening', 'interviewing', 'offer', 'closed_won', 'closed_lost'];
        for (const stage of ALL_STAGES) {
            await expect(page.getByRole('heading', { name: new RegExp(`^${stage}`, 'i') })).toBeVisible();
        }
        const card = page.getByTestId('card-op-1');
        await expect(card).toBeVisible();
        await expect(card).toContainText('Agency GmbH');
        await expect(card).toContainText('Staff Engineer');
    });

    test('opens the detail panel with the timeline empty state', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OPP) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([OPP])) })
        );

        await page.goto('/pipeline');
        await page.getByTestId('card-op-1').click();
        await expect(page.getByRole('heading', { name: 'Agency GmbH' })).toBeVisible();
        await expect(page.getByText('Rita Recruiter')).toBeVisible();
        await expect(page.getByText('No notes yet.')).toBeVisible();
    });

    test('moves a card to another stage through the API', async ({ page }) => {
        let staged: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1/stage`, (route) => {
            staged = route.request().postDataJSON();
            return route.fulfill({
                status: 200, contentType: 'application/json',
                body: JSON.stringify({ ...OPP, stage: 'screening' }),
            });
        });
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OPP) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([OPP])) })
        );

        await page.goto('/pipeline');
        await page.getByTestId('card-op-1').click();
        await page.getByLabel('stage').selectOption('screening');
        await expect.poll(() => staged).toMatchObject({ stage: 'screening' });

        // The board must reflect the move, not just send it: the card leaves
        // the lead column and appears under screening (review nit 4).
        const screeningColumn = page
            .locator('div.w-64')
            .filter({ has: page.getByRole('heading', { name: /^screening/i }) });
        await expect(screeningColumn.getByTestId('card-op-1')).toBeVisible();
    });

    test('adds a timeline note and repaints with it', async ({ page }) => {
        let noted: Record<string, unknown> | null = null;
        const withNote = {
            ...OPP,
            notes: [{ id: 'n-1', interaction_id: null, body: 'Call scheduled for Tuesday.', created_at: '2026-09-06T10:00:00Z' }],
        };
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1/notes`, (route) => {
            noted = route.request().postDataJSON();
            return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(withNote) });
        });
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OPP) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([OPP])) })
        );

        await page.goto('/pipeline');
        await page.getByTestId('card-op-1').click();
        await page.fill('input[name="note"]', 'Call scheduled for Tuesday.');
        await page.getByRole('button', { name: 'Add', exact: true }).click();

        await expect.poll(() => noted).toMatchObject({ body: 'Call scheduled for Tuesday.' });
        // Zoneless admin app: the note must appear without a manual reload.
        await expect(page.getByText('Call scheduled for Tuesday.')).toBeVisible();
    });

    test('creates an opportunity from the quick-create form', async ({ page }) => {
        let created: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) => {
            if (route.request().method() === 'POST') {
                created = route.request().postDataJSON();
                return route.fulfill({
                    status: 201,
                    contentType: 'application/json',
                    body: JSON.stringify({ ...OPP, id: 'op-new', company: 'Northwind', role_title: 'Platform Engineer' }),
                });
            }
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([])) });
        });

        await page.goto('/pipeline');
        await page.getByRole('button', { name: '+ Opportunity' }).click();

        // The form refuses to submit until BOTH required fields carry real text.
        const submit = page.getByRole('button', { name: 'Create', exact: true });
        await expect(submit).toBeDisabled();
        await page.fill('input[name="company"]', '   ');
        await expect(submit).toBeDisabled();

        await page.fill('input[name="company"]', 'Northwind');
        await page.fill('input[name="role_title"]', 'Platform Engineer');
        await expect(submit).toBeEnabled();
        await submit.click();

        await expect.poll(() => created).toMatchObject({
            company: 'Northwind',
            role_title: 'Platform Engineer',
        });
    });

    test('surfaces a board load failure while keeping the columns visible', async ({ page }) => {
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' })
        );
        await page.goto('/pipeline');
        // Genuinely scoped to the admin content region (the union selector this
        // replaced was a no-op — the second branch is a superset), and asserting
        // the COPY, so a future shell toast neither collides in strict mode nor
        // satisfies this silently.
        const alert = page.locator('main').getByRole('alert').first();
        await expect(alert).toBeVisible();
        await expect(alert).toContainText(/fail|error|load/i);
        // The board frame survives the failure — an operator sees an errored
        // board, not a blank page that looks like "you have no opportunities".
        await expect(page.getByRole('heading', { name: /^lead/i })).toBeVisible();
    });
    test('records a CV variant as sent — the criterion-4 flow in a real browser', async ({ page }) => {
        const CV = { id: 'cv-1', filename: 'cv-backend.pdf', version: 'backend-focus', is_active: true, created_at: '2026-09-01T09:00:00Z' };
        await page.route(`**${API_PREFIX}/admin/cv/versions*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json',
                body: JSON.stringify({ items: [CV], total: 1, page: 1, pages: 1 }) })
        );
        let recorded: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1/cv-sent`, (route) => {
            recorded = route.request().postDataJSON();
            return route.fulfill({
                status: 201, contentType: 'application/json',
                body: JSON.stringify({
                    ...OPP, sent_cv_id: 'cv-1', sent_cv_at: '2026-09-06T21:00:00Z',
                    notes: [{ id: 'n1', interaction_id: null, body: 'CV sent: backend-focus (cv-backend.pdf)', created_at: '2026-09-06T21:00:00Z' }],
                }),
            });
        });
        await page.route(`**${API_PREFIX}/admin/opportunities/op-1`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OPP) })
        );
        await page.route(`**${API_PREFIX}/admin/opportunities*`, (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(page1([OPP])) })
        );

        await page.goto('/pipeline');
        await page.getByTestId('card-op-1').click();
        await expect(page.getByText('No CV recorded for this opportunity yet.')).toBeVisible();
        // The public default is flagged in the picker (#294 review minor 7).
        await expect(page.getByLabel('CV variant')).toContainText('backend-focus (cv-backend.pdf) — public default');

        await page.getByLabel('CV variant').selectOption('cv-1');
        await page.getByRole('button', { name: 'Record as sent' }).click();

        // Zoneless: the subscribe callback must repaint the panel on its own.
        // Specific locators — the version string legitimately appears in three
        // places (the Sent line, the <option>, the timeline note).
        await expect(page.getByText(/^Sent: backend-focus \(cv-backend\.pdf\)/)).toBeVisible();
        await expect(page.getByText(/^CV sent: backend-focus \(cv-backend\.pdf\)$/)).toBeVisible();
        await expect(page.getByText('No CV recorded for this opportunity yet.')).toHaveCount(0);
        expect(recorded).toEqual({ cv_document_id: 'cv-1' });
    });

});
