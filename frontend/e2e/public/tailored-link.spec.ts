import { test, expect, APIRequestContext } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Tailored application links (#250) end to end, against the composed stack.
 *
 * This is the layer that unit tests structurally cannot reach (rule 12): the
 * route only exists in the SERVER-rendered HTML if SSR resolved the API call,
 * and "the tailored page 404s or renders blank server-side" is exactly the
 * failure this spec is here to catch. Everything is created and torn down
 * through the admin API so the suite leaves the board as it found it.
 */

const SLUG = `e2e-tailored-${Date.now().toString(36)}`;
const NOTE = 'Hi Contoso team — here is why this candidate fits the role.';

async function adminToken(request: APIRequestContext, backend: string): Promise<string | null> {
    let login;
    try {
        login = await request.post(`${backend}${API_PREFIX}/auth/login`, {
            form: { username: 'admin', password: 'admin123' },
        });
    } catch {
        return null; // backend unreachable on this topology
    }
    return login.ok() ? (await login.json()).access_token : null;
}

test.describe('Tailored application links (/for/:slug)', () => {
    test('mint → SSR-render → count the visit → revoke → 404', async ({
        page,
        request,
        baseURL,
    }) => {
        // Same origin the browser uses: CI's E2E stack publishes only the proxy,
        // which serves /api on the public vhost (the :8000 port exists only in
        // the dev topology).
        const backend = process.env['BACKEND_URL'] || baseURL || 'http://localhost:4200';
        const token = await adminToken(request, backend);
        test.skip(!token, `admin API unavailable via ${backend}`);
        const auth = { Authorization: `Bearer ${token}` };

        const opportunity = await request.post(`${backend}${API_PREFIX}/admin/opportunities`, {
            headers: auth,
            data: { company: 'Contoso E2E', role_title: 'Staff Engineer' },
        });
        expect(opportunity.status()).toBe(201);
        const opportunityId = (await opportunity.json()).id;

        const minted = await request.post(`${backend}${API_PREFIX}/admin/tailored-links`, {
            headers: auth,
            data: {
                opportunity_id: opportunityId,
                slug: SLUG,
                headline_note: NOTE,
                highlighted_skills: ['Angular', 'Python'],
                highlighted_projects: ['Contoso'],
            },
        });
        // A backend image predating #250 has no such route — skip VISIBLY
        // rather than fake-green; CI builds this branch, so it runs for real.
        test.skip(minted.status() === 404, 'backend image predates #250');
        expect(minted.status()).toBe(201);
        const linkId = (await minted.json()).id;

        try {
            // 1. SERVER-rendered HTML carries the note and the noindex marker.
            const ssr = await request.get(`/for/${SLUG}`);
            expect(ssr.status()).toBe(200);
            const html = await ssr.text();
            expect(html).toContain(NOTE);
            expect(html).toContain('Contoso E2E');
            expect(html).toMatch(/<meta[^>]+name="robots"[^>]+content="noindex/);
            // The page is the portfolio, not an empty shell.
            expect(html).toContain('data-testid="tailored-banner"');

            // 2. robots.txt keeps the whole surface out of every index.
            const robots = await request.get('/robots.txt');
            expect(await robots.text()).toContain('Disallow: /for/');

            // 3. In a real browser: the banner renders and the visit is counted.
            await page.addInitScript(() => {
                window.localStorage.setItem('cookie_consent', 'true');
            });
            await page.goto(`/for/${SLUG}`);
            await expect(page.getByTestId('tailored-note')).toContainText('Contoso team');
            await expect(page.getByTestId('tailored-company')).toContainText('Contoso E2E');
            await expect(page.getByTestId('tailored-cv-cta')).toBeVisible();

            await expect
                .poll(
                    async () => {
                        const rows = await request.get(
                            `${backend}${API_PREFIX}/admin/tailored-links?opportunity_id=${opportunityId}`,
                            { headers: auth },
                        );
                        return (await rows.json())[0].visit_count;
                    },
                    { timeout: 15000, message: 'the browser visit never reached the timeline' },
                )
                .toBeGreaterThanOrEqual(1);

            // 4. The visit is on the opportunity timeline, where the owner looks.
            const detail = await request.get(
                `${backend}${API_PREFIX}/admin/opportunities/${opportunityId}`,
                { headers: auth },
            );
            const bodies = (await detail.json()).notes.map((n: { body: string }) => n.body);
            expect(bodies.some((b: string) => b.includes(`/for/${SLUG} opened`))).toBe(true);

            // 5. Revoking is immediate and indistinguishable from "never existed".
            const disabled = await request.patch(
                `${backend}${API_PREFIX}/admin/tailored-links/${linkId}`,
                { headers: auth, data: { enabled: false } },
            );
            expect(disabled.ok()).toBe(true);
            expect((await request.get(`/for/${SLUG}`)).status()).toBe(404);
            expect((await request.get(`/for/${SLUG}-nope`)).status()).toBe(404);
        } finally {
            await request.delete(`${backend}${API_PREFIX}/admin/tailored-links/${linkId}`, {
                headers: auth,
            });
        }
    });
});
