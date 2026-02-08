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
      currentLang$: of('en'),
    };

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [BlogService, { provide: LanguageService, useValue: languageServiceSpy }],
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

      const req = httpMock.expectOne(
        (req) =>
          req.url.endsWith(environment.apiPrefix + '/posts') &&
          req.params.get('published_only') === 'true' &&
          !req.params.has('lang'),
      );
      expect(req.request.method).toBe('GET');
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });

    it('should fetch drafts when publishedOnly is false', () => {
      service.getPosts(false, null).subscribe();

      const req = httpMock.expectOne(
        (req) => req.url.endsWith(environment.apiPrefix + '/posts') && req.params.get('published_only') === 'false',
      );
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });

    it('should filter by tag when tag is provided', () => {
      service.getPosts(true, null, 'angular').subscribe();

      const req = httpMock.expectOne(
        (req) => req.url.endsWith(environment.apiPrefix + '/posts') && req.params.get('tag') === 'angular',
      );
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });

    it('should combine language and tag filters', () => {
      service.getPosts(true, 'de', 'tech').subscribe();

      const req = httpMock.expectOne(
        (req) =>
          req.url.endsWith(environment.apiPrefix + '/posts') &&
          req.params.get('lang') === 'de' &&
          req.params.get('tag') === 'tech',
      );
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });

    it('should fallback to current language from service when lang is undefined', () => {
      // Call without lang parameter
      service.getPosts(true).subscribe();

      const req = httpMock.expectOne(
        (req) => req.url.endsWith(environment.apiPrefix + '/posts') && req.params.get('lang') === 'en',
      );
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });

    it('should handle tag and publishedOnly correctly in fallback mode', () => {
      // Call without lang, but with tag and publishedOnly=false
      service.getPosts(false, undefined, 'tech').subscribe();

      const req = httpMock.expectOne(
        (req) =>
          req.url.endsWith(environment.apiPrefix + '/posts') &&
          req.params.get('lang') === 'en' &&
          req.params.get('tag') === 'tech' &&
          req.params.get('published_only') === 'false',
      );
      req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 1 });
    });
  });

  describe('suggestTags', () => {
    it('should call suggest-tags endpoint via POST', () => {
      const title = 'Test Title';
      const content = 'Test Content';
      const mockResponse = { tags: ['tag1', 'tag2'] };

      service.suggestTags(title, content).subscribe((res) => {
        expect(res.tags).toEqual(['tag1', 'tag2']);
      });

      // With relative path in environment, exact match might start with /api
      const req = httpMock.expectOne((req) => req.url.includes(environment.apiPrefix + '/posts/suggest-tags'));
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ title, content });
      req.flush(mockResponse);
    });
  });

  describe('suggestPostDetails', () => {
    it('should call suggest-details endpoint via POST', () => {
      const content = 'Test Content';
      const field = 'title';
      const mockResponse = { title: 'Suggested' };

      service.suggestPostDetails(content, field).subscribe((res) => {
        expect(res).toEqual(mockResponse);
      });

      const req = httpMock.expectOne((req) => req.url.includes(environment.apiPrefix + '/posts/suggest-details'));
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ content, field });
      req.flush(mockResponse);
    });
  });

  describe('CRUD Operations', () => {
    it('should get post by id', () => {
      const mockPost = { id: 1, title: 'Test' };
      service.getPostById(1).subscribe((post) => {
        expect(post).toEqual(mockPost as any);
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts/1'));
      expect(req.request.method).toBe('GET');
      req.flush(mockPost);
    });

    it('should get post by slug', () => {
      const mockPost = { slug: 'test' };
      service.getPost('test').subscribe((post) => {
        expect(post).toEqual(mockPost as any);
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts/test'));
      expect(req.request.method).toBe('GET');
      req.flush(mockPost);
    });

    it('should create post', () => {
      const mockPost = { title: 'New' };
      service.createPost(mockPost).subscribe((post) => {
        expect(post).toEqual(mockPost as any);
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts'));
      expect(req.request.method).toBe('POST');
      req.flush(mockPost);
    });

    it('should update post by id', () => {
      const mockPost = { id: 1, title: 'Updated' };
      service.updatePostById(1, mockPost).subscribe((post) => {
        expect(post).toEqual(mockPost as any);
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts/1'));
      expect(req.request.method).toBe('PUT');
      req.flush(mockPost);
    });

    it('should delete post by id', () => {
      service.deletePostById(1).subscribe((res) => {
        expect(res).toBeNull(); // Void return is often null in tests or undefined
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts/1'));
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });

  describe('Search', () => {
    it('should search posts with current language', () => {
      const query = 'AI';
      const mockResults = [{ id: 1, relevance: 0.9 }];

      service.searchPosts(query).subscribe((results) => {
        expect(results).toEqual(mockResults as any);
      });

      const req = httpMock.expectOne(
        (req) =>
          req.url.endsWith(environment.apiPrefix + '/posts/search/semantic') &&
          req.params.get('q') === query &&
          req.params.get('lang') === 'en',
      );
      expect(req.request.method).toBe('GET');
      req.flush(mockResults);
    });
  });

  describe('Error Handling', () => {
    it('should propagate 404 errors', () => {
      service.getPostById(999).subscribe({
        error: (error) => {
          expect(error.status).toBe(404);
        },
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts/999'));
      req.flush('Not Found', { status: 404, statusText: 'Not Found' });
    });

    it('should propagate 500 errors', () => {
      service.createPost({}).subscribe({
        error: (error) => {
          expect(error.status).toBe(500);
        },
      });

      const req = httpMock.expectOne((req) => req.url.endsWith(environment.apiPrefix + '/posts'));
      req.flush('Server Error', { status: 500, statusText: 'Server Error' });
    });
  });
});
