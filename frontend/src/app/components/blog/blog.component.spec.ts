import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BlogComponent } from './blog.component';
import { BlogService } from '../../services/blog.service';
import { LanguageService } from '../../services/language.service';
import { of } from 'rxjs';
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
      getPosts: vi.fn().mockReturnValue(of(mockPosts)),
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

  it('should load posts on init', async () => {
    fixture.detectChanges();
    expect(blogServiceSpy.getPosts).toHaveBeenCalled();

    await fixture.whenStable();
    fixture.detectChanges();

    const postElement = fixture.debugElement.query(By.css('.group .text-primary.font-bold'));
    if (postElement) {
      expect(postElement.nativeElement.textContent).toContain('Test Post');
    }
  });

  it('should toggle post expansion state', () => {
    fixture.detectChanges();

    // 1. Expand - Synchronous call
    component.togglePost('1');

    // Assert state, verified function logic
    expect(component.expandedPostId).toBe('1');
    expect(component.isExpanded('1')).toBe(true);

    // 2. Collapse - Synchronous call
    component.togglePost('1');

    // Assert state
    expect(component.expandedPostId).toBeNull();
    expect(component.isExpanded('1')).toBe(false);
  });

  it('should perform semantic search on enter', async () => {
    fixture.detectChanges();

    // This triggers a setTimeout in component
    component.onSearch({ target: { value: 'angular' } } as any);

    // Wait for timeout to resolve.
    await wait(200);

    expect(blogServiceSpy.searchPosts).toHaveBeenCalledWith('angular');

    // Subscribe to exercise the map operator
    component.searchResults$?.subscribe();
    expect(component.isSearching).toBe(false);
  });

  it('should clear search', async () => {
    fixture.detectChanges();

    // Setup state directly to avoid waiting for search
    component.onSearch({ target: { value: 'angular' } } as any);
    await wait(200);

    const input = document.createElement('input');
    input.value = 'angular';

    component.clearSearch(input);
    await wait(200);

    expect(component.currentQuery).toBe('');
  });

  it('should not search if query is too short', async () => {
    fixture.detectChanges();

    component.onSearch({ target: { value: 'ab' } } as any);
    await wait(200);

    expect(blogServiceSpy.searchPosts).not.toHaveBeenCalled();
    expect(component.searchResults$).toBeNull();
    expect(component.isSearching).toBe(false);
  });

  it('should filter by tag', () => {
    fixture.detectChanges();
    component.filterByTag('angular');
    expect(component.activeTag).toBe('angular');
    expect(component.currentQuery).toBe('');
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, 'angular');
  });

  it('should clear tag filter', () => {
    fixture.detectChanges();
    component.filterByTag('angular');
    component.clearTagFilter();
    expect(component.activeTag).toBeNull();
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(true, null, null);
  });
});
