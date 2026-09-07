import { describe, it, expect } from 'vitest';
import {
    buildAddress,
    buildAlumniOf,
    buildPersonSchema,
    buildSeeks,
    buildWorksFor,
    isOngoingRole,
} from './person-schema';
import { Experience, Profile } from '../services/profile.service';
import { SiteConfig } from '../services/site-config.service';

const role = (over: Partial<Experience> = {}): Experience => ({
    title: 'Senior Software Engineer',
    company: 'Acme Cloud GmbH',
    startDate: 'Mar 2022',
    endDate: 'Present',
    ...over,
});

const FULL_PROFILE: Profile = {
    name: 'Jane Doe',
    headline: 'Senior Software Engineer',
    location: 'Berlin, Germany',
    about: 'Builds distributed systems.',
    skills: ['Python', 'Angular'],
    experience: [
        role({ company: 'Initech Solutions', endDate: 'Feb 2022' }),
        role({ companyLinkedInUrl: 'https://www.linkedin.com/company/acme/' }),
    ],
    education: [
        { school: 'Example Technical University', degree: 'M.Sc.', years: '2014 - 2016' },
        { school: 'Example University', degree: 'B.Sc.', years: '2011 - 2014' },
    ],
};

const FULL_SITE: SiteConfig = {
    siteName: 'My Portfolio',
    siteUrl: 'https://example.com',
    ownerName: 'Jane Doe',
    ownerHeadline: 'Senior Software Engineer',
    ownerDescription: 'Portfolio.',
    socialLinks: ['https://www.linkedin.com/in/jane/'],
    analyticsId: '',
    availability: 'open',
};

describe('isOngoingRole', () => {
    it.each([
        ['Present', true],
        ['Heute', true],
        ['', true],
        ['Feb 2022', false],
        ['1999', false],
    ])('endDate %j is ongoing: %s', (endDate, expected) => {
        expect(isOngoingRole(role({ endDate }))).toBe(expected);
    });

    it('treats a missing endDate as ongoing', () => {
        expect(isOngoingRole({ ...role(), endDate: undefined as unknown as string })).toBe(true);
    });
});

describe('buildAddress', () => {
    it('splits locality and country', () => {
        expect(buildAddress('Berlin, Germany')).toEqual({
            '@type': 'PostalAddress',
            addressLocality: 'Berlin',
            addressCountry: 'Germany',
        });
    });

    it('emits locality only when there is no country part', () => {
        expect(buildAddress('Berlin')).toEqual({
            '@type': 'PostalAddress',
            addressLocality: 'Berlin',
        });
    });

    it.each([undefined, '', '  ', ','])('returns undefined for %j', (location) => {
        expect(buildAddress(location)).toBeUndefined();
    });
});

describe('buildWorksFor', () => {
    it('picks the first role without an end year and carries its company URL', () => {
        expect(
            buildWorksFor([
                role({ company: 'Initech Solutions', endDate: 'Feb 2022' }),
                role({ companyLinkedInUrl: 'https://www.linkedin.com/company/acme/' }),
            ]),
        ).toEqual({
            '@type': 'Organization',
            name: 'Acme Cloud GmbH',
            url: 'https://www.linkedin.com/company/acme/',
        });
    });

    it.each([[{ companyLinkedInUrl: '   ' }], [{ companyLinkedInUrl: undefined }], [{}]])(
        'omits url when the company link is blank or absent (%#)',
        (over) => {
            expect(buildWorksFor([role(over)])).toEqual({
                '@type': 'Organization',
                name: 'Acme Cloud GmbH',
            });
        },
    );

    it('ignores an ongoing role with no company name', () => {
        expect(buildWorksFor([role({ company: '' })])).toBeUndefined();
    });

    it.each([[undefined], [[]], [[role({ endDate: 'Feb 2022' })]]])(
        'returns undefined when nothing is ongoing (%#)',
        (experience) => {
            expect(buildWorksFor(experience)).toBeUndefined();
        },
    );
});

describe('buildAlumniOf', () => {
    it('maps every named school', () => {
        expect(
            buildAlumniOf([
                { school: 'Example Technical University', degree: 'M.Sc.', years: '2014 - 2016' },
                { school: ' Example University ', degree: 'B.Sc.', years: '2011 - 2014' },
            ]),
        ).toEqual([
            { '@type': 'EducationalOrganization', name: 'Example Technical University' },
            { '@type': 'EducationalOrganization', name: 'Example University' },
        ]);
    });

    it.each([
        [undefined],
        [[]],
        [[{ school: '  ', degree: 'M.Sc.', years: '2014' }]],
    ])('returns undefined when there is no named school (%#)', (education) => {
        expect(buildAlumniOf(education)).toBeUndefined();
    });

    it('tolerates an entry with no school field at all', () => {
        expect(buildAlumniOf([{ degree: 'M.Sc.', years: '2014' } as never])).toBeUndefined();
    });
});

describe('buildSeeks (open-to-work signal, #71 AC5)', () => {
    it('emits a Demand for an actively looking owner', () => {
        expect(buildSeeks('open')).toEqual({
            '@type': 'Demand',
            name: 'Open to new opportunities',
        });
    });

    it('emits a softer Demand while only listening', () => {
        expect(buildSeeks('listening')).toEqual({
            '@type': 'Demand',
            name: 'Open to hearing about new opportunities',
        });
    });

    it('emits nothing when the owner is not looking', () => {
        expect(buildSeeks('not_looking')).toBeUndefined();
    });
});

describe('buildPersonSchema', () => {
    it('assembles the enriched Person node from profile + site config', () => {
        expect(buildPersonSchema(FULL_PROFILE, FULL_SITE)).toEqual({
            '@context': 'https://schema.org',
            '@type': 'Person',
            name: 'Jane Doe',
            jobTitle: 'Senior Software Engineer',
            url: 'https://example.com',
            description: 'Builds distributed systems.',
            sameAs: ['https://www.linkedin.com/in/jane/'],
            knowsAbout: ['Python', 'Angular'],
            hasOccupation: {
                '@type': 'Occupation',
                name: 'Senior Software Engineer',
                skills: ['Python', 'Angular'],
            },
            worksFor: {
                '@type': 'Organization',
                name: 'Acme Cloud GmbH',
                url: 'https://www.linkedin.com/company/acme/',
            },
            alumniOf: [
                { '@type': 'EducationalOrganization', name: 'Example Technical University' },
                { '@type': 'EducationalOrganization', name: 'Example University' },
            ],
            address: { '@type': 'PostalAddress', addressLocality: 'Berlin', addressCountry: 'Germany' },
            seeks: { '@type': 'Demand', name: 'Open to new opportunities' },
        });
    });

    it('omits every optional property rather than emitting an empty one', () => {
        const bare = buildPersonSchema(
            {
                name: 'Jane Doe',
                headline: '',
                location: '',
                about: '',
                skills: [],
                experience: [],
                education: [],
            },
            { ...FULL_SITE, siteUrl: '', socialLinks: [], availability: 'not_looking' },
        );

        expect(bare).toEqual({ '@context': 'https://schema.org', '@type': 'Person', name: 'Jane Doe' });
    });

    it('survives a raw uploaded profile whose optional arrays are missing entirely', () => {
        const schema = buildPersonSchema(
            { name: 'Jane Doe', headline: 'Engineer' } as unknown as Profile,
            { ...FULL_SITE, socialLinks: undefined as unknown as string[] },
        );

        expect(schema.hasOccupation).toEqual({ '@type': 'Occupation', name: 'Engineer' });
        expect(schema.knowsAbout).toBeUndefined();
        expect(schema.sameAs).toBeUndefined();
    });
});
