import { TestBed, ComponentFixture } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { PipelineComponent } from './pipeline.component';
import { OpportunitiesService, Opportunity } from '../../../services/opportunities.service';

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
        created_at: 'now',
        updated_at: 'now',
        notes: [],
        ...overrides,
    };
}

describe('PipelineComponent', () => {
    let fixture: ComponentFixture<PipelineComponent>;
    let component: PipelineComponent;
    let serviceSpy: Record<'list' | 'get' | 'create' | 'moveStage' | 'addNote', ReturnType<typeof vi.fn>>;

    beforeEach(async () => {
        serviceSpy = {
            list: vi.fn().mockReturnValue(of({ items: [makeOpp()], total: 1, page: 1, pages: 1 })),
            get: vi.fn(),
            create: vi.fn(),
            moveStage: vi.fn(),
            addNote: vi.fn(),
        };
        await TestBed.configureTestingModule({
            imports: [PipelineComponent],
            providers: [{ provide: OpportunitiesService, useValue: serviceSpy }],
        }).compileComponents();

        fixture = TestBed.createComponent(PipelineComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('loads and groups by stage', () => {
        expect(component.all.length).toBe(1);
        expect(component.byStage('lead').length).toBe(1);
        expect(component.byStage('offer').length).toBe(0);
    });

    it('surfaces load errors', () => {
        serviceSpy.list.mockReturnValue(throwError(() => new Error('x')));
        component.load();
        expect(component.error).toBe('Failed to load the pipeline');
        expect(component.loading).toBe(false);
    });

    it('creates from the draft and prepends the result', () => {
        serviceSpy.create.mockReturnValue(of(makeOpp({ id: 'o2', company: 'New Co' })));
        component.draft = { company: 'New Co', role_title: 'Dev', source: 'referral' };
        component.create();
        expect(serviceSpy.create).toHaveBeenCalledWith(
            expect.objectContaining({ company: 'New Co' })
        );
        expect(component.all[0].id).toBe('o2');
        expect(component.showCreate).toBe(false);
    });

    it('refuses to create from a blank draft', () => {
        component.draft = { company: '  ', role_title: '', source: 'referral' };
        component.create();
        expect(serviceSpy.create).not.toHaveBeenCalled();
    });

    it('surfaces create errors', () => {
        serviceSpy.create.mockReturnValue(throwError(() => new Error('x')));
        component.draft = { company: 'C', role_title: 'R', source: 'referral' };
        component.create();
        expect(component.error).toBe('Failed to create the opportunity');
    });

    it('opens the detail panel with the full record', () => {
        serviceSpy.get.mockReturnValue(of(makeOpp({ notes: [{ id: 'n1', interaction_id: null, body: 'note', created_at: 'now' }] })));
        component.open(component.all[0]);
        expect(component.selected?.notes.length).toBe(1);
        component.close();
        expect(component.selected).toBeNull();
    });

    it('surfaces open errors', () => {
        serviceSpy.get.mockReturnValue(throwError(() => new Error('x')));
        component.open(component.all[0]);
        expect(component.error).toBe('Failed to load the opportunity');
    });

    it('moves the stage and syncs board + panel (other cards untouched)', () => {
        const other = makeOpp({ id: 'o9', company: 'Other Co' });
        component.all = [component.all[0], other];
        component.selected = makeOpp();
        serviceSpy.moveStage.mockReturnValue(of(makeOpp({ stage: 'offer' })));
        component.moveStage('offer');
        expect(serviceSpy.moveStage).toHaveBeenCalledWith('o1', 'offer');
        expect(component.selected?.stage).toBe('offer');
        expect(component.all[0].stage).toBe('offer');
        expect(component.all[1]).toBe(other);
    });

    it('ignores same-stage moves and no selection', () => {
        component.selected = null;
        component.moveStage('offer');
        component.selected = makeOpp();
        component.moveStage('lead');
        expect(serviceSpy.moveStage).not.toHaveBeenCalled();
    });

    it('surfaces stage-move errors', () => {
        component.selected = makeOpp();
        serviceSpy.moveStage.mockReturnValue(throwError(() => new Error('x')));
        component.moveStage('offer');
        expect(component.error).toBe('Failed to move the stage');
    });

    it('adds a note and clears the draft', () => {
        component.selected = makeOpp();
        component.noteDraft = 'Call notes';
        serviceSpy.addNote.mockReturnValue(
            of(makeOpp({ notes: [{ id: 'n1', interaction_id: null, body: 'Call notes', created_at: 'now' }] }))
        );
        component.addNote();
        expect(component.selected?.notes.length).toBe(1);
        expect(component.noteDraft).toBe('');
    });

    it('refuses empty notes and surfaces note errors', () => {
        component.selected = null;
        component.noteDraft = 'orphan note';
        component.addNote();
        expect(serviceSpy.addNote).not.toHaveBeenCalled();

        component.selected = makeOpp();
        component.noteDraft = '   ';
        component.addNote();
        expect(serviceSpy.addNote).not.toHaveBeenCalled();

        component.noteDraft = 'x';
        serviceSpy.addNote.mockReturnValue(throwError(() => new Error('x')));
        component.addNote();
        expect(component.error).toBe('Failed to add the note');
    });
});
