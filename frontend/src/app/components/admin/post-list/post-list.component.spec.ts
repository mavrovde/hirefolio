import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PostListComponent } from './post-list.component';
import { BlogService, BlogPost } from '../../../services/blog.service';
import { of, throwError } from 'rxjs';
import { RouterTestingModule } from '@angular/router/testing';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('PostListComponent', () => {
    let component: PostListComponent;
    let fixture: ComponentFixture<PostListComponent>;
    let blogServiceSpy: { getPosts: Mock; deletePostById: Mock };

    const mockPosts: BlogPost[] = [
        {
            id: 1,
            title: 'Test Post 1',
            slug: 'test-post-1',
            date: '2024-01-01',
            summary: 'Summary 1',
            content: 'Content 1',
            language: 'en',
            published: true,
            created_at: '2024-01-01T10:00:00Z',
            tags: ['tag1']
        },
        {
            id: 2,
            title: 'Test Post 2',
            slug: 'test-post-2',
            date: '2024-01-02',
            summary: 'Summary 2',
            content: 'Content 2',
            language: 'de',
            published: false,
            created_at: '2024-01-02T10:00:00Z',
            tags: []
        }
    ];

    beforeEach(async () => {
        blogServiceSpy = {
            getPosts: vi.fn(),
            deletePostById: vi.fn()
        };

        await TestBed.configureTestingModule({
            imports: [PostListComponent, RouterTestingModule],
            providers: [
                { provide: BlogService, useValue: blogServiceSpy }
            ]
        })
            .compileComponents();

        fixture = TestBed.createComponent(PostListComponent);
        component = fixture.componentInstance;
    });

    it('should create', () => {
        blogServiceSpy.getPosts.mockReturnValue(of([]));
        fixture.detectChanges();
        expect(component).toBeTruthy();
    });

    it('should load posts on init', () => {
        blogServiceSpy.getPosts.mockReturnValue(of(mockPosts));
        fixture.detectChanges();

        expect(component.posts).toEqual(mockPosts);
        expect(component.loading).toBe(false);
        expect(component.error).toBeNull();
    });

    it('should handle error when loading posts', () => {
        blogServiceSpy.getPosts.mockReturnValue(throwError(() => new Error('Network error')));
        fixture.detectChanges();

        expect(component.posts).toEqual([]);
        expect(component.loading).toBe(false);
        expect(component.error).toContain('Failed to load posts');
    });

    it('should delete post after confirmation', () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        blogServiceSpy.getPosts.mockReturnValue(of(mockPosts));
        blogServiceSpy.deletePostById.mockReturnValue(of(void 0));

        fixture.detectChanges();

        component.deletePost(mockPosts[0]);

        expect(blogServiceSpy.deletePostById).toHaveBeenCalledWith(mockPosts[0].id);
        expect(component.posts.length).toBe(1);
        expect(component.posts.find(p => p.id === mockPosts[0].id)).toBeUndefined();
    });

    it('should not delete post if confirmation cancelled', () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        blogServiceSpy.getPosts.mockReturnValue(of(mockPosts));

        fixture.detectChanges();

        component.deletePost(mockPosts[0]);

        expect(blogServiceSpy.deletePostById).not.toHaveBeenCalled();
        expect(component.posts.length).toBe(2);
    });

    it('should handle error when deleting post', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => { });
        vi.spyOn(window, 'confirm').mockReturnValue(true);

        blogServiceSpy.getPosts.mockReturnValue(of(mockPosts));
        blogServiceSpy.deletePostById.mockReturnValue(throwError(() => new Error('Delete failed')));

        fixture.detectChanges();

        component.deletePost(mockPosts[0]);

        expect(consoleSpy).toHaveBeenCalledWith('Failed to delete post:', expect.any(Error));
        expect(alertSpy).toHaveBeenCalledWith('Failed to delete post. Please try again.');
        expect(component.posts.length).toBe(2); // Post should remain

        consoleSpy.mockRestore();
    });
});
