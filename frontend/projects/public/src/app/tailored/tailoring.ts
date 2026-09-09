/**
 * Pure re-ordering rules for a tailored application link (#250).
 *
 * A tailored page is the SAME portfolio, read in a different order: the skills
 * and the roles the owner marked as relevant to this application come first,
 * everything else keeps its original relative order. Nothing is hidden — a
 * recruiter who scrolls still sees the whole profile, so a tailored link can
 * never become a misleading subset of the truth.
 *
 * Kept as free functions (no injectable, no state) so the component stays dumb
 * and the ordering is testable without a TestBed.
 */

import { Experience, Profile } from '../services/profile.service';

/** Case- and whitespace-insensitive comparison key. */
function key(value: string): string {
    return value.trim().toLowerCase();
}

/** Whether `value` matches any highlight (either side may contain the other). */
export function matchesHighlight(value: string, highlights: readonly string[]): boolean {
    const candidate = key(value);
    if (!candidate) {
        return false;
    }
    return highlights.some((highlight) => {
        const needle = key(highlight);
        return !!needle && (candidate.includes(needle) || needle.includes(candidate));
    });
}

/**
 * Stable partition: matching items first, in their original relative order.
 * `Array.prototype.sort` is stable in every runtime we target, but an explicit
 * partition says the intent out loud and cannot be broken by a comparator typo.
 */
function highlightedFirst<T>(items: readonly T[], matches: (item: T) => boolean): T[] {
    const hit: T[] = [];
    const rest: T[] = [];
    for (const item of items) {
        (matches(item) ? hit : rest).push(item);
    }
    return [...hit, ...rest];
}

/** An experience entry counts as highlighted by its company OR its title. */
export function experienceMatches(entry: Experience, highlights: readonly string[]): boolean {
    return (
        matchesHighlight(entry.company ?? '', highlights) ||
        matchesHighlight(entry.title ?? '', highlights)
    );
}

/**
 * The profile as this recipient should read it. Returns the ORIGINAL object
 * when there is nothing to highlight, so an empty tailoring is provably a
 * no-op (criterion 5: the default portfolio is unchanged when unused).
 */
export function applyTailoring(
    profile: Profile,
    highlightedSkills: readonly string[],
    highlightedProjects: readonly string[],
): Profile {
    if (highlightedSkills.length === 0 && highlightedProjects.length === 0) {
        return profile;
    }
    return {
        ...profile,
        skills: highlightedSkills.length
            ? highlightedFirst(profile.skills ?? [], (skill) =>
                  matchesHighlight(skill, highlightedSkills),
              )
            : profile.skills,
        experience: highlightedProjects.length
            ? highlightedFirst(profile.experience ?? [], (entry) =>
                  experienceMatches(entry, highlightedProjects),
              )
            : profile.experience,
    };
}
