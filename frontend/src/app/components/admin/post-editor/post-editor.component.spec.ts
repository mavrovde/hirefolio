import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PostEditorComponent } from './post-editor.component';
import { BlogService } from '../../../services/blog.service';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { of } from 'rxjs';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('PostEditorComponent', () => {
    let component: PostEditorComponent;
    let fixture: ComponentFixture<PostEditorComponent>;
    let blogServiceSpy: { getPostById: Mock; createPost: Mock; updatePostById: Mock; deletePostById: Mock; suggestTags: Mock };
    let routerSpy: { navigate: Mock };

    beforeEach(async () => {
        blogServiceSpy = {
            getPostById: vi.fn(),
            createPost: vi.fn(),
            updatePostById: vi.fn(),
            deletePostById: vi.fn(),
            suggestTags: vi.fn()
        };
        routerSpy = { navigate: vi.fn() };

        await TestBed.configureTestingModule({
            imports: [PostEditorComponent, FormsModule, HttpClientTestingModule],
            providers: [
                { provide: BlogService, useValue: blogServiceSpy },
                { provide: Router, useValue: routerSpy },
                {
                    provide: ActivatedRoute,
                    useValue: {
                        snapshot: { paramMap: { get: () => null } }
                    }
                }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(PostEditorComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    describe('Tags', () => {
        it('should add tags correctly', () => {
            component.newTag = 'test-tag';
            component.addTag();
            expect(component.post.tags).toContain('test-tag');
            expect(component.newTag).toBe('');
        });

        it('should not add duplicates', () => {
            component.post.tags = ['existing'];
            component.newTag = 'existing';
            component.addTag();
            expect(component.post.tags.length).toBe(1);
        });

        it('should remove tags', () => {
            component.post.tags = ['t1', 't2'];
            component.removeTag('t1');
            expect(component.post.tags).toEqual(['t2']);
        });

        it('should call explain suggested tags', () => {
            component.post.title = 'AI';
            component.post.content = 'Content';
            blogServiceSpy.suggestTags.mockReturnValue(of({ tags: ['ai', 'robot'] }));

            component.suggestTags();

            expect(blogServiceSpy.suggestTags).toHaveBeenCalledWith('AI', 'Content');
            expect(component.post.tags).toEqual(['ai', 'robot']);
        });
    });

    describe('Publishing', () => {
        it('should toggle published state and save', () => {
            component.post.published = false;
            blogServiceSpy.createPost.mockReturnValue(of({} as any));

            component.togglePublish();

            expect(component.post.published).toBe(true);
            expect(blogServiceSpy.createPost).toHaveBeenCalled();
        });

        it('should toggle from published to draft', () => {
            component.post.published = true;
            blogServiceSpy.createPost.mockReturnValue(of({} as any));

            component.togglePublish();

            expect(component.post.published).toBe(false);
        });
    });

    describe('Edit Mode and Change Tracking', () => {
        beforeEach(() => {
            // Mock ActivatedRoute for edit mode
            const id = 123;
            component['route'].snapshot.paramMap.get = vi.fn().mockReturnValue(id.toString());
            blogServiceSpy.getPostById.mockReturnValue(of({
                id,
                title: 'Original Title',
                slug: 'original-slug',
                content: 'Original Content',
                language: 'en',
                published: true,
                tags: ['original']
            }));

            component.ngOnInit();
            fixture.detectChanges();
        });

        it('should load post data and show no changes initially', () => {
            expect(component.isEditMode).toBe(true);
            expect(component.post.title).toBe('Original Title');
            expect(component.isChanged('title')).toBe(false);
        });

        it('should detect when a field has changed', () => {
            component.post.title = 'Updated Title';
            expect(component.isChanged('title')).toBe(true);
            expect(component.isChanged('content')).toBe(false);
        });

        it('should detect when tags have changed', () => {
            component.post.tags = ['original', 'new'];
            expect(component.isChanged('tags')).toBe(true);

            component.post.tags = ['original'];
            expect(component.isChanged('tags')).toBe(false);
        });

        it('should handle loading state', () => {
            // Check that loading was set to true during ngOnInit (via loadPost)
            // and should be false after of() emits.
            expect(component.loading).toBe(false);
        });
    });

    describe('Error Handling and Edge Cases', () => {
        beforeEach(() => {
            // Mock window interactions
            vi.spyOn(window, 'alert').mockImplementation(() => { });
            vi.spyOn(window, 'confirm').mockReturnValue(true);
        });

        it('should handle loadPost error', () => {
            const errorResponse = { status: 404, statusText: 'Not Found' };
            blogServiceSpy.getPostById.mockReturnValue({
                subscribe: (observer: any) => observer.error(errorResponse)
            });

            // Trigger load via direct call since ngOnInit mock setup is already done in outer beforeEach
            component['loadPost'](999);

            expect(component.errorMessage).toBe('Failed to load post');
            expect(component.loading).toBe(false);
        });

        it('should handle suggestTags error', () => {
            component.post.title = 'Title';
            component.post.content = 'Content';
            blogServiceSpy.suggestTags.mockReturnValue({
                subscribe: (observer: any) => observer.error('AI Error')
            });

            component.suggestTags();

            expect(component.generatingTags).toBe(false);
            expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Failed to suggest tags'));
        });

        it('should handle empty suggestTags response', () => {
            component.post.title = 'Title';
            component.post.content = 'Content';
            blogServiceSpy.suggestTags.mockReturnValue(of({ tags: [] }));

            component.suggestTags();

            expect(window.alert).toHaveBeenCalledWith('No tags suggested.');
        });

        it('should validate inputs before suggestTags', () => {
            component.post.title = '';
            component.suggestTags();
            expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Please fill in'));
            expect(blogServiceSpy.suggestTags).not.toHaveBeenCalled();
        });

        it('should limit tags during suggestion', () => {
            component.post.title = 'Title';
            component.post.content = 'Content';
            component.post.tags = ['1', '2', '3', '4', '5']; // Full

            blogServiceSpy.suggestTags.mockReturnValue(of({ tags: ['new'] }));

            component.suggestTags();

            expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Tag limit'));
            expect(component.post.tags.length).toBe(5);
        });

        it('should handle save error', () => {
            component.isEditMode = true;
            component.currentId = 1;
            blogServiceSpy.updatePostById.mockReturnValue({
                subscribe: (observer: any) => observer.error({ error: { detail: 'Save Failed' } })
            });

            component.onSubmit();

            expect(component.saving).toBe(false);
            expect(component.errorMessage).toBe('Save Failed');
        });

        it('should handle delete cancellation', () => {
            vi.spyOn(window, 'confirm').mockReturnValue(false);
            component.currentId = 1;

            component.deletePost();

            expect(blogServiceSpy.deletePostById).not.toHaveBeenCalled();
        });

        it('should handle delete error', () => {
            component.currentId = 1;
            blogServiceSpy.deletePostById.mockReturnValue({
                subscribe: (observer: any) => observer.error('Delete Error')
            });

            component.deletePost();

            expect(component.errorMessage).toBe('Failed to delete post');
            expect(component.deleting).toBe(false);
        });

        it('should alert when adding 6th tag manually', () => {
            component.post.tags = ['1', '2', '3', '4', '5'];
            component.newTag = '6';

            component.addTag();

            expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Max 5 tags'));
            expect(component.post.tags.length).toBe(5);
        });
    });
});
