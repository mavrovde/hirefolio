import { Component, OnInit, Input, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { BlogService, BlogPost, BlogSearchResult } from '../../services/blog.service';
import { Observable, map, firstValueFrom } from 'rxjs';
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

  async loadPosts() {
    if (this.isLoading) return;
    this.isLoading = true;

    const effectivePageSize = this.currentPage === 1 ? this.pageSize : this.loadMoreSize;
    // After the initial load of pageSize(10) items, subsequent loads use loadMoreSize(5).
    // To get the correct offset, compute API page in terms of loadMoreSize:
    // Initial: page=1, page_size=10 -> offset=0, limit=10
    // Load more #1: need offset=10 -> page=3 with page_size=5 (offset=(3-1)*5=10)
    // Load more #2: need offset=15 -> page=4 with page_size=5 (offset=(4-1)*5=15)
    let apiPage: number;
    let apiPageSize: number;
    if (this.currentPage === 1) {
      apiPage = 1;
      apiPageSize = this.pageSize;
    } else {
      apiPageSize = this.loadMoreSize;
      // posts.length gives us the actual offset we need
      apiPage = Math.floor(this.posts.length / apiPageSize) + 1;
    }

    if (this.usingFallback) {
      this.loadFallbackPosts(effectivePageSize);
      return;
    }

    try {
      const response = await firstValueFrom(
        this.blogService.getPosts(true, null, this.activeTag, apiPage, apiPageSize)
      );
      // Deduplicate by id to handle any edge cases
      const existingIds = new Set(this.posts.map(p => p.id));
      const newPosts = response.items.filter(p => !existingIds.has(p.id));
      this.posts = [...this.posts, ...newPosts];
      this.hasMore = this.posts.length < response.total;
      this.isLoading = false;
    } catch (err) {
      console.error('Failed to load posts from API, using fallback', err);
      this.usingFallback = true;
      this.loadFallbackPosts(effectivePageSize);
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
