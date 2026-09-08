import { describe, expect, it } from 'vitest';
import { Profile } from '../services/profile.service';
import { applyTailoring, experienceMatches, matchesHighlight } from './tailoring';

function profile(overrides: Partial<Profile> = {}): Profile {
    return {
        name: 'Owner',
        headline: 'Engineer',
        location: 'Somewhere',
        about: 'About',
        experience: [
            { title: 'Backend Engineer', company: 'Globex', startDate: '2019', endDate: '2021' },
            { title: 'Staff Engineer', company: 'Acme GmbH', startDate: '2021', endDate: 'now' },
            { title: 'Consultant', company: 'Initech', startDate: '2017', endDate: '2019' },
        ],
        education: [],
        skills: ['Python', 'Angular', 'Kubernetes', 'RxJS'],
        ...overrides,
    };
}

describe('matchesHighlight', () => {
    it('matches case- and whitespace-insensitively, in either direction', () => {
        expect(matchesHighlight('Angular', [' angular '])).toBe(true);
        expect(matchesHighlight('Angular 22', ['angular'])).toBe(true);
        expect(matchesHighlight('Angular', ['Angular 22'])).toBe(true);
        expect(matchesHighlight('Python', ['Angular'])).toBe(false);
    });

    it('never matches on emptiness — a blank highlight would match everything', () => {
        expect(matchesHighlight('', ['angular'])).toBe(false);
        expect(matchesHighlight('   ', ['angular'])).toBe(false);
        expect(matchesHighlight('Angular', ['   '])).toBe(false);
        expect(matchesHighlight('Angular', [])).toBe(false);
    });
});

describe('experienceMatches', () => {
    it('matches on the company or on the title', () => {
        const entry = { title: 'Staff Engineer', company: 'Acme GmbH', startDate: '', endDate: '' };
        expect(experienceMatches(entry, ['acme'])).toBe(true);
        expect(experienceMatches(entry, ['staff engineer'])).toBe(true);
        expect(experienceMatches(entry, ['Initech'])).toBe(false);
    });

    it('tolerates an entry with neither field, rather than throwing', () => {
        const partial = { startDate: '', endDate: '' } as unknown as Profile['experience'][number];
        expect(experienceMatches(partial, ['acme'])).toBe(false);
    });
});

describe('applyTailoring', () => {
    it('returns the ORIGINAL object when nothing is highlighted', () => {
        const original = profile();
        // Criterion 5: an unused tailoring must be a provable no-op, not a
        // structurally-equal copy that could quietly diverge later.
        expect(applyTailoring(original, [], [])).toBe(original);
    });

    it('moves the highlighted skills first and keeps the rest in order', () => {
        const tailored = applyTailoring(profile(), ['Angular', 'RxJS'], []);
        expect(tailored.skills).toEqual(['Angular', 'RxJS', 'Python', 'Kubernetes']);
        // Nothing is hidden — a tailored page is a re-ordering, never a subset.
        expect(tailored.skills).toHaveLength(4);
    });

    it('moves the highlighted roles first, matched by company or title', () => {
        const tailored = applyTailoring(profile(), [], ['Acme']);
        expect(tailored.experience.map((e) => e.company)).toEqual([
            'Acme GmbH',
            'Globex',
            'Initech',
        ]);
    });

    it('leaves the untouched dimension exactly as it was', () => {
        const original = profile();
        const tailored = applyTailoring(original, ['Angular'], []);
        expect(tailored.experience).toBe(original.experience);
        expect(tailored.education).toBe(original.education);
    });

    it('survives a profile whose arrays are missing entirely', () => {
        const bare = { ...profile(), skills: undefined, experience: undefined } as unknown as Profile;
        const tailored = applyTailoring(bare, ['Angular'], ['Acme']);
        expect(tailored.skills).toEqual([]);
        expect(tailored.experience).toEqual([]);
    });
});
