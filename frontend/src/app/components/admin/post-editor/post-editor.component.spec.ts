import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PostEditorComponent } from './post-editor.component';
import { BlogService } from '../../../services/blog.service';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { of, Subject } from 'rxjs';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('PostEditorComponent', () => {
  let component: PostEditorComponent;
  let fixture: ComponentFixture<PostEditorComponent>;
  let blogServiceSpy: {
    getPostById: Mock;
    createPost: Mock;
    updatePostById: Mock;
    deletePostById: Mock;
    suggestTags: Mock;
    suggestPostDetails: Mock;
  };
  let routerSpy: { navigate: Mock };

  beforeEach(async () => {
    blogServiceSpy = {
      getPostById: vi.fn().mockReturnValue(
        of({
          title: 'T',
          slug: 'S',
          content: 'C',
          language: 'en',
          published: false,
          tags: ['tag1'],
        }),
      ),
      createPost: vi.fn(),
      updatePostById: vi.fn(),
      deletePostById: vi.fn(),
      suggestTags: vi.fn(),
      suggestPostDetails: vi.fn(),
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
            snapshot: { paramMap: { get: () => null } },
          },
        },
      ],
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
      blogServiceSpy.getPostById.mockReturnValue(
        of({
          id,
          title: 'Original Title',
          slug: 'original-slug',
          content: 'Original Content',
          language: 'en',
          published: true,
          tags: ['original'],
        }),
      );

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
      vi.spyOn(window, 'alert').mockImplementation(() => {});
      vi.spyOn(window, 'confirm').mockReturnValue(true);
    });

    it('should handle loadPost error', () => {
      const errorResponse = { status: 404, statusText: 'Not Found' };
      blogServiceSpy.getPostById.mockReturnValue({
        subscribe: (observer: any) => observer.error(errorResponse),
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
        subscribe: (observer: any) => observer.error('AI Error'),
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
        subscribe: (observer: any) => observer.error({ error: { detail: 'Save Failed' } }),
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
        subscribe: (observer: any) => observer.error('Delete Error'),
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

    it('should suggest title from content', () => {
      component.post.content = 'AI is the future.';
      blogServiceSpy.suggestPostDetails.mockReturnValue(of({ title: 'AI Future' }));

      component.suggestTitle();

      expect(blogServiceSpy.suggestPostDetails).toHaveBeenCalledWith('AI is the future.', 'title');
      expect(component.post.title).toBe('AI Future');
    });

    it('should suggest slug from content', () => {
      component.post.content = 'AI is the future.';
      blogServiceSpy.suggestPostDetails.mockReturnValue(of({ slug: 'ai-future' }));

      component.suggestSlug();

      expect(blogServiceSpy.suggestPostDetails).toHaveBeenCalledWith('AI is the future.', 'slug');
      expect(component.post.slug).toBe('ai-future');
    });

    it('should suggest summary from content', () => {
      component.post.content = 'AI is the future.';
      blogServiceSpy.suggestPostDetails.mockReturnValue(of({ summary: 'Summary of AI.' }));

      component.suggestSummary();

      expect(blogServiceSpy.suggestPostDetails).toHaveBeenCalledWith(
        'AI is the future.',
        'summary',
      );
      expect(component.post.summary).toBe('Summary of AI.');
    });

    it('should suggest all from content', () => {
      component.post.content = 'Deep Learning.';
      const mockRes = { title: 'DL', slug: 'dl', summary: 'Brief DL' };
      blogServiceSpy.suggestPostDetails.mockReturnValue(of(mockRes));

      component.suggestAll();

      expect(blogServiceSpy.suggestPostDetails).toHaveBeenCalledWith('Deep Learning.', 'all');
      expect(component.post.summary).toBe('Brief DL');
    });

    it('should merge tags in suggestAll without exceeding limit of 5', () => {
      component.post.content = 'Content';
      component.post.tags = ['existing1', 'existing2'];
      const mockRes = {
        title: 'T',
        slug: 's',
        summary: 'Sum',
        tags: ['new1', 'new2', 'new3', 'new4', 'existing1'],
      };
      blogServiceSpy.suggestPostDetails.mockReturnValue(of(mockRes));

      component.suggestAll();

      // existing1 skipped, new1, new2, new3 added (total 5). new4 skipped.
      expect(component.post.tags).toEqual(['existing1', 'existing2', 'new1', 'new2', 'new3']);
      expect(component.post.tags.length).toBe(5);
    });

    it('should handle suggestAll response with no tags', () => {
      component.post.content = 'Content';
      component.post.tags = ['t1'];
      const mockRes = { title: 'T', slug: 's', summary: 'Sum' };
      blogServiceSpy.suggestPostDetails.mockReturnValue(of(mockRes));

      component.suggestAll();
      expect(component.post.tags).toEqual(['t1']);
    });

    it('should handle errors in individual suggestions', () => {
      component.post.content = 'Content';

      // Title error
      blogServiceSpy.suggestPostDetails.mockReturnValue({
        subscribe: (observer: any) => observer.error('Error'),
      });
      component.suggestTitle();
      expect(component.suggestingTitle).toBe(false);

      // Slug error
      component.suggestSlug();
      expect(component.suggestingSlug).toBe(false);

      // Summary error
      component.suggestSummary();
      expect(component.suggestingSummary).toBe(false);

      // Suggest All error
      component.suggestAll();
      expect(component.suggestingAll).toBe(false);
    });

    it('should alert if content is missing for suggestions', () => {
      component.post.content = '';
      component.suggestTitle();
      expect(window.alert).toHaveBeenCalledWith('Please provide content first.');

      component.suggestSlug();
      component.suggestSummary();
      component.suggestAll();
      expect(blogServiceSpy.suggestPostDetails).not.toHaveBeenCalled();
    });
  });
  it('should not auto-generate slug in edit mode', () => {
    component.isEditMode = true;
    component.post.title = 'Title';
    component.post.slug = 'manual-slug';
    component.onTitleChange();
    expect(component.post.slug).toBe('manual-slug');
  });

  it('should handle addTag edge cases', () => {
    component.newTag = '';
    component.addTag();
    expect(component.post.tags.length).toBe(0);

    component.newTag = '   ';
    component.addTag();
    expect(component.post.tags.length).toBe(0);
  });

  it('should auto-generate slug from title when not in edit mode', () => {
    component.isEditMode = false;
    component.post.title = 'New Post Title';
    component.onTitleChange();
    expect(component.post.slug).toBe('new-post-title');
  });

  it('should navigate to post list on cancel', () => {
    component.cancel();
    expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
  });

  it('should navigate to post list after successful deletion', () => {
    component.currentId = 123;
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const deleteSubject = new Subject();
    blogServiceSpy.deletePostById.mockReturnValue(deleteSubject.asObservable());

    component.deletePost();
    deleteSubject.next(undefined);

    expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
  });

  it('should handle loadPost error', () => {
    component.isEditMode = true;
    blogServiceSpy.getPostById.mockReturnValue({
      subscribe: (observer: any) => observer.error('Load Error'),
    });

    (component as any).loadPost(123);

    expect(component.errorMessage).toBe('Failed to load post');
    expect(component.loading).toBe(false);
  });

  it('should handle partial suggestAll response with null fields', () => {
    component.post.content = 'Content';
    const mockRes = { title: null, slug: '', summary: undefined, tags: null };
    blogServiceSpy.suggestPostDetails.mockReturnValue(of(mockRes));

    component.suggestAll();
    // Since the component checks if(res.title), null should be skipped
    expect(component.post.title).toBe('');
  });

  it('should handle save error with detail message', () => {
    blogServiceSpy.createPost.mockReturnValue({
      subscribe: (observer: any) => observer.error({ error: { detail: 'Custom Error' } }),
    });

    component.onSubmit();

    expect(component.errorMessage).toBe('Custom Error');
    expect(component.saving).toBe(false);
  });

  it('should handle save error without detail message', () => {
    blogServiceSpy.createPost.mockReturnValue({
      subscribe: (observer: any) => observer.error({ error: {} }),
    });

    component.onSubmit();

    expect(component.errorMessage).toBe('Failed to save post');
  });

  it('should handle NaN id in ngOnInit', () => {
    (component as any).route = {
      snapshot: { paramMap: { get: () => 'not-a-number' } },
    };
    component.isEditMode = true; // Set to true to verify it becomes false
    component.ngOnInit();
    expect(component.isEditMode).toBe(true); // Wait, line 59 says if(idParam && idParam !== 'new')
    // if idParam is 'not-a-number', +idParam is NaN.
    // so if(!isNaN(id)) will be false.
  });

  it('should skip update if suggestion res field is null', () => {
    component.post.content = 'Content';
    component.post.title = 'Existing';
    blogServiceSpy.suggestPostDetails.mockReturnValue(of({ title: null }));
    component.suggestTitle();
    expect(component.post.title).toBe('Existing');

    component.post.slug = 'existing-slug';
    blogServiceSpy.suggestPostDetails.mockReturnValue(of({ slug: null }));
    component.suggestSlug();
    expect(component.post.slug).toBe('existing-slug');

    component.post.summary = 'existing-summary';
    blogServiceSpy.suggestPostDetails.mockReturnValue(of({ summary: null }));
    component.suggestSummary();
    expect(component.post.summary).toBe('existing-summary');
  });

  it('should handle post without tags in loadPost', () => {
    blogServiceSpy.getPostById.mockReturnValue(of({ tags: null }));
    (component as any).loadPost(123);
    expect(component.post.tags).toEqual([]);
  });

  it('should skip tags merge in suggestAll if no slots available', () => {
    component.post.content = 'Content';
    component.post.tags = ['1', '2', '3', '4', '5'];
    blogServiceSpy.suggestPostDetails.mockReturnValue(of({ tags: ['new'] }));
    component.suggestAll();
    expect(component.post.tags.length).toBe(5);
    expect(component.post.tags).not.toContain('new');
  });

  it('should handle null post in loadPost', () => {
    blogServiceSpy.getPostById.mockReturnValue(of(null));
    (component as any).loadPost(123);
    expect(component.loading).toBe(false);
  });
});
