import { TestBed, ComponentFixture } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { InboxComponent } from './inbox.component';
import { InteractionsService, Interaction } from '../../../services/interactions.service';

function makeInteraction(overrides: Partial<Interaction> = {}): Interaction {
    return {
        id: 'i1',
        source: 'contact_form',
        status: 'new',
        name: 'Rita',
        email: 'rita@a.example',
        company: 'Agency',
        message: 'Hello there',
        payload: null,
        created_at: '2026-09-05T10:00:00Z',
        updated_at: '2026-09-05T10:00:00Z',
        ...overrides,
    };
}

describe('InboxComponent', () => {
    let fixture: ComponentFixture<InboxComponent>;
    let component: InboxComponent;
    let serviceSpy: { list: ReturnType<typeof vi.fn>; updateStatus: ReturnType<typeof vi.fn> };

    beforeEach(async () => {
        serviceSpy = {
            list: vi.fn().mockReturnValue(
                of({ items: [makeInteraction()], total: 1, page: 1, pages: 1 })
            ),
            updateStatus: vi.fn(),
        };
        await TestBed.configureTestingModule({
            imports: [InboxComponent],
            providers: [{ provide: InteractionsService, useValue: serviceSpy }],
        }).compileComponents();

        fixture = TestBed.createComponent(InboxComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('loads the inbox on init', () => {
        expect(serviceSpy.list).toHaveBeenCalledWith({
            status: undefined,
            source: undefined,
            page: 1,
            pageSize: 20,
        });
        expect(component.items.length).toBe(1);
        expect(component.total).toBe(1);
        expect(component.loading).toBe(false);
    });

    it('shows an error when loading fails', () => {
        serviceSpy.list.mockReturnValue(throwError(() => new Error('boom')));
        component.load();
        expect(component.error).toBe('Failed to load the inbox');
        expect(component.loading).toBe(false);
    });

    it('resets to page 1 when filters change', () => {
        component.page = 3;
        component.statusFilter = 'closed';
        component.onFilterChange();
        expect(component.page).toBe(1);
        expect(serviceSpy.list).toHaveBeenLastCalledWith(
            expect.objectContaining({ status: 'closed', page: 1 })
        );
    });

    it('paginates within bounds only', () => {
        component.pages = 3;
        component.goToPage(2);
        expect(component.page).toBe(2);
        component.goToPage(0);
        expect(component.page).toBe(2);
        component.goToPage(4);
        expect(component.page).toBe(2);
        component.goToPage(2); // no-op on same page
        expect(component.page).toBe(2);
    });

    it('toggles message expansion', () => {
        component.toggleExpand('i1');
        expect(component.expandedId).toBe('i1');
        component.toggleExpand('i1');
        expect(component.expandedId).toBeNull();
    });

    it('updates status via the service and reflects the response', () => {
        const row = component.items[0];
        serviceSpy.updateStatus.mockReturnValue(
            of(makeInteraction({ status: 'contacted', updated_at: 'later' }))
        );
        component.setStatus(row, 'contacted');
        expect(serviceSpy.updateStatus).toHaveBeenCalledWith('i1', 'contacted');
        expect(row.status).toBe('contacted');
        expect(row.updated_at).toBe('later');
    });

    it('ignores a status "change" to the same value', () => {
        component.setStatus(component.items[0], 'new');
        expect(serviceSpy.updateStatus).not.toHaveBeenCalled();
    });

    it('surfaces status-update failures', () => {
        serviceSpy.updateStatus.mockReturnValue(throwError(() => new Error('nope')));
        component.setStatus(component.items[0], 'closed');
        expect(component.error).toBe('Failed to update the status');
        expect(component.items[0].status).toBe('new');
    });
});
