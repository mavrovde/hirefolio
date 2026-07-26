import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AdminLinkedinComponent } from './admin-linkedin.component';
import { LinkedinService, LinkedInPost } from '../../../services/linkedin.service';
import { CommonModule } from '@angular/common';
import { vi } from 'vitest';

class MockLinkedinService {
    async syncProfile() { return {}; }
    async getPosts() { return []; }
    async transferPost() { return { id: 0, message: '' }; }
    async getStatus() { return { logged_in: false }; }
    async login() { return {}; }
    async importPostsJson() { return { created: 0, updated: 0, skipped: 0, count: 0 }; }
}

describe('AdminLinkedinComponent', () => {
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

        // Clear message display timeout delay for tests
        component.clearMessageAfterDelay = vi.fn();

        // Set default returns
        vi.spyOn(mockLinkedinService, 'syncProfile').mockResolvedValue({});
        vi.spyOn(mockLinkedinService, 'getPosts').mockResolvedValue([]);
        vi.spyOn(mockLinkedinService, 'transferPost').mockResolvedValue({ id: 0, message: '' });

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

    it('should sync profile successfully', async () => {
        const mockData = { name: 'Test User' };
        vi.spyOn(mockLinkedinService, 'syncProfile').mockResolvedValue(mockData);

        await component.syncProfile();

        expect(component.isSyncingProfile).toBe(false);
        expect(component.profileData).toEqual(mockData);
        expect(component.statusMessage).toBe('Profile synced successfully.');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should handle profile sync error', async () => {
        vi.spyOn(mockLinkedinService, 'syncProfile').mockRejectedValue(new Error('Error'));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        await component.syncProfile();

        expect(component.isSyncingProfile).toBe(false);
        expect(component.statusMessage).toBe('Error syncing profile.');
        expect(console.error).toHaveBeenCalled();
    });

    it('should fetch posts successfully', async () => {
        const mockPosts: LinkedInPost[] = [{ id: '1', content: 'Test post', time: '1d', imageUrl: '' }];
        vi.spyOn(mockLinkedinService, 'getPosts').mockResolvedValue(mockPosts);

        await component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.posts).toEqual(mockPosts);
        expect(component.statusMessage).toBe('Fetched 1 posts.');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should handle fetch posts error', async () => {
        vi.spyOn(mockLinkedinService, 'getPosts').mockRejectedValue(new Error('Error'));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        await component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.statusMessage).toBe('Error');
        expect(console.error).toHaveBeenCalled();
    });

    it('should extract backend error message on fetch posts error', async () => {
        const backendError = new Error('Scraper blocked');
        vi.spyOn(mockLinkedinService, 'getPosts').mockRejectedValue(backendError);
        vi.spyOn(console, 'error').mockImplementation(() => { });

        await component.fetchPosts();

        expect(component.isFetchingPosts).toBe(false);
        expect(component.statusMessage).toBe('Scraper blocked');
    });

    it('should transfer post successfully', async () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        const mockResponse = { id: 123, message: '' };
        component.posts = [mockPost];

        vi.spyOn(mockLinkedinService, 'transferPost').mockResolvedValue(mockResponse);

        await component.transferPost(mockPost);

        expect(component.transferringPostId).toBeNull();
        expect(component.posts.length).toBe(0);
        expect(component.statusMessage).toBe('Transferred as draft 123');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should not transfer if already transferring', async () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        component.transferringPostId = '1';

        vi.spyOn(mockLinkedinService, 'transferPost');
        await component.transferPost(mockPost);

        expect(mockLinkedinService.transferPost).not.toHaveBeenCalled();
    });

    it('should handle transfer post error', async () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post', time: '1d', imageUrl: '' };
        vi.spyOn(mockLinkedinService, 'transferPost').mockRejectedValue(new Error('Error'));
        vi.spyOn(console, 'error').mockImplementation(() => { });

        await component.transferPost(mockPost);

        expect(component.transferringPostId).toBeNull();
        expect(component.statusMessage).toBe('Error transferring post.');
        expect(console.error).toHaveBeenCalled();
    });

    it('should clear message after delay', () => {
        vi.useFakeTimers();
        // Restore actual implementation for this test
        component.clearMessageAfterDelay = AdminLinkedinComponent.prototype.clearMessageAfterDelay.bind(component);
        component.statusMessage = 'Test msg';
        component.clearMessageAfterDelay();
        vi.advanceTimersByTime(5000);
        expect(component.statusMessage).toBe('');
        // Clean up
        vi.useRealTimers();
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
    });

    it('should check login status on init successfully', async () => {
        vi.spyOn(mockLinkedinService, 'getStatus').mockResolvedValue({ logged_in: true });
        await component.checkLoginStatus();
        expect(component.isLoggedIn).toBe(true);
    });

    it('should handle login status check error gracefully', async () => {
        vi.spyOn(mockLinkedinService, 'getStatus').mockRejectedValue(new Error('Network error'));
        vi.spyOn(console, 'error').mockImplementation(() => {});
        component.isLoggedIn = false;
        await component.checkLoginStatus();
        expect(component.isLoggedIn).toBe(false);
        expect(console.error).toHaveBeenCalled();
    });

    it('should not login if credentials are missing', async () => {
        component.linkedinUsername = '';
        component.linkedinPassword = '';
        vi.spyOn(mockLinkedinService, 'login');
        await component.login();
        expect(mockLinkedinService.login).not.toHaveBeenCalled();
    });

    it('should login successfully and clear password', async () => {
        component.linkedinUsername = 'testuser';
        component.linkedinPassword = 'mypassword';
        vi.spyOn(mockLinkedinService, 'login').mockResolvedValue({ message: 'Success' });
        
        await component.login();
        
        expect(component.isLoggingIn).toBe(false);
        expect(component.isLoggedIn).toBe(true);
        expect(component.linkedinPassword).toBe('');
        expect(component.statusMessage).toBe('Successfully logged in and session saved.');
        expect(component.clearMessageAfterDelay).toHaveBeenCalled();
    });

    it('should handle login failure and surface error message', async () => {
        component.linkedinUsername = 'testuser';
        component.linkedinPassword = 'wrongpassword';
        vi.spyOn(mockLinkedinService, 'login').mockRejectedValue(new Error('Invalid credentials'));
        
        await component.login();
        
        expect(component.isLoggingIn).toBe(false);
        expect(component.isLoggedIn).toBe(false);
        expect(component.linkedinPassword).toBe('wrongpassword'); // Password is not cleared on failure
        expect(component.statusMessage).toBe('Invalid credentials');
    });

    it('should handle login failure with default fallback message', async () => {
        component.linkedinUsername = 'testuser';
        component.linkedinPassword = 'wrongpassword';
        vi.spyOn(mockLinkedinService, 'login').mockRejectedValue({});
        
        await component.login();
        
        expect(component.isLoggingIn).toBe(false);
        expect(component.statusMessage).toBe('Login failed. Note: MFA is not currently supported.');
    });

    it('should select a posts JSON file', () => {
        const file = new File(['[]'], 'posts_data.json', { type: 'application/json' });
        component.onPostsFileSelected({ target: { files: [file] } } as unknown as Event);
        expect(component.selectedPostsFile).toBe(file);
    });

    it('should ignore an empty posts file selection', () => {
        component.onPostsFileSelected({ target: { files: [] } } as unknown as Event);
        expect(component.selectedPostsFile).toBeNull();
    });

    it('should do nothing when uploading posts JSON with no file', async () => {
        const spy = vi.spyOn(mockLinkedinService, 'importPostsJson');
        component.selectedPostsFile = null;
        await component.uploadPostsJson();
        expect(spy).not.toHaveBeenCalled();
    });

    it('should upload posts JSON and report the summary', async () => {
        vi.spyOn(mockLinkedinService, 'importPostsJson').mockResolvedValue({
            created: 2, updated: 1, skipped: 3, count: 6,
        });
        component.selectedPostsFile = new File(['[]'], 'posts_data.json');
        await component.uploadPostsJson();
        expect(component.statusMessage).toContain('Imported 6 posts');
        expect(component.statusMessage).toContain('2 created');
        expect(component.selectedPostsFile).toBeNull();
        expect(component.isUploadingPostsJson).toBe(false);
    });

    it('should report an error when posts JSON upload fails', async () => {
        vi.spyOn(mockLinkedinService, 'importPostsJson').mockRejectedValue(
            new Error('File is not valid JSON.'),
        );
        component.selectedPostsFile = new File(['x'], 'bad.json');
        await component.uploadPostsJson();
        expect(component.statusMessage).toBe('File is not valid JSON.');
        expect(component.isUploadingPostsJson).toBe(false);
    });

    it('should use a fallback error message when none is provided', async () => {
        vi.spyOn(mockLinkedinService, 'importPostsJson').mockRejectedValue({});
        component.selectedPostsFile = new File(['x'], 'bad.json');
        await component.uploadPostsJson();
        expect(component.statusMessage).toBe('Error uploading posts JSON.');
    });
});
