import { test, expect, APIRequestContext } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * Tailored application links (#250) end to end, against the composed stack.
 *
 * This is the layer that unit tests structurally cannot reach (rule 12): the
 * route only exists in the SERVER-rendered HTML if SSR resolved the API call,
 * and "the tailored page 404s or renders blank server-side" is exactly the
 * failure this spec is here to catch.
 *
 * Teardown, stated honestly: the tailored link IS deleted, and the opportunity
 * this spec mints it from is retired to `closed_lost` with a note naming it an
 * automated artifact — because the pipeline API (#247) exposes no
 * `DELETE /admin/opportunities/{id}`, so the card itself cannot be removed
 * over HTTP. The card is therefore left inert and self-identifying, not
 * removed; an earlier revision of this file claimed it "leaves the board as it
 * found it", which was false.
 *
 * Nothing here skips on an unreachable or outdated backend. A spec that turns
 * "the stack is broken" into a green run is worse than no spec at all, so both
 * conditions fail loudly instead.
 */

const RUN_ID = Date.now().toString(36);
const SLUG = `e2e-tailored-${RUN_ID}`;
const COMPANY = `Contoso E2E ${RUN_ID}`;
const NOTE = 'Hi Contoso team — here is why this candidate fits the role.';

async function adminToken(request: APIRequestContext, backend: string): Promise<string> {
    // No try/catch: on a refused connection Playwright's request.post THROWS,
    // and that throw is the correct outcome — the stack under test is not
    // serving the admin API, which is a failure of the run, not a reason to
    // pass.
    const login = await request.post(`${backend}${API_PREFIX}/auth/login`, {
        form: { username: 'admin', password: 'admin123' },
    });
    expect(
        login.ok(),
        `admin login failed at ${backend}${API_PREFIX}/auth/login (${login.status()}) — ` +
            'the stack under test cannot exercise tailored links',
    ).toBe(true);
    return (await login.json()).access_token;
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
        const auth = { Authorization: `Bearer ${token}` };

        const opportunity = await request.post(`${backend}${API_PREFIX}/admin/opportunities`, {
            headers: auth,
            data: { company: COMPANY, role_title: 'Staff Engineer' },
        });
        expect(opportunity.status()).toBe(201);
        const opportunityId = (await opportunity.json()).id;

        try {
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
            // A backend image predating #250 has no such route. That is a
            // MISCONFIGURED RUN, not an excuse to pass: the E2E stack is built
            // from the branch under test, so a 404 here means the image is
            // stale and every assertion below would be meaningless.
            expect(
                minted.status(),
                `POST /admin/tailored-links returned ${minted.status()} — the backend image ` +
                    'under test predates #250; rebuild the stack from this branch',
            ).toBe(201);
            const linkId = (await minted.json()).id;

            try {
                // 1. SERVER-rendered HTML carries the note and the noindex marker.
                const ssr = await request.get(`/for/${SLUG}`);
                expect(ssr.status()).toBe(200);
                const html = await ssr.text();
                expect(html).toContain(NOTE);
                expect(html).toContain(COMPANY);
                expect(html).toMatch(/<meta[^>]+name="robots"[^>]+content="noindex/);
                // The page is the portfolio, not an empty shell.
                expect(html).toContain('data-testid="tailored-banner"');

                // 2. robots.txt keeps the whole surface out of every index.
                const robots = await request.get('/robots.txt');
                expect(await robots.text()).toContain('Disallow: /for/');

                // 3. The slug never appears in the sitemap.
                const sitemap = await request.get('/sitemap.xml');
                expect(await sitemap.text()).not.toContain('/for/');

                // 4. In a real browser: the banner renders and the visit is counted.
                await page.addInitScript(() => {
                    window.localStorage.setItem('cookie_consent', 'true');
                });
                await page.goto(`/for/${SLUG}`);
                await expect(page.getByTestId('tailored-note')).toContainText('Contoso team');
                await expect(page.getByTestId('tailored-company')).toContainText(COMPANY);
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

                // 5. The visit is on the opportunity timeline, where the owner looks.
                const detail = await request.get(
                    `${backend}${API_PREFIX}/admin/opportunities/${opportunityId}`,
                    { headers: auth },
                );
                const bodies = (await detail.json()).notes.map((n: { body: string }) => n.body);
                expect(bodies.some((b: string) => b.includes(`/for/${SLUG} opened`))).toBe(true);

                // 6. Revoking is immediate and indistinguishable from "never existed".
                const disabled = await request.patch(
                    `${backend}${API_PREFIX}/admin/tailored-links/${linkId}`,
                    { headers: auth, data: { enabled: false } },
                );
                expect(disabled.ok()).toBe(true);
                expect((await request.get(`/for/${SLUG}`)).status()).toBe(404);
                expect((await request.get(`/for/${SLUG}-nope`)).status()).toBe(404);
            } finally {
                const removed = await request.delete(
                    `${backend}${API_PREFIX}/admin/tailored-links/${linkId}`,
                    { headers: auth },
                );
                expect(
                    removed.status(),
                    'the tailored link outlived the spec that minted it',
                ).toBe(204);
            }
        } finally {
            // The card cannot be deleted over HTTP (no DELETE on
            // /admin/opportunities), so retire it and label it, leaving the
            // active pipeline clean and the residue unmistakably automated.
            await request.post(`${backend}${API_PREFIX}/admin/opportunities/${opportunityId}/notes`, {
                headers: auth,
                data: { body: `Automated E2E artifact (${SLUG}); safe to delete.` },
            });
            await request.patch(
                `${backend}${API_PREFIX}/admin/opportunities/${opportunityId}/stage`,
                { headers: auth, data: { stage: 'closed_lost' } },
            );
        }
    });
});
