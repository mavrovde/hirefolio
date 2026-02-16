import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BlogComponent } from './blog.component';
import { BlogService } from '../../services/blog.service';
import { LanguageService } from '../../services/language.service';
import { of, Observable } from 'rxjs';
import { By } from '@angular/platform-browser';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('BlogComponent', () => {
  let component: BlogComponent;
  let fixture: ComponentFixture<BlogComponent>;
  let blogServiceSpy: any;
  let languageServiceMock: any;

  const mockPosts = [
    {
      id: '1',
      title: 'Test Post',
      date: '2026-01-24',
      summary: 'Summary',
      content: '<p>Content</p>',
      language: 'en',
    },
  ];

  const mockSearchResults = [
    {
      id: 1,
      title: 'Search Result',
      slug: 'search-result',
      summary: 'Search Summary',
      relevance: 0.95,
    },
  ];

  // Helper to wait for timeouts
  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  beforeEach(async () => {
    blogServiceSpy = {
      getPosts: vi.fn().mockReturnValue(of({
        items: mockPosts,
        total: mockPosts.length,
        page: 1,
        page_size: 10,
        total_pages: 1
      })),
      searchPosts: vi.fn().mockReturnValue(of(mockSearchResults)),
      getStaticPosts: vi.fn().mockReturnValue(of({
        items: mockPosts,
        total: mockPosts.length,
        page: 1,
        page_size: 10,
        total_pages: 1
      })),
    };

    languageServiceMock = {
      currentLang$: of('en'),
      translations$: of({}),
      translate: (key: string) => of(key),
      getCurrentLanguage: () => 'en',
    };

    await TestBed.configureTestingModule({
      imports: [BlogComponent, MockTranslatePipe, NoopAnimationsModule],
      providers: [
        { provide: BlogService, useValue: blogServiceSpy },
        { provide: LanguageService, useValue: languageServiceMock },
        provideRouter([])
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(BlogComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load initial posts', async () => {
    // Initial load happens in ngOnInit
    fixture.detectChanges();
    await fixture.whenStable();
    expect(component.posts.length).toBe(1);
    expect(component.posts[0].title).toBe('Test Post');
    expect(component.currentPage).toBe(1);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 1, 10);
  });

  it('should append posts on loadMore with loadMoreSize=5', async () => {
    fixture.detectChanges(); // Initial load (page 1)
    await fixture.whenStable();

    // Mock next page response
    const nextPosts = [{ ...mockPosts[0], id: '2', title: 'Next Post' }];
    blogServiceSpy.getPosts.mockReturnValueOnce(of({
      items: nextPosts,
      total: 20,
      page: 1,
      page_size: 5,
      total_pages: 4
    }));

    // Trigger load more
    component.hasMore = true; // Ensure it's clickable
    component.loadMore();
    await fixture.whenStable();

    expect(component.currentPage).toBe(2);
    // After initial load of 1 post, apiPage = floor(1/5)+1 = 1, apiPageSize = 5
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 1, 5);
    expect(component.posts.length).toBe(2);
    expect(component.posts[1].title).toBe('Next Post');
  });

  it('should fall back to static posts on API error', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
    blogServiceSpy.getPosts.mockReturnValue(new Observable(observer => {
      observer.error('Network error');
    }));

    const staticPosts = [{ ...mockPosts[0], id: '99', title: 'Static Post' }];
    blogServiceSpy.getStaticPosts.mockReturnValue(of({
      items: staticPosts,
      total: 5,
      page: 1,
      page_size: 10,
      total_pages: 1
    }));

    fixture.detectChanges(); // triggers ngOnInit -> loadInitialPosts -> loadPosts
    await fixture.whenStable();

    expect(blogServiceSpy.getStaticPosts).toHaveBeenCalledWith(1, 10);
    expect(component.posts.length).toBe(1);
    expect(component.posts[0].title).toBe('Static Post');
    expect(component.isLoading).toBe(false);
    errorSpy.mockRestore();
  });

  it('should handle end of list', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    // Mock last page response
    // Initial load added 1 item.
    // Total is 1. If we return 0 items, total length remains 1. 1 < 1 is false.
    blogServiceSpy.getPosts.mockReturnValueOnce(of({
      items: [],
      total: 1, // Total matches existing count
      page: 2,
      page_size: 10,
      total_pages: 1
    }));

    component.hasMore = true;
    component.loadMore();
    await fixture.whenStable();

    expect(component.hasMore).toBe(false);
  });

  it('should not load more if isLoading or no more posts', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    // Case 1: isLoading
    component.isLoading = true;
    component.loadMore();
    expect(blogServiceSpy.getPosts).toHaveBeenCalledTimes(1); // Only initial load

    // Case 2: !hasMore
    component.isLoading = false;
    component.hasMore = false;
    component.loadMore();
    expect(blogServiceSpy.getPosts).toHaveBeenCalledTimes(1);
  });

  it('should handle load error', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
    blogServiceSpy.getPosts.mockReturnValueOnce(new Observable(observer => {
      observer.error('Network error');
    }));

    component.hasMore = true;
    component.loadMore();
    await fixture.whenStable();

    expect(component.isLoading).toBe(false);
    expect(errorSpy).toHaveBeenCalled();
  });

  it('should filter by tag and reset pagination', async () => {
    fixture.detectChanges();
    await fixture.whenStable();

    // Clear calls from init
    blogServiceSpy.getPosts.mockClear();

    // Mock response for filter
    blogServiceSpy.getPosts.mockReturnValueOnce(of({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0
    }));

    component.filterByTag('angular');
    await fixture.whenStable();

    expect(component.activeTag).toBe('angular');
    expect(component.currentPage).toBe(1);
    expect(component.posts).toEqual([]);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, 'angular', 1, 10);
  });

  it('should clear tag filter and reset pagination', async () => {
    component.activeTag = 'angular';
    fixture.detectChanges();
    await fixture.whenStable();
    blogServiceSpy.getPosts.mockClear();

    component.clearTagFilter();
    await fixture.whenStable();

    expect(component.activeTag).toBeNull();
    expect(component.currentPage).toBe(1);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 1, 10);
  });
});
