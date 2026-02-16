import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { BlogService, BlogPost } from '../../../services/blog.service';
import { Observable, switchMap, catchError, of, tap } from 'rxjs';
import { HeaderComponent } from '../../header/header.component';
import { SeoService } from '../../../services/seo.service';

@Component({
  selector: 'app-blog-post',
  standalone: true,
  imports: [CommonModule, RouterModule, HeaderComponent],
  template: `
    <div class="min-h-screen bg-black font-mono text-primary">
      <app-header></app-header>
      <div class="p-6 md:p-12">
        <div class="max-w-4xl mx-auto">
          <!-- Header / Navigation -->
          <div class="mb-8 flex items-center gap-4 text-sm md:text-base border-b border-dashed border-terminal-dim pb-4">
            <button 
              (click)="goBack()" 
              class="text-secondary hover:text-white transition-colors flex items-center gap-2 group"
            >
              <span class="text-terminal-highlight group-hover:-translate-x-1 transition-transform">&lt;</span>
              [ cd .. ]
            </button>
            <span class="text-terminal-dim">|</span>
            <span class="text-secondary">~/blog/{{ (post$ | async)?.slug }}</span>
          </div>

          <ng-container *ngIf="post$ | async as post; else loading">
            <!-- Post Metadata -->
            <div class="mb-8 space-y-2">
              <h1 class="text-2xl md:text-4xl font-bold text-primary mb-4">{{ post.title }}</h1>
              
              <div class="flex flex-wrap items-center gap-4 text-sm text-secondary">
                <span class="flex items-center gap-2">
                  <span class="text-terminal-highlight">author:</span> sergii
                </span>
                <span class="flex items-center gap-2">
                  <span class="text-terminal-highlight">date:</span> {{ post.created_at | date }}
                </span>
                <span class="flex items-center gap-2">
                   <span class="text-terminal-highlight">lang:</span> {{ post.language }}
                </span>
              </div>

              <!-- Tags -->
              <div class="flex flex-wrap gap-2 mt-4">
                <span *ngFor="let tag of post.tags" class="text-xs border border-terminal-dim text-secondary px-2 py-1 rounded">
                  #{{ tag }}
                </span>
              </div>
            </div>

            <!-- Content -->
            <article class="prose prose-invert prose-p:text-primary prose-a:text-terminal-highlight prose-headings:text-primary prose-pre:bg-terminal-dim/20 prose-pre:border prose-pre:border-terminal-dim max-w-none">
              <div *ngIf="post.image_url" class="mb-8">
                <img [src]="post.image_url" [alt]="post.title" class="w-full h-auto rounded border border-terminal-dim shadow-lg object-cover max-h-[500px]">
              </div>
              <div [innerHTML]="post.content" class="whitespace-pre-wrap"></div>
            </article>

            <!-- Footer -->
            <div class="mt-12 pt-8 border-t border-dashed border-terminal-dim text-center text-secondary">
              <span class="animate-pulse">_</span>
              <span class="ml-2">End of file</span>
              <div class="mt-4 flex flex-wrap justify-center gap-4">
                 <button 
                  (click)="goBack()" 
                  class="text-terminal-highlight hover:text-white hover:underline decoration-dashed transition-colors"
                >
                  [ cd .. ]
                </button>
                <button 
                  (click)="sharePost()" 
                  class="text-secondary hover:text-terminal-highlight hover:underline decoration-dashed transition-colors"
                >
                  $ cp post.url /clipboard →
                </button>
              </div>
            </div>
          </ng-container>

          <ng-template #loading>
            <div class="text-secondary animate-pulse">
              $ loading resource...
            </div>
          </ng-template>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
    }
  `]
})
export class BlogPostComponent implements OnInit {
  post$: Observable<BlogPost | undefined> | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private blogService: BlogService,
    private seoService: SeoService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) { }

  ngOnInit() {
    this.post$ = this.route.paramMap.pipe(
      switchMap(params => {
        const slug = params.get('slug');
        if (!slug) {
          this.router.navigate(['/']);
          return of(undefined);
        }
        return this.blogService.getPost(slug).pipe(
          tap((post) => {
            if (post) {
              this.seoService.updateSeo({
                title: post.title,
                description: post.summary || post.content.substring(0, 160),
                url: `/blog/${post.slug}`,
                type: 'article',
                keywords: post.tags?.join(', ')
              });

              this.seoService.setJsonLd({
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": post.title,
                "datePublished": post.created_at,
                "author": {
                  "@type": "Person",
                  "name": "Sergii Mavrov",
                  "url": "https://mavrov.de"
                },
                "description": post.summary || post.content.substring(0, 160),
                "mainEntityOfPage": {
                  "@type": "WebPage",
                  "@id": `https://mavrov.de/blog/${post.slug}`
                },
                "keywords": post.tags?.join(', ')
              });
            }
          }),
          catchError(() => {
            this.router.navigate(['/']);
            return of(undefined);
          })
        );
      })
    );
  }



  goBack() {
    this.router.navigate(['/blog']);
  }

  async sharePost() {
    const slug = this.route.snapshot.paramMap.get('slug');
    const url = `${isPlatformBrowser(this.platformId) ? window.location.origin : 'https://mavrov.de'}/blog/${slug}`;
    if (isPlatformBrowser(this.platformId) && navigator.share) {
      try {
        await navigator.share({ title: document.title, url });
      } catch { }
    } else if (isPlatformBrowser(this.platformId)) {
      await navigator.clipboard.writeText(url);
    }
  }
}
