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

  it('should load initial posts', () => {
    // Initial load happens in ngOnInit
    fixture.detectChanges();
    expect(component.posts.length).toBe(1);
    expect(component.posts[0].title).toBe('Test Post');
    expect(component.currentPage).toBe(1);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 1, 10);
  });

  it('should append posts on loadMore', () => {
    fixture.detectChanges(); // Initial load (page 1)

    // Mock next page response
    const nextPosts = [{ ...mockPosts[0], id: '2', title: 'Next Post' }];
    blogServiceSpy.getPosts.mockReturnValueOnce(of({
      items: nextPosts,
      total: 20,
      page: 2,
      page_size: 10,
      total_pages: 2
    }));

    // Trigger load more
    component.hasMore = true; // Ensure it's clickable
    component.loadMore();

    expect(component.currentPage).toBe(2);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 2, 10);
    expect(component.posts.length).toBe(2);
    expect(component.posts[1].title).toBe('Next Post');
  });

  it('should handle end of list', () => {
    fixture.detectChanges();

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

    expect(component.hasMore).toBe(false);
  });

  it('should not load more if isLoading or no more posts', () => {
    fixture.detectChanges();

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

  it('should handle load error', () => {
    fixture.detectChanges();

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
    blogServiceSpy.getPosts.mockReturnValueOnce(new Observable(observer => {
      observer.error('Network error');
    }));

    component.hasMore = true;
    component.loadMore();

    expect(component.isLoading).toBe(false);
    expect(errorSpy).toHaveBeenCalled();
  });

  it('should filter by tag and reset pagination', () => {
    fixture.detectChanges();

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

    expect(component.activeTag).toBe('angular');
    expect(component.currentPage).toBe(1);
    expect(component.posts).toEqual([]);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, 'angular', 1, 10);
  });

  it('should clear tag filter and reset pagination', () => {
    component.activeTag = 'angular';
    fixture.detectChanges();
    blogServiceSpy.getPosts.mockClear();

    component.clearTagFilter();

    expect(component.activeTag).toBeNull();
    expect(component.currentPage).toBe(1);
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null, 1, 10);
  });
});
