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
  posts$: Observable<BlogPost[]> | null = null;
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
    this.loadPosts();
  }

  loadPosts() {
    // Fetch all published posts regardless of language, optional tag filter
    this.posts$ = this.blogService.getPosts(true, null, this.activeTag).pipe(
      map(response => response.items)
    );
  }

  filterByTag(tag: string) {
    this.activeTag = tag;
    this.currentQuery = ''; // Clear text search
    this.searchResults$ = null;
    this.loadPosts();
  }

  clearTagFilter() {
    this.activeTag = null;
    this.loadPosts();
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
}
