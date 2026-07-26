import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BlogComponent } from './blog.component';
import { BlogService } from '@mavrov/shared';
import { LanguageService } from '@mavrov/shared';
import { of, throwError } from 'rxjs';
import { MockTranslatePipe } from '@mavrov/shared/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

describe('BlogComponent (cov2 branch coverage)', () => {
  let component: BlogComponent;
  let blogServiceSpy: any;
  let languageServiceMock: any;
  let fetchSpy: any;

  const mockPosts = [
    {
      id: '1',
      title: 'Test Post',
      slug: 'test-post',
      date: '2026-01-24',
      summary: 'Summary',
      content: '<p>Content</p>',
      language: 'en',
    },
  ];

  const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0));

  const mockFetchResponse = (data: any) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(data),
    } as Response);

  beforeEach(async () => {
    blogServiceSpy = {
      getPosts: vi.fn().mockReturnValue(
        of({ items: mockPosts, total: mockPosts.length, page: 1, page_size: 10, total_pages: 1 })
      ),
      searchPosts: vi.fn().mockReturnValue(of([])),
      getStaticPosts: vi.fn().mockReturnValue(
        of({ items: mockPosts, total: mockPosts.length, page: 1, page_size: 10, total_pages: 1 })
      ),
    };

    languageServiceMock = {
      currentLang$: of('en'),
      translations$: of({}),
      translate: (key: string) => of(key),
      getCurrentLanguage: () => 'en',
    };

    fetchSpy = vi.spyOn(globalThis, 'fetch');
    fetchSpy.mockReturnValue(
      mockFetchResponse({ items: mockPosts, total: 1, page: 1, page_size: 10, total_pages: 1 })
    );

    await TestBed.configureTestingModule({
      imports: [BlogComponent, MockTranslatePipe],
      providers: [
        { provide: BlogService, useValue: blogServiceSpy },
        { provide: LanguageService, useValue: languageServiceMock },
        provideRouter([]),
      ],
    }).compileComponents();

    component = TestBed.createComponent(BlogComponent).componentInstance;
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  // Line 46 false branch: standalone=false skips SEO update
  it('should skip SEO update when not standalone', () => {
    const seoSpy = { updateSeo: vi.fn() };
    const c = new BlogComponent(
      blogServiceSpy, seoSpy as any, {} as any, {} as any, {} as any, 'server'
    );
    c.standalone = false;
    c.ngOnInit();
    expect(seoSpy.updateSeo).not.toHaveBeenCalled();
    expect(blogServiceSpy.getPosts).toHaveBeenCalled();
  });

  // Lines 65: early return when already loading
  it('should return early from loadPosts when isLoading is true', () => {
    component.isLoading = true;
    component.loadPosts();
    // Neither fetch nor service should be triggered because of early return
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(blogServiceSpy.getPosts).not.toHaveBeenCalled();
    expect(blogServiceSpy.getStaticPosts).not.toHaveBeenCalled();
  });

  // Lines 79-81: usingFallback branch routes directly to loadFallbackPosts
  it('should route to fallback posts directly when usingFallback is already true', () => {
    (component as any).usingFallback = true;
    component.loadPosts();

    expect(blogServiceSpy.getStaticPosts).toHaveBeenCalledWith(1, 10);
    // Browser fetch path must NOT be taken
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(component.posts.length).toBe(1);
    expect(component.isLoading).toBe(false);
  });

  // Lines 79-81 with load-more page size (effectivePageSize = loadMoreSize)
  it('should use loadMoreSize for fallback on load-more when usingFallback is true', () => {
    (component as any).usingFallback = true;
    component.currentPage = 2;
    component.posts = [...mockPosts] as any;
    component.loadPosts();

    expect(blogServiceSpy.getStaticPosts).toHaveBeenCalledWith(2, 5);
  });

  // Line 149-150: error branch in loadFallbackPosts sets isLoading false
  it('should set isLoading false when fallback getStaticPosts errors', () => {
    (component as any).usingFallback = true;
    blogServiceSpy.getStaticPosts.mockReturnValueOnce(throwError(() => new Error('static fail')));
    component.isLoading = false;
    component.loadPosts();
    expect(component.isLoading).toBe(false);
    expect(blogServiceSpy.getStaticPosts).toHaveBeenCalled();
  });

  // Line 92-95 branch: dedupe existing ids in SSR getPosts path (non-browser)
  it('should dedupe posts by id in SSR getPosts path', () => {
    const serverComponent = new BlogComponent(
      blogServiceSpy, {} as any, {} as any, {} as any, {} as any, 'server'
    );
    serverComponent.posts = [{ ...mockPosts[0] }] as any;
    blogServiceSpy.getPosts.mockReturnValueOnce(
      of({ items: mockPosts, total: 1, page: 1, page_size: 10, total_pages: 1 })
    );
    serverComponent.loadPosts();
    // Existing id '1' is filtered out; no duplicates added
    expect(serverComponent.posts.length).toBe(1);
    expect(serverComponent.hasMore).toBe(false);
  });

  // Line 118 branch + 127 branch: browser fetch path with missing items -> [] fallback
  it('should handle fetch response with no items array (|| [] branch)', async () => {
    fetchSpy.mockReset();
    fetchSpy.mockReturnValue(
      mockFetchResponse({ total: 0 }) // no items key
    );
    component.loadPosts();
    await flushPromises();
    await flushPromises();
    expect(component.posts).toEqual([]);
    expect(component.isLoading).toBe(false);
  });

  // Line 118: activeTag appended to fetch params in browser path
  it('should include tag in fetch url when activeTag is set', async () => {
    component.activeTag = 'angular';
    fetchSpy.mockReturnValueOnce(
      mockFetchResponse({ items: [], total: 0 })
    );
    component.loadPosts();
    await flushPromises();
    // Angular 22's HttpClient defaults to the Fetch backend, so unrelated HttpClient
    // requests (e.g. YearsService's /api/app/cv/years from the rendered header) also hit
    // this fetch spy. Target the posts request explicitly rather than assuming it is last.
    const postsCall = fetchSpy.mock.calls.find(
      (call: any[]) => typeof call[0] === 'string' && call[0].includes('/api/app/posts')
    );
    expect(postsCall).toBeTruthy();
    expect(postsCall[0] as string).toContain('tag=angular');
  });

  // Line 229 + 234: sharePost non-browser branch uses https://mavrov.de and skips both browser branches
  it('should build https://mavrov.de url and skip browser actions on SSR sharePost', async () => {
    const serverComponent = new BlogComponent(
      blogServiceSpy, {} as any, {} as any, {} as any, {} as any, 'server'
    );
    const post = { ...mockPosts[0], slug: 'test-post', title: 'Test Post' } as any;
    // Should not throw even though navigator is not used on SSR
    await expect(serverComponent.sharePost(post)).resolves.toBeUndefined();
  });

  // Line 233 catch branch: navigator.share rejects -> swallowed
  it('should swallow errors thrown by navigator.share', async () => {
    const shareSpy = vi.fn().mockRejectedValue(new Error('share cancelled'));
    Object.defineProperty(navigator, 'share', {
      value: shareSpy,
      writable: true,
      configurable: true,
    });
    const post = { ...mockPosts[0], slug: 'test-post', title: 'Test Post' } as any;
    await expect(component.sharePost(post)).resolves.toBeUndefined();
    expect(shareSpy).toHaveBeenCalled();
  });
});
