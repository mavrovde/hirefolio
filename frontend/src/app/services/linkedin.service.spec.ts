import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { LinkedinService, LinkedInPost } from './linkedin.service';
import { environment } from '../../environments/environment';

describe('LinkedinService', () => {
    let service: LinkedinService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.resetTestingModule();
        TestBed.configureTestingModule({
            providers: [
                LinkedinService,
                provideHttpClient(),
                provideHttpClientTesting()
            ]
        });
        service = TestBed.inject(LinkedinService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should sync profile data', () => {
        const mockProfileData = { name: 'Test User', skills: ['Angular'] };

        service.syncProfile().subscribe(data => {
            expect(data).toEqual(mockProfileData);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/linkedin/profile-sync`);
        expect(req.request.method).toBe('GET');
        req.flush(mockProfileData);
    });

    it('should fetch posts', () => {
        const mockPosts: LinkedInPost[] = [
            { id: '1', content: 'Post 1', time: '1d' },
            { id: '2', content: 'Post 2', time: '2d' }
        ];

        service.getPosts().subscribe(posts => {
            expect(posts).toEqual(mockPosts);
            expect(posts.length).toBe(2);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/linkedin/posts`);
        expect(req.request.method).toBe('GET');
        req.flush(mockPosts);
    });

    it('should transfer a post', () => {
        const mockPost: LinkedInPost = { id: 'urn:li:activity:1234', content: 'Post 1', time: '1d', imageUrl: '', urn: '1234' };
        const mockResponse = { id: 123, message: 'Transfer successful' };

        service.transferPost(mockPost).subscribe(res => {
            expect(res).toEqual(mockResponse);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/linkedin/transfer-post`);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual({
            content: mockPost.content,
            image_url: null,
            urn: '1234'
        });
        req.flush(mockResponse);
    });
});
