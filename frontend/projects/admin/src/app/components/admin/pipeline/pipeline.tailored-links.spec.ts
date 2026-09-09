import { DATE_PIPE_DEFAULT_OPTIONS } from '@angular/common';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { PipelineComponent } from './pipeline.component';
import { Opportunity, OpportunitiesService } from '../../../services/opportunities.service';
import { AdminCvService, CvVersion } from '../../../services/admin-cv.service';
import { TailoredLink, TailoredLinksService } from '../../../services/tailored-links.service';

/** Tailored application links in the pipeline detail panel (#250, criterion 1). */

function makeOpp(overrides: Partial<Opportunity> = {}): Opportunity {
    return {
        id: 'o1',
        company: 'Acme',
        role_title: 'Staff Engineer',
        stage: 'lead',
        source: 'recruiter_outreach',
        recruiter_name: null,
        recruiter_email: null,
        link: null,
        salary_note: null,
        next_action: null,
        next_action_date: null,
        sent_cv_id: null,
        sent_cv_at: null,
        created_at: '2026-09-05T10:00:00Z',
        updated_at: '2026-09-05T10:30:00Z',
        notes: [],
        ...overrides,
    };
}

function makeCv(overrides: Partial<CvVersion> = {}): CvVersion {
    return {
        id: 'cv1',
        filename: 'acme-v1.pdf',
        version: 'acme-v1',
        is_active: false,
        created_at: '2026-09-01T09:00:00Z',
        ...overrides,
    };
}

function makeLink(overrides: Partial<TailoredLink> = {}): TailoredLink {
    return {
        id: 'l1',
        opportunity_id: 'o1',
        slug: 'acme-staff-eng',
        path: '/for/acme-staff-eng',
        url: 'https://example.com/for/acme-staff-eng',
        cv_document_id: null,
        cv_version: null,
        cv_filename: null,
        headline_note: null,
        highlighted_skills: [],
        highlighted_projects: [],
        enabled: true,
        expires_at: null,
        visit_count: 0,
        cv_download_count: 0,
        last_visited_at: null,
        created_at: '2026-09-08T10:00:00Z',
        updated_at: '2026-09-08T10:00:00Z',
        ...overrides,
    };
}

describe('PipelineComponent — tailored links (#250)', () => {
    let fixture: ComponentFixture<PipelineComponent>;
    let component: PipelineComponent;
    let serviceSpy: Record<string, ReturnType<typeof vi.fn>>;
    let cvSpy: Record<'getVersions', ReturnType<typeof vi.fn>>;
    let tailoredSpy: Record<'listFor' | 'create' | 'update' | 'remove', ReturnType<typeof vi.fn>>;

    beforeEach(async () => {
        serviceSpy = {
            list: vi.fn().mockReturnValue(of({ items: [makeOpp()], total: 1, page: 1, pages: 1 })),
            get: vi.fn().mockReturnValue(of(makeOpp())),
            create: vi.fn(),
            moveStage: vi.fn(),
            addNote: vi.fn(),
            recordCvSent: vi.fn(),
        };
        cvSpy = {
            getVersions: vi
                .fn()
                .mockReturnValue(of({ items: [makeCv()], total: 1, page: 1, pages: 1 })),
        };
        tailoredSpy = {
            listFor: vi.fn().mockReturnValue(of([makeLink()])),
            create: vi.fn().mockReturnValue(of(makeLink({ id: 'l2', slug: 'fresh' }))),
            update: vi.fn().mockReturnValue(of(makeLink({ enabled: false }))),
            remove: vi.fn().mockReturnValue(of(void 0)),
        };

        await TestBed.configureTestingModule({
            imports: [PipelineComponent],
            providers: [
                { provide: OpportunitiesService, useValue: serviceSpy },
                { provide: AdminCvService, useValue: cvSpy },
                { provide: TailoredLinksService, useValue: tailoredSpy },
            ],
        }).compileComponents();

        fixture = TestBed.createComponent(PipelineComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('loads the links of the opened opportunity and renders their signal', () => {
        tailoredSpy.listFor.mockReturnValue(
            of([makeLink({ visit_count: 2, cv_download_count: 1, cv_version: 'acme-v1' })])
        );
        component.open(makeOpp());
        fixture.detectChanges();

        expect(tailoredSpy.listFor).toHaveBeenCalledWith('o1');
        const row: HTMLElement = fixture.nativeElement.querySelector('[data-testid="link-l1"]');
        expect(row.textContent).toContain('https://example.com/for/acme-staff-eng');
        expect(row.textContent).toContain('2 visits');
        expect(row.textContent).toContain('1 CV download');
        expect(row.textContent).toContain('variant acme-v1');
        expect(row.textContent).toContain('live');
    });

    it('never carries a previous opportunity’s links into the next panel', () => {
        component.open(makeOpp());
        expect(component.links.length).toBe(1);

        // A slow list response for the SECOND opportunity must not leave the
        // first one's private URLs on screen under the wrong company header.
        tailoredSpy.listFor.mockReturnValue(throwError(() => new Error('slow')));
        component.open(makeOpp({ id: 'o2', company: 'Globex' }));
        expect(component.links).toEqual([]);
    });

    it('mints a link from the draft, generating the slug when none is given', () => {
        component.open(makeOpp());
        component.linkDraft = {
            slug: '  ',
            cv_document_id: 'cv1',
            headline_note: '  Hi Acme team  ',
            highlighted_skills: 'Angular, Python',
            highlighted_projects: 'Acme',
            expires_at: '2026-12-01',
        };
        component.createLink();

        expect(tailoredSpy.create).toHaveBeenCalledWith({
            opportunity_id: 'o1',
            slug: null,
            cv_document_id: 'cv1',
            headline_note: 'Hi Acme team',
            highlighted_skills: ['Angular', 'Python'],
            highlighted_projects: ['Acme'],
            // Forwarded verbatim — see 'sends the picked day as a bare date'
            // below for why the panel must not turn this into an instant.
            expires_at: '2026-12-01',
        });
        expect(component.links[0].id).toBe('l2');
        expect(component.showLinkForm).toBe(false);
        expect(component.linkDraft.headline_note).toBe('');
    });

    it('sends the picked day as a bare date, never a fabricated instant', () => {
        // The contract behind the expiry off-by-one (#323 review, finding 1):
        // `<input type="date">` yields `YYYY-MM-DD` and the panel forwards it
        // UNCHANGED, because the backend is what defines what a bare day means
        // — `normalize_expiry` resolves it to the LAST microsecond of that day,
        // so "expires 2026-12-01" is live through all of 2026-12-01. If this
        // ever starts sending a timestamp (`…T00:00:00Z`), the backend honours
        // it literally and the link dies a day early: the exact bug that made a
        // link minted with today's date 404 the moment it was sent.
        component.open(makeOpp());
        component.linkDraft = { ...component.linkDraft, expires_at: '2026-12-01' };
        component.createLink();

        const payload = tailoredSpy.create.mock.calls[0][0];
        expect(payload.expires_at).toBe('2026-12-01');
        expect(payload.expires_at).not.toContain('T');
    });

    it('sends explicit nulls for the empty optional controls', () => {
        component.open(makeOpp());
        component.createLink();

        expect(tailoredSpy.create).toHaveBeenCalledWith(
            expect.objectContaining({
                cv_document_id: null,
                headline_note: null,
                expires_at: null,
                highlighted_skills: [],
            })
        );
    });

    it('names the duplicate-slug conflict instead of a generic failure', () => {
        tailoredSpy.create.mockReturnValue(throwError(() => ({ status: 409 })));
        component.open(makeOpp());
        component.createLink();

        expect(component.error).toBe('That slug is already taken — pick another one');
        expect(component.savingLink).toBe(false);
    });

    it('surfaces any other mint failure', () => {
        tailoredSpy.create.mockReturnValue(throwError(() => ({ status: 500 })));
        component.open(makeOpp());
        component.createLink();

        expect(component.error).toBe('Failed to create the tailored link');
    });

    it('refuses to mint without a selected opportunity, or while one is in flight', () => {
        component.createLink();
        expect(tailoredSpy.create).not.toHaveBeenCalled();

        component.open(makeOpp());
        component.savingLink = true;
        component.createLink();
        expect(tailoredSpy.create).not.toHaveBeenCalled();
    });

    it('disables a link — the revocation the recipient sees as a 404', () => {
        // Two links on purpose: a toggle must replace exactly the one row and
        // leave its sibling untouched.
        tailoredSpy.listFor.mockReturnValue(
            of([makeLink(), makeLink({ id: 'l9', slug: 'other', enabled: true })])
        );
        component.open(makeOpp());
        component.toggleLink(component.links[0]);

        expect(tailoredSpy.update).toHaveBeenCalledWith('l1', { enabled: false });
        expect(component.links[0].enabled).toBe(false);
        expect(component.links[1]).toEqual(expect.objectContaining({ id: 'l9', enabled: true }));
    });

    it('surfaces a toggle failure', () => {
        tailoredSpy.update.mockReturnValue(throwError(() => new Error('x')));
        component.open(makeOpp());
        component.toggleLink(component.links[0]);

        expect(component.error).toBe('Failed to update the tailored link');
    });

    it('deletes a link and drops only that one from the list', () => {
        const confirmed = vi.spyOn(window, 'confirm').mockReturnValue(true);
        tailoredSpy.listFor.mockReturnValue(of([makeLink(), makeLink({ id: 'l9' })]));
        component.open(makeOpp());
        component.deleteLink(component.links[0]);

        expect(confirmed).toHaveBeenCalledWith(
            'Delete the tailored link /for/acme-staff-eng? This cannot be undone.'
        );
        expect(tailoredSpy.remove).toHaveBeenCalledWith('l1');
        expect(component.links.map((l) => l.id)).toEqual(['l9']);
    });

    it('does not delete a shared URL when the confirmation is dismissed', () => {
        // Delete is irreversible and the URL is already in a recruiter's inbox:
        // a mis-click turns a live page into a permanent 404, while the
        // recoverable `Disable` sits in the same row (#323 review, finding 3).
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        component.open(makeOpp());
        component.deleteLink(component.links[0]);

        expect(tailoredSpy.remove).not.toHaveBeenCalled();
        expect(component.links.map((l) => l.id)).toEqual(['l1']);
        expect(component.error).toBeNull();
    });

    it('surfaces a delete failure', () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        tailoredSpy.remove.mockReturnValue(throwError(() => new Error('x')));
        component.open(makeOpp());
        component.deleteLink(component.links[0]);

        expect(component.error).toBe('Failed to delete the tailored link');
    });

    it('surfaces a link-list failure without breaking the panel', () => {
        tailoredSpy.listFor.mockReturnValue(throwError(() => new Error('x')));
        component.open(makeOpp());

        expect(component.links).toEqual([]);
        expect(component.selected).toBeTruthy();
    });

    it('clears the panel state when the detail view closes', () => {
        component.open(makeOpp());
        component.showLinkForm = true;
        component.copiedLinkId = 'l1';
        component.close();

        expect(component.links).toEqual([]);
        expect(component.showLinkForm).toBe(false);
        expect(component.copiedLinkId).toBeNull();
    });

    describe('the expiry the panel shows is the day that was picked', () => {
        // A bare day resolves to the LAST instant of that day in UTC. Rendered
        // in a browser east of UTC, that instant lands on the NEXT calendar
        // day — so without an explicit `'UTC'` on the date pipe the panel would
        // report an expiry one day later than the one the owner typed, which is
        // the same off-by-one as #323's finding 1 wearing a different hat.
        beforeEach(async () => {
            TestBed.resetTestingModule();
            await TestBed.configureTestingModule({
                imports: [PipelineComponent],
                providers: [
                    { provide: OpportunitiesService, useValue: serviceSpy },
                    { provide: AdminCvService, useValue: cvSpy },
                    { provide: TailoredLinksService, useValue: tailoredSpy },
                    // Pin the "browser" 9 hours east of UTC so the assertion
                    // cannot pass by accident on a machine that happens to run
                    // in UTC (as CI does).
                    { provide: DATE_PIPE_DEFAULT_OPTIONS, useValue: { timezone: '+0900' } },
                ],
            }).compileComponents();
            fixture = TestBed.createComponent(PipelineComponent);
            component = fixture.componentInstance;
            fixture.detectChanges();
        });

        it('shows the picked day, not the next one, east of UTC', () => {
            tailoredSpy.listFor.mockReturnValue(
                of([makeLink({ expires_at: '2026-12-01T23:59:59.999999Z' })])
            );
            component.open(makeOpp());
            fixture.detectChanges();

            const row: HTMLElement = fixture.nativeElement.querySelector(
                '[data-testid="link-l1"]'
            );
            expect(row.textContent).toContain('expires Dec 1, 2026');
            expect(row.textContent).not.toContain('Dec 2, 2026');
        });
    });

    describe('copy to clipboard', () => {
        function withClipboard(value: unknown) {
            Object.defineProperty(navigator, 'clipboard', {
                value,
                configurable: true,
            });
        }

        it('copies the absolute URL and marks the row', async () => {
            const writeText = vi.fn().mockResolvedValue(undefined);
            withClipboard({ writeText });
            component.open(makeOpp());

            component.copyLink(component.links[0]);
            await Promise.resolve();

            expect(writeText).toHaveBeenCalledWith('https://example.com/for/acme-staff-eng');
            expect(component.copiedLinkId).toBe('l1');
        });

        it('says so when the clipboard rejects', async () => {
            withClipboard({ writeText: vi.fn().mockRejectedValue(new Error('denied')) });
            component.open(makeOpp());

            component.copyLink(component.links[0]);
            await Promise.resolve();
            await Promise.resolve();

            expect(component.error).toBe('Clipboard unavailable — copy the URL manually');
            expect(component.copiedLinkId).toBeNull();
        });

        it('says so when there is no clipboard API at all (insecure origin)', () => {
            withClipboard(undefined);
            component.open(makeOpp());

            component.copyLink(component.links[0]);

            expect(component.error).toBe('Clipboard unavailable — copy the URL manually');
        });
    });
});
