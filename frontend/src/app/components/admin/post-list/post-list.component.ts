import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { BlogService, BlogPost } from '../../../services/blog.service';

@Component({
  selector: 'app-post-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './post-list.component.html',
  styleUrls: ['./post-list.component.css']
})
export class PostListComponent implements OnInit {
  posts: BlogPost[] = [];
  loading = true;
  error: string | null = null;

  constructor(
    private blogService: BlogService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit(): void {
    this.loadPosts();
  }

  loadPosts(): void {
    this.loading = true;
    this.error = null;
    this.blogService.getPosts(false, null)
      .subscribe({
        next: (posts) => {
          this.posts = posts;
          this.loading = false;
          this.cdr.detectChanges();
        },
        error: (error) => {
          console.error('Failed to load posts:', error);
          this.error = 'Failed to load posts. Please try again later.';
          this.loading = false;
          this.cdr.detectChanges();
        }
      });
  }

  formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  deletePost(post: BlogPost): void {
    if (!confirm(`Are you sure you want to delete "${post.title}"?`)) {
      return;
    }

    this.blogService.deletePost(post.slug)
      .subscribe({
        next: () => {
          this.posts = this.posts.filter(p => p.id !== post.id);
        },
        error: (error) => {
          console.error('Failed to delete post:', error);
          alert('Failed to delete post. Please try again.');
        }
      });
  }
}
