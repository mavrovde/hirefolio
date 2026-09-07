import { Education, Experience, Profile } from '../services/profile.service';
import { SiteConfig } from '../services/site-config.service';

/**
 * schema.org `Person` structured data for the home page (#71).
 *
 * Pure, DI-free functions so the mapping is unit-testable in isolation and the
 * component stays dumb (rule 5). Every value is derived from the active profile
 * and the runtime site config (#65) — nothing about the owner is hardcoded, so
 * a forker's own data produces their own rich result with no code edits.
 *
 * Types are explicit object *type aliases* (not interfaces) on purpose: an
 * alias gets an implicit index signature and is therefore assignable to
 * `JsonLd` (`Record<string, unknown>`), which keeps `SeoService.setJsonLd`
 * free of `any` (rule 4).
 */

export type PostalAddressSchema = {
    '@type': 'PostalAddress';
    addressLocality: string;
    addressCountry?: string;
};

export type OrganizationSchema = {
    '@type': 'Organization';
    name: string;
    url?: string;
};

export type EducationalOrganizationSchema = {
    '@type': 'EducationalOrganization';
    name: string;
};

export type OccupationSchema = {
    '@type': 'Occupation';
    name: string;
    skills?: string[];
};

/**
 * The machine-readable "open to work" signal (#71 AC5). schema.org models a
 * person LOOKING for something as `Person.seeks` → `Demand`. `JobPosting` is
 * deliberately NOT used: it describes a vacancy offered by a hiring
 * organization (Google's job-posting rich result requires `hiringOrganization`,
 * `datePosted`, `jobLocation`), so a candidate emitting one would be publishing
 * a fake vacancy.
 */
export type DemandSchema = {
    '@type': 'Demand';
    name: string;
};

export type PersonSchema = {
    '@context': 'https://schema.org';
    '@type': 'Person';
    name: string;
    jobTitle?: string;
    url?: string;
    description?: string;
    sameAs?: string[];
    knowsAbout?: string[];
    hasOccupation?: OccupationSchema;
    worksFor?: OrganizationSchema;
    alumniOf?: EducationalOrganizationSchema[];
    address?: PostalAddressSchema;
    seeks?: DemandSchema;
};

/**
 * A four-digit year anywhere in `endDate` means the role has ENDED; its absence
 * means it is ongoing. Locale-independent by design — the demo profiles alone
 * say "Present" (en) and "Heute" (de), and a scraped profile may say anything,
 * so matching a word list would silently mis-classify a forker's data. Same
 * idea as `YearExtractPipe`.
 */
const YEAR = /\b(19|20)\d{2}\b/;

/** Labels for the availability states that constitute an open-to-work signal. */
const SEEKS_LABEL: Record<string, string | undefined> = {
    open: 'Open to new opportunities',
    listening: 'Open to hearing about new opportunities',
};

export function isOngoingRole(experience: Experience): boolean {
    return !YEAR.test(experience.endDate ?? '');
}

/** `"Berlin, Germany"` → locality + country; a single token yields locality only. */
export function buildAddress(location: string | undefined): PostalAddressSchema | undefined {
    const parts = (location ?? '')
        .split(',')
        .map((part) => part.trim())
        .filter((part) => part.length > 0);
    if (parts.length === 0) {
        return undefined;
    }
    const address: PostalAddressSchema = { '@type': 'PostalAddress', addressLocality: parts[0] };
    if (parts.length > 1) {
        address.addressCountry = parts[parts.length - 1];
    }
    return address;
}

/** The current employer: the first named role that has not ended. */
export function buildWorksFor(experience: Experience[] | undefined): OrganizationSchema | undefined {
    const current = (experience ?? []).find((role) => role.company && isOngoingRole(role));
    if (!current) {
        return undefined;
    }
    const organization: OrganizationSchema = { '@type': 'Organization', name: current.company };
    const url = (current.companyLinkedInUrl ?? '').trim();
    if (url) {
        organization.url = url;
    }
    return organization;
}

export function buildAlumniOf(
    education: Education[] | undefined,
): EducationalOrganizationSchema[] | undefined {
    const schools = (education ?? [])
        .map((entry) => (entry.school ?? '').trim())
        .filter((school) => school.length > 0);
    return schools.length
        ? schools.map((name) => ({ '@type': 'EducationalOrganization' as const, name }))
        : undefined;
}

export function buildSeeks(availability: string): DemandSchema | undefined {
    const name = SEEKS_LABEL[availability];
    return name ? { '@type': 'Demand', name } : undefined;
}

/**
 * Assemble the enriched `Person` node. Every optional property is OMITTED
 * rather than emitted empty — a `"worksFor": {}` or `"address": null` fails
 * schema.org validation, while an absent property is simply not claimed.
 */
export function buildPersonSchema(profile: Profile, site: SiteConfig): PersonSchema {
    const schema: PersonSchema = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        name: profile.name,
    };

    if (profile.headline) {
        schema.jobTitle = profile.headline;
        schema.hasOccupation = { '@type': 'Occupation', name: profile.headline };
        if (profile.skills?.length) {
            schema.hasOccupation.skills = profile.skills;
        }
    }
    if (site.siteUrl) {
        schema.url = site.siteUrl;
    }
    if (profile.about) {
        schema.description = profile.about;
    }
    if (site.socialLinks?.length) {
        schema.sameAs = site.socialLinks;
    }
    if (profile.skills?.length) {
        schema.knowsAbout = profile.skills;
    }

    const worksFor = buildWorksFor(profile.experience);
    if (worksFor) {
        schema.worksFor = worksFor;
    }
    const alumniOf = buildAlumniOf(profile.education);
    if (alumniOf) {
        schema.alumniOf = alumniOf;
    }
    const address = buildAddress(profile.location);
    if (address) {
        schema.address = address;
    }
    const seeks = buildSeeks(site.availability);
    if (seeks) {
        schema.seeks = seeks;
    }

    return schema;
}
