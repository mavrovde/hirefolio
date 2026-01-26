import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { BlogService, BlogPost } from '../../../services/blog.service';
import { Observable, switchMap, catchError, of } from 'rxjs';

@Component({
  selector: 'app-blog-post',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="min-h-screen bg-black font-mono text-primary p-6 md:p-12">
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
                <span class="text-terminal-highlight">date:</span> {{ post.date }}
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
            <div [innerHTML]="post.content"></div>
          </article>

          <!-- Footer -->
          <div class="mt-12 pt-8 border-t border-dashed border-terminal-dim text-center text-secondary">
            <span class="animate-pulse">_</span>
            <span class="ml-2">End of file</span>
            <div class="mt-4">
               <button 
                (click)="goBack()" 
                class="text-terminal-highlight hover:text-white hover:underline decoration-dashed transition-colors"
              >
                [ cd .. ]
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
    private blogService: BlogService
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
          catchError(() => {
            this.router.navigate(['/']);
            return of(undefined);
          })
        );
      })
    );
  }

  goBack() {
    this.router.navigate(['/'], { fragment: 'blog' });
  }
}
