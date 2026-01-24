import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { BlogService } from './blog.service';
import { LanguageService } from './language.service';
import { of } from 'rxjs';
import { environment } from '../../environments/environment';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

describe('BlogService', () => {
    let service: BlogService;
    let httpMock: HttpTestingController;
    let languageServiceSpy: any;

    beforeEach(() => {
        languageServiceSpy = {
            currentLang$: of('en')
        };

        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [
                BlogService,
                { provide: LanguageService, useValue: languageServiceSpy }
            ]
        });
        service = TestBed.inject(BlogService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    describe('getPosts', () => {
        it('should fetch published posts with default settings', () => {
            service.getPosts(true, null).subscribe();

            const req = httpMock.expectOne(req =>
                req.url.endsWith('/api/posts') &&
                req.params.get('published_only') === 'true' &&
                !req.params.has('lang')
            );
            expect(req.request.method).toBe('GET');
            req.flush([]);
        });

        it('should fetch drafts when publishedOnly is false', () => {
            service.getPosts(false, null).subscribe();

            const req = httpMock.expectOne(req =>
                req.url.endsWith('/api/posts') &&
                req.params.get('published_only') === 'false'
            );
            req.flush([]);
        });

        it('should filter by tag when tag is provided', () => {
            service.getPosts(true, null, 'angular').subscribe();

            const req = httpMock.expectOne(req =>
                req.url.endsWith('/api/posts') &&
                req.params.get('tag') === 'angular'
            );
            req.flush([]);
        });

        it('should combine language and tag filters', () => {
            service.getPosts(true, 'de', 'tech').subscribe();

            const req = httpMock.expectOne(req =>
                req.url.endsWith('/api/posts') &&
                req.params.get('lang') === 'de' &&
                req.params.get('tag') === 'tech'
            );
            req.flush([]);
        });
    });

    describe('suggestTags', () => {
        it('should call suggest-tags endpoint via POST', () => {
            const title = 'Test Title';
            const content = 'Test Content';
            const mockResponse = { tags: ['tag1', 'tag2'] };

            service.suggestTags(title, content).subscribe(res => {
                expect(res.tags).toEqual(['tag1', 'tag2']);
            });

            // With relative path in environment, exact match might start with /api
            const req = httpMock.expectOne(req => req.url.includes('/api/posts/suggest-tags'));
            expect(req.request.method).toBe('POST');
            expect(req.request.body).toEqual({ title, content });
            req.flush(mockResponse);
        });
    });
});
