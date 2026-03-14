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

    it('should throw with API detail on syncProfile failure', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.resolve({ detail: 'LinkedIn config error: credentials missing' })
        });
        await expect(service.syncProfile()).rejects.toThrow('LinkedIn config error: credentials missing');
    });

    it('should throw with API detail on getPosts failure', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.resolve({ detail: 'LinkedIn posts fetch failed: timeout' })
        });
        await expect(service.getPosts()).rejects.toThrow('LinkedIn posts fetch failed: timeout');
    });

    it('should throw fallback message when no detail in error response', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.reject(new Error('not json'))
        });
        await expect(service.getPosts()).rejects.toThrow('Failed to fetch posts');
    });

    it('should throw with API detail on transferPost failure', async () => {
        const mockPost: LinkedInPost = { id: '1', content: 'Test post' };
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.resolve({ detail: 'Transfer failed: DB Error' })
        });
        await expect(service.transferPost(mockPost)).rejects.toThrow('Transfer failed: DB Error');
    });

    it('should not include Authorization header when no token', () => {
        authServiceSpy.getToken.mockReturnValue(null);
        const svc = TestBed.inject(LinkedinService);
        (globalThis.fetch as any).mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
        svc.syncProfile();
        expect(globalThis.fetch).toHaveBeenCalledWith(
            expect.any(String),
            { headers: { 'Content-Type': 'application/json' } }
        );
    });

    it('should transfer posts in bulk', async () => {
        const mockPosts: LinkedInPost[] = [
            { id: '1', content: 'Post 1', imageUrl: 'https://img1.jpg', urn: 'urn1' },
            { id: '2', content: 'Post 2', imageUrl: '', urn: 'urn2' },
        ];
        const mockResponse = { transferred: 2, ids: [1, 2], message: 'Successfully transferred 2 posts' };

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        const res = await service.transferPosts(mockPosts);

        expect(res).toEqual(mockResponse);
        expect(res.transferred).toBe(2);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/transfer-posts`,
            {
                method: 'POST',
                headers: expect.any(Object),
                body: JSON.stringify([
                    { content: 'Post 1', image_url: 'https://img1.jpg', urn: 'urn1' },
                    { content: 'Post 2', image_url: null, urn: 'urn2' },
                ])
            }
        );
    });

    it('should throw on transferPosts failure', async () => {
        const mockPosts: LinkedInPost[] = [{ id: '1', content: 'Test' }];
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.resolve({ detail: 'Bulk transfer failed: DB Error' })
        });
        await expect(service.transferPosts(mockPosts)).rejects.toThrow('Bulk transfer failed: DB Error');
    });

    it('should transfer post with image URL preserved', async () => {
        const mockPost: LinkedInPost = {
            id: '1',
            content: 'Post with image',
            imageUrl: 'https://media.licdn.com/dms/image/test.jpg',
            urn: 'urn:li:activity:555'
        };
        const mockResponse = { id: 1, message: 'Post transferred successfully' };

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockResponse)
        });

        await service.transferPost(mockPost);

        expect(globalThis.fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                body: JSON.stringify({
                    content: 'Post with image',
                    image_url: 'https://media.licdn.com/dms/image/test.jpg',
                    urn: 'urn:li:activity:555'
                })
            })
        );
    });

    it('should check login status successfully', async () => {
        const mockStatus = { logged_in: true };
        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockStatus)
        });

        const status = await service.getStatus();
        expect(status).toEqual(mockStatus);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/status`,
            expect.any(Object)
        );
    });

    it('should throw with API detail on getStatus failure', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.resolve({ detail: 'Failed to access status' })
        });
        await expect(service.getStatus()).rejects.toThrow('Failed to access status');
    });

    it('should throw default message on getStatus when no detail provided', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.reject(new Error('not json'))
        });
        await expect(service.getStatus()).rejects.toThrow('Failed to check status');
    });

    it('should login successfully', async () => {
        const mockLoginResponse = { message: 'Successfully logged in' };
        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(mockLoginResponse)
        });

        const res = await service.login('testuser', 'testpass');
        expect(res).toEqual(mockLoginResponse);
        expect(globalThis.fetch).toHaveBeenCalledWith(
            `${environment.apiUrl}${environment.apiPrefix}/linkedin/login`,
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ username: 'testuser', password: 'testpass' })
            })
        );
    });

    it('should throw with API detail on login failure', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 401,
            json: () => Promise.resolve({ detail: 'Invalid credentials' })
        });
        await expect(service.login('testuser', 'wrongpass')).rejects.toThrow('Invalid credentials');
    });

    it('should throw default message on login failure when no detail provided', async () => {
        (globalThis.fetch as any).mockResolvedValue({
            ok: false, status: 500,
            json: () => Promise.reject(new Error('not json'))
        });
        await expect(service.login('testuser', 'wrongpass')).rejects.toThrow('Login failed');
    });
});
