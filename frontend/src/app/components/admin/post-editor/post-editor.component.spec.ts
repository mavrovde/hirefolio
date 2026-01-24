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
    let blogServiceSpy: { getPost: Mock; createPost: Mock; updatePost: Mock; suggestTags: Mock };
    let routerSpy: { navigate: Mock };

    beforeEach(async () => {
        blogServiceSpy = {
            getPost: vi.fn(),
            createPost: vi.fn(),
            updatePost: vi.fn(),
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
});
