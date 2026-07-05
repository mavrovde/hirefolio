import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { BlogService } from './blog.service';
import { LanguageService } from './language.service';
import { BehaviorSubject } from 'rxjs';

class MockLanguageService {
  currentLang$ = new BehaviorSubject<string>('en');
  getCurrentLanguage() {
    return 'en';
  }
}

describe('BlogService getStaticPosts slug branches (line 159)', () => {
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

  it('resolves slug from p.id, then p.slug, then generated fallback within a single page', () => {
    service.getStaticPosts(1, 10).subscribe((response) => {
      expect(response.total).toBe(3);
      expect(response.items.length).toBe(3);
      // p.id truthy -> uses id
      expect(response.items[0].slug).toBe('id-slug');
      // p.id falsy, p.slug truthy -> uses slug
      expect(response.items[1].slug).toBe('real-slug');
      // p.id and p.slug both falsy -> generated fallback using i + start
      expect(response.items[2].slug).toBe('post-2');
    });

    const req = httpMock.expectOne('/assets/blog_data_en.json');
    expect(req.request.method).toBe('GET');
    req.flush([
      { id: 'id-slug', title: 'Post 1' },
      { id: 0, slug: 'real-slug', title: 'Post 2' },
      { id: '', slug: '', title: 'Post 3' },
    ]);
  });

  it('generates fallback slug using start offset on a later page', () => {
    // page 2, pageSize 1 -> start = 1, so fallback slug should be post-1
    service.getStaticPosts(2, 1).subscribe((response) => {
      expect(response.items.length).toBe(1);
      expect(response.items[0].slug).toBe('post-1');
      expect(response.items[0].id).toBe(1);
    });

    const req = httpMock.expectOne('/assets/blog_data_en.json');
    req.flush([
      { id: 'first', title: 'Post 1' },
      { title: 'Post 2 no id or slug' },
    ]);
  });
});
