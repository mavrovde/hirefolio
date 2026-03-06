import { TestBed } from '@angular/core/testing';
import { LinkedinService, LinkedInPost } from './linkedin.service';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';
import { vi } from 'vitest';

describe('LinkedinService', () => {
    let service: LinkedinService;
    let authServiceSpy: any;

    beforeEach(() => {
        authServiceSpy = { getToken: vi.fn().mockReturnValue('test-token') };

        TestBed.resetTestingModule();
        TestBed.configureTestingModule({
            providers: [
                LinkedinService,
                { provide: AuthService, useValue: authServiceSpy }
            ]
        });
        service = TestBed.inject(LinkedinService);
        globalThis.fetch = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should sync profile data', async () => {
        const mockProfileData = { name: 'Test User', skills: ['Angular'] };
        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockProfileData)
        });

        const data = await service.syncProfile();

        expect(data).toEqual(mockProfileData);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/profile-sync`,
            { headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer test-token' } }
        );
    });

    it('should fetch posts', async () => {
        const mockPosts: LinkedInPost[] = [
            { id: '1', content: 'Post 1', time: '1d', imageUrl: '' },
            { id: '2', content: 'Post 2', time: '2d', imageUrl: '' }
        ];

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockPosts)
        });

        const posts = await service.getPosts();

        expect(posts).toEqual(mockPosts);
        expect(posts.length).toBe(2);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/posts`,
            expect.any(Object)
        );
    });

    it('should transfer a post', async () => {
        const mockPost: LinkedInPost = { id: 'urn:li:activity:1234', content: 'Post 1', time: '1d', imageUrl: '', urn: '1234' };
        const mockResponse = { id: 123, message: 'Transfer successful' };

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        const res = await service.transferPost(mockPost);

        expect(res).toEqual(mockResponse);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/transfer-post`,
            {
                method: 'POST',
                headers: expect.any(Object),
                body: JSON.stringify({
                    content: mockPost.content,
                    image_url: null,
                    urn: '1234'
                })
            }
        );
    });
});
