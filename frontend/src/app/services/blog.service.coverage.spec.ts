import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { BlogService } from './blog.service';
import { LanguageService } from './language.service';
import { BehaviorSubject } from 'rxjs';
import { environment } from '../../environments/environment';

class MockLanguageService {
  currentLang$ = new BehaviorSubject<string>('en');
}

describe('BlogService search param branches', () => {
  let service: BlogService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        BlogService,
        { provide: LanguageService, useClass: MockLanguageService },
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(BlogService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('includes search param in explicit-lang path (line 73)', () => {
    service
      .getPosts(true, 'en', 'ng', 2, 5, 'title', 'asc', 'keyword')
      .subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}${environment.apiPrefix}/posts`);
    expect(req.request.params.get('search')).toBe('keyword');
    expect(req.request.params.get('tag')).toBe('ng');
    expect(req.request.params.get('published_only')).toBe('true');
    req.flush({ items: [], total: 0, page: 2, page_size: 5, total_pages: 0 });
  });

  it('includes search param in fallback current-language path (line 97)', () => {
    // lang undefined -> uses languageService.currentLang$
    service
      .getPosts(false, undefined, 'ng', 1, 10, 'created_at', 'desc', 'kw')
      .subscribe();
    const req = httpMock.expectOne((r) => r.url === `${environment.apiUrl}${environment.apiPrefix}/posts`);
    expect(req.request.params.get('search')).toBe('kw');
    expect(req.request.params.get('lang')).toBe('en');
    expect(req.request.params.get('published_only')).toBe('false');
    req.flush({ items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  });
});
