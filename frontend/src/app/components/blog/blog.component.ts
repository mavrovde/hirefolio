import { Component, OnInit, Input, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { BlogService, BlogPost, BlogSearchResult } from '../../services/blog.service';
import { Observable, map } from 'rxjs';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { RouterModule } from '@angular/router';
import { SeoService } from '../../services/seo.service';

import { HeaderComponent } from '../header/header.component';

@Component({
  selector: 'app-blog',
  standalone: true,
  imports: [CommonModule, TranslatePipe, RouterModule, HeaderComponent],
  templateUrl: './blog.component.html',
  styleUrls: ['./blog.component.css'],
})
export class BlogComponent implements OnInit {
  @Input() standalone = true;
  // Pagination State
  posts: BlogPost[] = [];
  currentPage = 1;
  pageSize = 10;
  loadMoreSize = 5;
  hasMore = false;
  isLoading = false;
  private usingFallback = false;

  // Search State
  searchResults$: Observable<BlogSearchResult[]> | null = null;
  expandedPostId: string | null = null;
  isSearching = false;
  currentQuery = '';
  activeTag: string | null = null;

  constructor(
    private blogService: BlogService,
    private seoService: SeoService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) { }

  ngOnInit() {
    if (this.standalone) {
      this.seoService.updateSeo({
        title: 'Blog',
        description: 'Read the latest insights and professional reflections from Sergii Mavrov, covering Cloud Architecture, AI, and Software Engineering.',
        url: '/blog',
        keywords: 'Blog, Technology, Software Engineering, AI, Cloud, Sergii Mavrov'
      });
    }
    this.loadInitialPosts();
  }

  loadInitialPosts() {
    this.posts = [];
    this.currentPage = 1;
    this.hasMore = false;
    this.loadPosts();
  }

  loadPosts() {
    if (this.isLoading) return;
    this.isLoading = true;

    const effectivePageSize = this.currentPage === 1 ? this.pageSize : this.loadMoreSize;
    let apiPage: number;
    let apiPageSize: number;
    if (this.currentPage === 1) {
      apiPage = 1;
      apiPageSize = this.pageSize;
    } else {
      apiPageSize = this.loadMoreSize;
      apiPage = Math.floor(this.posts.length / apiPageSize) + 1;
    }

    if (this.usingFallback) {
      this.loadFallbackPosts(effectivePageSize);
      return;
    }

    // For load-more on the browser, use native fetch to bypass Angular HttpClient SSR issues
    if (this.currentPage > 1 && isPlatformBrowser(this.platformId)) {
      this.loadMoreWithFetch(apiPage, apiPageSize);
      return;
    }

    this.blogService.getPosts(true, null, this.activeTag, apiPage, apiPageSize).subscribe({
      next: (response) => {
        const existingIds = new Set(this.posts.map(p => p.id));
        const newPosts = response.items.filter(p => !existingIds.has(p.id));
        this.posts = [...this.posts, ...newPosts];
        this.hasMore = this.posts.length < response.total;
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Failed to load posts from API, using fallback', err);
        this.usingFallback = true;
        this.loadFallbackPosts(effectivePageSize);
      }
    });
  }

  private async loadMoreWithFetch(apiPage: number, apiPageSize: number) {
    try {
      const params = new URLSearchParams({
        page: apiPage.toString(),
        page_size: apiPageSize.toString(),
        sort_by: 'created_at',
        sort_order: 'desc',
        published_only: 'true',
      });
      if (this.activeTag) {
        params.set('tag', this.activeTag);
      }
      const resp = await fetch(`/api/app/posts?${params.toString()}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const response = await resp.json();
      const existingIds = new Set(this.posts.map((p: BlogPost) => p.id));
      const newPosts = (response.items || []).filter((p: BlogPost) => !existingIds.has(p.id));
      this.posts = [...this.posts, ...newPosts];
      this.hasMore = this.posts.length < response.total;
      this.isLoading = false;
    } catch (err) {
      console.error('Failed to load more posts via fetch, using fallback', err);
      this.usingFallback = true;
      this.loadFallbackPosts(this.loadMoreSize);
    }
  }

  private loadFallbackPosts(effectivePageSize: number) {
    this.blogService.getStaticPosts(this.currentPage, effectivePageSize).subscribe({
      next: (response) => {
        this.posts = [...this.posts, ...response.items];
        this.hasMore = this.posts.length < response.total;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  loadMore() {
    if (!this.hasMore || this.isLoading) return;
    this.currentPage++;
    this.loadPosts();
  }

  filterByTag(tag: string) {
    this.activeTag = tag;
    this.currentQuery = ''; // Clear text search
    this.searchResults$ = null;
    this.loadInitialPosts();
  }

  clearTagFilter() {
    this.activeTag = null;
    this.loadInitialPosts();
  }

  onSearch(event: any) {
    const query = event.target.value;
    // Use standard timeout for debouncing (simple implementation)
    setTimeout(() => {
      this.currentQuery = query;
      if (!query || query.trim().length < 3) {
        this.searchResults$ = null;
        this.isSearching = false;
        return;
      }

      this.isSearching = true;
      this.searchResults$ = this.blogService.searchPosts(query).pipe(
        map((results) => {
          this.isSearching = false;
          return results;
        }),
      );
    });
  }

  clearSearch(input: HTMLInputElement) {
    setTimeout(() => {
      input.value = '';
      this.currentQuery = '';
      this.searchResults$ = null;
      this.isSearching = false;
    });
  }

  togglePost(id: number | string) {
    const idStr = String(id);
    if (this.expandedPostId === idStr) {
      this.expandedPostId = null;
    } else {
      this.expandedPostId = idStr;
    }
  }

  isExpanded(id: number | string): boolean {
    return this.expandedPostId === String(id);
  }

  trackByPostId(index: number, post: BlogPost): number {
    return post.id;
  }
}
