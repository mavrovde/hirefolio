import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AdminLinkedinComponent } from './admin-linkedin.component';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { LinkedinService, LinkedInPost } from '../../../services/linkedin.service';
import { of, throwError } from 'rxjs';
import { CommonModule } from '@angular/common';
import { vi } from 'vitest';

class MockLinkedinService {
    syncProfile() { return of({}); }
    getPosts() { return of([]); }
    transferPost() { return of({ id: 0, message: '' }); }
}

describe('AdminLinkedinComponent', () => {
    let component: AdminLinkedinComponent;
    let fixture: ComponentFixture<AdminLinkedinComponent>;
    let mockLinkedinService: LinkedinService;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [AdminLinkedinComponent, HttpClientTestingModule, CommonModule],
            providers: [
                { provide: LinkedinService, useClass: MockLinkedinService }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(AdminLinkedinComponent);
        component = fixture.componentInstance;
        mockLinkedinService = TestBed.inject(LinkedinService);

        // Clear message display timeout delay for tests
        component.clearMessageAfterDelay = vi.fn();

        // Set default returns to prevent undefined subscribe errors during initialization
        vi.spyOn(mockLinkedinService, 'syncProfile').mockReturnValue(of({}));
        vi.spyOn(mockLinkedinService, 'getPosts').mockReturnValue(of([]));
        vi.spyOn(mockLinkedinService, 'transferPost').mockReturnValue(of({ id: 0, message: '' }));

        fixture.detectChanges();
    });

    afterEach(() => {
        component.statusMessage = '';
    });

    it('should create', () => {
        expect(component).toBeTruthy();
        expect(component.activeTab).toBe('posts');
    });

    it('should change tabs', () => {
        component.setTab('profile');
        expect(component.activeTab).toBe('profile');
    });

    it('should sync profile successfully', () => {
        const mockData = { name: 'Test User' };
        vi.spyOn(mockLinkedinService, 'syncProfile').mockReturnValue(of(mockData));

        component.syncProfile();

        // As `of` is synchronous, we directly check the final state.
        expect(component.isSyncingProfile).toBe(false);
        expect(component.profileData).toEqual(mockData);
        expect(component.statusMessage).toBe('Profile synced successfully.');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should handle profile sync error', () => {
        vi.spyOn(mockLinkedinService, 'syncProfile').mockReturnValue(throwError(() => new Error('Error')));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        component.syncProfile();

        expect(component.isSyncingProfile).toBe(false);
        expect(component.statusMessage).toBe('Error syncing profile.');
        expect(console.error).toHaveBeenCalled();
    });

    it('should fetch posts successfully', () => {
        const mockPosts: LinkedInPost[] = [{ id: '1', content: 'Test post', time: '1d', imageUrl: '' }];
        vi.spyOn(mockLinkedinService, 'getPosts').mockReturnValue(of(mockPosts));

        component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.posts).toEqual(mockPosts);
        expect(component.statusMessage).toBe('Fetched 1 posts.');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should handle fetch posts error', () => {
        vi.spyOn(mockLinkedinService, 'getPosts').mockReturnValue(throwError(() => new Error('Error')));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.statusMessage).toBe('Error fetching posts.');
        expect(console.error).toHaveBeenCalled();
    });

    it('should transfer post successfully', () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        const mockResponse = { id: 123, message: '' };
        component.posts = [mockPost];

        vi.spyOn(mockLinkedinService, 'transferPost').mockReturnValue(of(mockResponse));

        component.transferPost(mockPost);

        expect(component.transferringPostId).toBeNull();
        expect(component.posts.length).toBe(0);
        expect(component.statusMessage).toBe('Transferred as draft 123');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should not transfer if already transferring', () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        component.transferringPostId = '1';

        vi.spyOn(mockLinkedinService, 'transferPost');
        component.transferPost(mockPost);

        expect(mockLinkedinService.transferPost).not.toHaveBeenCalled();
    });

    it('should handle transfer post error', () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        vi.spyOn(mockLinkedinService, 'transferPost').mockReturnValue(throwError(() => new Error('Error')));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        component.transferPost(mockPost);

        expect(component.transferringPostId).toBeNull();
        expect(component.statusMessage).toBe('Error transferring post.');
        expect(console.error).toHaveBeenCalled();
    });

    it('should truncate exact text', () => {
        const exact150 = 'A'.repeat(150);
        expect(component.truncateText(exact150)).toBe(exact150);
    });

    it('should truncate long text', () => {
        const longText = 'A'.repeat(200);
        expect(component.truncateText(longText)).toBe('A'.repeat(150) + '...');
    });

    it('should return empty string for falsy text', () => {
        expect(component.truncateText(null as any)).toBe('');
        expect(component.truncateText('')).toBe('');
    });
});
