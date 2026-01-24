import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { BlogService } from '../../../services/blog.service';

interface PostData {
  title: string;
  slug: string;
  content: string;
  summary: string;
  language: string;
  published: boolean;
  tags: string[];
}

@Component({
  selector: 'app-post-editor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './post-editor.component.html',
  styleUrls: ['./post-editor.component.css']
})
export class PostEditorComponent implements OnInit {
  post: PostData = {
    title: '',
    slug: '',
    content: '',
    summary: '',
    language: 'en',
    published: false,
    tags: []
  };

  isEditMode = false;
  currentSlug: string | null = null;
  saving = false;
  generatingTags = false;
  errorMessage = '';
  newTag = '';

  constructor(
    private blogService: BlogService,
    private router: Router,
    private route: ActivatedRoute
  ) { }

  ngOnInit(): void {
    const slug = this.route.snapshot.paramMap.get('id'); // Route is defined as :id but we use slug
    if (slug && slug !== 'new') { // Ensure it's not the 'new' route erroneously matched
      this.isEditMode = true;
      this.currentSlug = slug;
      this.loadPost(slug);
    }
  }

  private loadPost(slug: string): void {
    this.blogService.getPost(slug).subscribe({
      next: (post) => {
        if (post) {
          this.post = {
            title: post.title,
            slug: post.slug,
            content: post.content,
            summary: post.summary || '',
            language: post.language,
            published: post.published,
            tags: post.tags || []
          };
        }
      },
      error: (error) => {
        console.error('Failed to load post:', error);
        this.errorMessage = 'Failed to load post';
      }
    });
  }

  onTitleChange(): void {
    if (!this.isEditMode) {
      // Auto-generate slug from title
      this.post.slug = this.post.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    }
  }

  addTag(): void {
    if (!this.newTag) return;
    const tag = this.newTag.trim();
    if (!tag) return;

    if (this.post.tags.length >= 5) {
      alert('Max 5 tags allowed');
      return;
    }

    if (!this.post.tags.includes(tag)) {
      this.post.tags.push(tag);
    }
    this.newTag = '';
  }

  removeTag(tag: string): void {
    this.post.tags = this.post.tags.filter(t => t !== tag);
  }

  suggestTags(): void {
    if (!this.post.title || !this.post.content) {
      alert('Please fill in title and content first.'); // Keep this alert for user feedback
      return;
    }

    this.generatingTags = true; // Use new flag
    this.blogService.suggestTags(this.post.title, this.post.content).subscribe({
      next: (response) => {
        this.generatingTags = false;
        if (response.tags && response.tags.length > 0) {
          // Add non-duplicate tags (max 5 total)
          const remainingSlots = 5 - this.post.tags.length;
          if (remainingSlots > 0) {
            const newTags = response.tags
              .filter(t => !this.post.tags.includes(t))
              .slice(0, remainingSlots);
            this.post.tags = [...this.post.tags, ...newTags];
          } else {
            alert('Tag limit (5) reached. No new tags added.');
          }
        } else {
          alert('No tags suggested.');
        }
      },
      error: (err) => {
        this.generatingTags = false;
        console.error('Error suggesting tags:', err);
        alert('Failed to suggest tags. Ensure AI service is available.');
      }
    });
  }

  togglePublish(): void {
    this.post.published = !this.post.published;
    this.onSubmit(); // Save immediately
  }

  onSubmit(): void {
    this.saving = true;
    this.errorMessage = '';

    const request = this.isEditMode && this.currentSlug
      ? this.blogService.updatePost(this.currentSlug, this.post)
      : this.blogService.createPost(this.post);

    request.subscribe({
      next: () => {
        this.router.navigate(['/admin/posts']);
      },
      error: (error) => {
        this.saving = false;
        // Revert published state on error if it was a toggle action
        // (Simplification: in real app manage cleaner state or separate save vs publish)
        this.errorMessage = error.error?.detail || 'Failed to save post';
        console.error('Save error:', error);
      }
    });
  }

  cancel(): void {
    this.router.navigate(['/admin/posts']);
  }
}
