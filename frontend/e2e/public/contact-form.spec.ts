import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * The public contact form (#69) — the product's newest PUBLIC WRITE path, and
 * until now the only v1.12.0 surface never exercised in a browser (both the
 * #258 and #274 reviews named this residual). Covers what unit tests can't:
 * the form renders in the SSR'd page, the zoneless client repaints after the
 * async submit, and a failing API surfaces an error instead of a silent hang.
 */
test.describe('Public contact form', () => {
    test('renders inside the contact section with its privacy note', async ({ page }) => {
        await page.goto('/');
        const form = page.locator('form[aria-label="contact form"]');
        await expect(form).toBeVisible();
        await expect(page.locator('#contact-name')).toBeVisible();
        await expect(page.locator('#contact-email')).toBeVisible();
        await expect(page.locator('#contact-message')).toBeVisible();
        // Privacy affordance: the page states what happens to the data.
        await expect(page.locator('#contact').getByText(/stored/i)).toBeVisible();
    });

    test('blocks submission until the required fields are valid', async ({ page }) => {
        await page.goto('/');
        const submit = page.locator('form[aria-label="contact form"] button[type="submit"]');
        await expect(submit).toBeDisabled();

        // Whitespace-only input must NOT satisfy the trimmed validators.
        await page.fill('#contact-name', '   ');
        await page.fill('#contact-email', 'rita@agency.example');
        await page.fill('#contact-message', '   ');
        await expect(submit).toBeDisabled();

        await page.fill('#contact-name', 'Rita Recruiter');
        await page.fill('#contact-message', 'We have a role that fits your profile.');
        await expect(submit).toBeEnabled();
    });

    test('submits, repaints with the success message, and clears the form', async ({ page }) => {
        let posted: Record<string, unknown> | null = null;
        await page.route(`**${API_PREFIX}/interactions/contact`, async (route) => {
            posted = route.request().postDataJSON();
            await route.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({
                    id: 'e2e-1', source: 'contact_form', status: 'new',
                    name: 'Rita Recruiter', email: 'rita@agency.example',
                    company: null, message: 'We have a role that fits your profile.',
                    payload: null, created_at: '2026-09-06T09:00:00Z',
                    updated_at: '2026-09-06T09:00:00Z',
                }),
            });
        });

        await page.goto('/');
        await page.fill('#contact-name', '  Rita Recruiter  ');
        await page.fill('#contact-email', 'rita@agency.example');
        await page.fill('#contact-message', 'We have a role that fits your profile.');
        await page.locator('form[aria-label="contact form"] button[type="submit"]').click();

        // Zoneless repaint after the async callback (#105) — the whole point of
        // this test: a missing markForCheck would leave the page frozen here.
        await expect(page.locator('form[aria-label="contact form"] [role="status"]')).toBeVisible();
        await expect(page.locator('#contact-name')).toHaveValue('');

        // The client mirrors the server's normalization contract.
        expect(posted).toMatchObject({ name: 'Rita Recruiter', company: null });
    });

    test('shows an error and keeps the values when the API fails', async ({ page }) => {
        await page.route(`**${API_PREFIX}/interactions/contact`, (route) =>
            route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"nope"}' })
        );

        await page.goto('/');
        await page.fill('#contact-name', 'Rita Recruiter');
        await page.fill('#contact-email', 'rita@agency.example');
        await page.fill('#contact-message', 'We have a role that fits your profile.');
        await page.locator('form[aria-label="contact form"] button[type="submit"]').click();

        await expect(page.locator('form[aria-label="contact form"] [role="alert"]')).toBeVisible();
        // Values survive a failure so the visitor can retry without retyping.
        await expect(page.locator('#contact-name')).toHaveValue('Rita Recruiter');
    });
});
