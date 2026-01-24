import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TagsService, TagStat } from '../../../services/tags.service';
import { FormsModule } from '@angular/forms';

@Component({
    selector: 'app-tag-manager',
    standalone: true,
    imports: [CommonModule, FormsModule],
    template: `
    <div class="tag-manager">
      <h1 class="page-title">&gt; Tag Manager</h1>

      @if (loading) {
        <div class="loading">Loading tags...</div>
      } @else if (error) {
        <div class="error-message">{{ error }}</div>
      } @else {
        <div class="tags-table-container">
          <table class="tags-table">
            <thead>
              <tr>
                <th>Tag Name</th>
                <th>Usage Count</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (tag of tags; track tag.name) {
                <tr>
                  <td>
                    @if (editingTag === tag.name) {
                      <div class="edit-row">
                        <input [(ngModel)]="editName" (keydown.enter)="saveRename(tag)" class="edit-input" />
                        <button (click)="saveRename(tag)" class="btn-sm btn-success">✓</button>
                        <button (click)="cancelEdit()" class="btn-sm btn-secondary">✗</button>
                      </div>
                    } @else {
                      <span class="tag-badge">{{ tag.name }}</span>
                    }
                  </td>
                  <td>{{ tag.count }}</td>
                  <td>
                    @if (editingTag !== tag.name) {
                      <button (click)="startEdit(tag)" class="btn-action">Edit</button>
                      <button (click)="deleteTag(tag)" class="btn-action btn-danger">Delete</button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    </div>
  `,
    styles: [`
    .tag-manager { padding: 20px; }
    .page-title { font-size: 2rem; margin-bottom: 2rem; color: var(--color-primary); }
    .tags-table { width: 100%; border-collapse: collapse; }
    .tags-table th, .tags-table td { padding: 12px; text-align: left; border-bottom: 1px solid var(--color-border); }
    .tag-badge { background: var(--color-bg-secondary); padding: 4px 8px; rounded: 4px; color: var(--color-secondary); }
    .btn-action { margin-right: 8px; padding: 4px 8px; cursor: pointer; background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
    .btn-danger { color: #ff6b6b; border-color: #ff6b6b; }
    .btn-action:hover { background: var(--color-bg-secondary); }
    .edit-row { display: flex; gap: 8px; align-items: center; }
    .edit-input { background: var(--color-bg-secondary); border: 1px solid var(--color-border); color: var(--color-text); padding: 4px; }
    .loading { color: var(--color-text-dim); }
    .error-message { color: #ff6b6b; }
  `]
})
export class TagManagerComponent implements OnInit {
    tags: TagStat[] = [];
    loading = true;
    error: string | null = null;
    editingTag: string | null = null;
    editName = '';

    constructor(private tagsService: TagsService) { }

    ngOnInit(): void {
        this.loadTags();
    }

    loadTags(): void {
        this.loading = true;
        this.tagsService.getAllTags().subscribe({
            next: (data) => {
                this.tags = data;
                this.loading = false;
            },
            error: (err) => {
                console.error('Failed to load tags', err);
                this.error = 'Failed to load tags.';
                this.loading = false;
            }
        });
    }

    startEdit(tag: TagStat): void {
        this.editingTag = tag.name;
        this.editName = tag.name;
    }

    cancelEdit(): void {
        this.editingTag = null;
        this.editName = '';
    }

    saveRename(tag: TagStat): void {
        if (!this.editName || this.editName === tag.name) {
            this.cancelEdit();
            return;
        }

        this.tagsService.renameTag(tag.name, this.editName).subscribe({
            next: () => {
                tag.name = this.editName; // Optimistic update
                this.loadTags(); // Reload to be safe
                this.cancelEdit();
            },
            error: (err) => {
                console.error('Rename failed', err);
                alert('Failed to rename tag.');
            }
        });
    }

    deleteTag(tag: TagStat): void {
        if (!confirm(`Are you sure you want to delete tag "${tag.name}" from ALL posts?`)) {
            return;
        }

        this.tagsService.deleteTag(tag.name).subscribe({
            next: () => {
                this.loadTags();
            },
            error: (err) => {
                console.error('Delete failed', err);
                alert('Failed to delete tag.');
            }
        });
    }
}
