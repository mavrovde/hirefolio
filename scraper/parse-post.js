// Pure, browser-free helpers that turn a raw scraped post record into the stable
// posts_data.json schema. Kept free of Playwright so it can be unit-tested with
// `node --test` against fixtures (no live LinkedIn, no network).

/** Extract the numeric activity id from a LinkedIn URN (activity or ugcPost). */
export function activityIdFromUrn(urn) {
  if (!urn) return null;
  const m = String(urn).match(/urn:li:(?:activity|ugcPost):(\d+)/);
  if (m) return m[1];
  const last = String(urn).split(':').pop();
  return /^\d+$/.test(last) ? last : null;
}

/**
 * LinkedIn activity ids encode the creation time in their high bits: the first
 * 41 bits are milliseconds since the epoch. `id >> 22` recovers that timestamp.
 * Returns an ISO-8601 string, or null if the id is unusable.
 */
export function postedAtFromActivityId(activityId) {
  if (!activityId || !/^\d+$/.test(String(activityId))) return null;
  try {
    const ms = Number(BigInt(activityId) >> 22n);
    if (!Number.isFinite(ms) || ms <= 0) return null;
    return new Date(ms).toISOString();
  } catch {
    return null;
  }
}

/** Canonical permalink for an activity id. */
export function urlFromActivityId(activityId) {
  return activityId
    ? `https://www.linkedin.com/feed/update/urn:li:activity:${activityId}/`
    : null;
}

/**
 * Keep only the post's OWN media: drop the author's profile/avatar photo (the
 * historical bug), drop non-http junk, and de-duplicate while preserving order.
 */
export function cleanImageUrls(candidates, authorImageUrl) {
  const out = [];
  const seen = new Set();
  for (const raw of candidates || []) {
    if (!raw) continue;
    const url = String(raw).trim();
    if (!url.startsWith('http')) continue;
    if (authorImageUrl && url === authorImageUrl) continue;
    // LinkedIn avatar assets — never the post image.
    if (/profile-displayphoto|profile-framedphoto|profile-photo/i.test(url)) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    out.push(url);
  }
  return out;
}

/** Light language heuristic (en/de) — the importer can refine, but a sensible
 *  default helps the (slug, language) key and semantic-search filter. */
export function detectLanguage(text) {
  if (!text) return 'en';
  const t = text.toLowerCase();
  if (/[äöüß]/.test(t) || /\b(und|der|die|das|nicht|mit|für|ich|auch|ist|eine)\b/.test(t)) {
    return 'de';
  }
  return 'en';
}

/**
 * Turn a raw extracted record into the stable schema, or null if it has no real
 * text. `raw` = { urn, content, imageCandidates, authorImageUrl, time }.
 */
export function parsePost(raw) {
  const content = (raw.content || '').trim();
  if (content.length < 5) return null;
  const activityId = activityIdFromUrn(raw.urn);
  const imageUrls = cleanImageUrls(raw.imageCandidates, raw.authorImageUrl);
  return {
    urn: activityId ? `urn:li:activity:${activityId}` : raw.urn || '',
    url: urlFromActivityId(activityId),
    content,
    imageUrls,
    imageUrl: imageUrls[0] || null,
    postedAt: postedAtFromActivityId(activityId),
    time: raw.time || '',
    language: detectLanguage(content),
  };
}
