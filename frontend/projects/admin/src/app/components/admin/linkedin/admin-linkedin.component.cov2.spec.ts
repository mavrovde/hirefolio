import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AdminLinkedinComponent } from './admin-linkedin.component';
import { LinkedinService } from '../../../services/linkedin.service';
import { CommonModule } from '@angular/common';
import { vi } from 'vitest';

class MockLinkedinService {
    async syncProfile() { return {}; }
    async getPosts() { return []; }
    async transferPost() { return { id: 0, message: '' }; }
    async getStatus() { return { logged_in: false }; }
    async login() { return {}; }
}

describe('AdminLinkedinComponent (cov2)', () => {
    let component: AdminLinkedinComponent;
    let fixture: ComponentFixture<AdminLinkedinComponent>;
    let mockLinkedinService: LinkedinService;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [AdminLinkedinComponent, CommonModule],
            providers: [
                { provide: LinkedinService, useClass: MockLinkedinService }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(AdminLinkedinComponent);
        component = fixture.componentInstance;
        mockLinkedinService = TestBed.inject(LinkedinService);

        component.clearMessageAfterDelay = vi.fn();
        fixture.detectChanges();
    });

    it('should use fallback message when fetch posts error has no message', async () => {
        // Reject with an object whose `.message` is falsy so the `|| 'Error fetching posts.'`
        // branch on line 100 is exercised.
        vi.spyOn(mockLinkedinService, 'getPosts').mockRejectedValue({});
        vi.spyOn(console, 'error').mockImplementation(() => { });

        await component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.statusMessage).toBe('Error fetching posts.');
        expect(console.error).toHaveBeenCalled();
    });
});
