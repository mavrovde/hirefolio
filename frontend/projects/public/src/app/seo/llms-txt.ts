/**
 * Config-driven `/llms.txt` (#252).
 *
 * `robots.txt` says what an agent MAY read and `sitemap.xml` lists every URL;
 * neither tells an agent WHERE THE ANSWER IS. llms.txt (llmstxt.org) is the
 * curated, markdown entry point for exactly that: a short H1 + summary, then
 * link lists an assistant can follow when a recruiter asks "has this person
 * shipped pgvector in production?".
 *
 * The file is rendered per request by the SSR Express server from the runtime
 * site config (#65) plus the live published-post list — the same seam
 * `sitemap.ts` uses, so a forker's deployment produces a forker's file with no
 * code edits and no rebuild. Every literal in here describes the PRODUCT's own
 * routes; nothing about an owner or a domain is hardcoded.
 *
 * Format (llmstxt.org, v2): an H1 (the only required section), an optional
 * blockquote summary, free prose, then H2-delimited link lists whose items are
 * `- [name](url): notes`.
 */

import {
    fetchPublishedPosts,
    JsonFetcher,
    RESUME_PATH,
    resolveSiteConfig,
    SitemapPost,
    SsrSiteConfig,
    stripTrailingSlash,
} from './sitemap';

/**
 * How many posts the blog section names individually.
 *
 * llms.txt is meant to FIT IN CONTEXT — the detail lives behind the links. A
 * blog with hundreds of posts would otherwise turn the entry point into the
 * payload; `/blog` and `sitemap.xml` carry the complete list.
 */
export const LLMS_TXT_MAX_POSTS = 25;

/**
 * The job-search state (#271) rendered as a sentence an assistant can quote.
 * An unknown/absent state yields nothing rather than a guess.
 */
const AVAILABILITY_NOTE: Record<string, string | undefined> = {
    open: 'Actively looking for new opportunities.',
    listening: 'Open to hearing about new opportunities.',
    not_looking: 'Not currently looking for new opportunities.',
};

/**
 * Markdown link-text escaping: an unescaped `]` truncates a link label, and a
 * post title is free text an admin controls.
 *
 * The BACKSLASH is escaped too, and it has to come first in the character
 * class: escaping only the brackets makes the escaping itself forgeable — a
 * title ending in `\` turns the emitted `\]` into `\\]`, which markdown reads
 * as a literal backslash followed by an ACTIVE `]`, closing the label anyway.
 * (`js/incomplete-sanitization`, flagged by CodeQL on the first push of this
 * branch; the round-1 version escaped brackets alone.)
 */
export function escapeMarkdown(value: string): string {
    return value.replace(/([\\[\]])/g, '\\$1');
}

/**
 * One `- [name](url): notes` item.
 *
 * The URL is emitted verbatim, byte-identical to the same post's `<loc>` in
 * `sitemap.xml` — two generated files must not disagree on a page's URL, and
 * percent-encoding here alone would make them disagree (and would double-encode
 * a slug that already carries an escape). Slug hygiene belongs to whoever
 * accepts the slug, not to two independent renderers.
 */
function link(name: string, url: string, notes?: string): string {
    const item = `- [${escapeMarkdown(name)}](${url})`;
    return notes ? `${item}: ${notes}` : item;
}

export function buildLlmsTxt(site: SsrSiteConfig, posts: readonly SitemapPost[]): string {
    const base = stripTrailingSlash(site.siteUrl);
    // The H1 is the ONE required section, so it always resolves to something:
    // the configured site name, else the owner, else the neutral product word
    // (which is also `DEFAULT_SITE_CONFIG.siteName` in the browser app).
    const title = site.siteName || site.ownerName || 'Portfolio';
    const summary = [site.ownerName, site.ownerHeadline].filter(Boolean).join(' — ');

    const lines: string[] = [`# ${title}`, ''];
    if (summary) {
        lines.push(`> ${summary}`, '');
    }
    if (site.ownerDescription) {
        lines.push(site.ownerDescription, '');
    }
    const availability = AVAILABILITY_NOTE[site.availability];
    if (availability) {
        lines.push(`Availability: ${availability}`, '');
    }
    lines.push(
        'The complete profile is available as structured data in a single request — ' +
            'prefer it over parsing the HTML pages below.',
        '',
    );

    lines.push(
        '## Profile',
        '',
        link(
            'Structured profile (JSON Resume v1.0.0)',
            `${base}${RESUME_PATH}`,
            'the whole candidate in one fetch — experience, education, skills, ' +
                'languages, certificates, references, availability and contact route',
        ),
        link('Home', `${base}/`, 'summary, current availability and the contact form'),
        link('CV', `${base}/cv`, 'the rendered CV, filterable by year'),
        link('Contact', `${base}/#contact`, 'how to reach the owner about a role'),
        '',
    );

    lines.push('## Blog', '', link('All posts', `${base}/blog`, 'the complete index'));
    for (const post of posts.slice(0, LLMS_TXT_MAX_POSTS)) {
        lines.push(
            link(post.title || post.slug, `${base}/blog/${post.slug}`, post.lastmod),
        );
    }
    lines.push('');

    lines.push(
        '## Optional',
        '',
        link('AI assistant', `${base}/llm`, 'ask questions against this profile'),
        link('Sitemap', `${base}/sitemap.xml`, 'every indexable URL'),
        link('Crawler policy', `${base}/robots.txt`, 'what automated clients may read'),
        '',
    );

    return lines.join('\n');
}

export async function renderLlmsTxt(
    fetchJson: JsonFetcher,
    fallbackOrigin: string,
): Promise<string> {
    const [site, posts] = await Promise.all([
        resolveSiteConfig(fetchJson, fallbackOrigin),
        // Bounded at what the file will actually print: one backend request of
        // 25, not four requests of 100 whose surplus is discarded (#252 review,
        // minor 1). `sitemap.xml` still reads every page — it must.
        fetchPublishedPosts(fetchJson, LLMS_TXT_MAX_POSTS),
    ]);
    return buildLlmsTxt(site, posts);
}
