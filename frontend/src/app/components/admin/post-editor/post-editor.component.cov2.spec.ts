import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PostEditorComponent } from './post-editor.component';
import { BlogService } from '../../../services/blog.service';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { of, Subject } from 'rxjs';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('PostEditorComponent (cov2: file upload)', () => {
  let component: PostEditorComponent;
  let fixture: ComponentFixture<PostEditorComponent>;
  let blogServiceSpy: {
    getPostById: Mock;
    createPost: Mock;
    updatePostById: Mock;
    deletePostById: Mock;
    suggestTags: Mock;
    suggestPostDetails: Mock;
    uploadImage: Mock;
  };
  let routerSpy: { navigate: Mock };

  beforeEach(async () => {
    blogServiceSpy = {
      getPostById: vi.fn().mockReturnValue(of(null)),
      createPost: vi.fn(),
      updatePostById: vi.fn(),
      deletePostById: vi.fn(),
      suggestTags: vi.fn(),
      suggestPostDetails: vi.fn(),
      uploadImage: vi.fn(),
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

  describe('onFileSelected', () => {
    it('should store the selected file and generate a preview via FileReader', async () => {
      const file = new File(['hello'], 'photo.png', { type: 'image/png' });
      const event = { target: { files: [file] } };

      component.onFileSelected(event);

      expect(component.selectedFile).toBe(file);

      // FileReader.onload is async; wait for it to populate the preview.
      await vi.waitFor(() => {
        expect(component.imagePreview).toContain('data:');
      });
    });

    it('should do nothing when no file is present in the event', () => {
      const event = { target: { files: [] } };

      component.onFileSelected(event);

      expect(component.selectedFile).toBeNull();
      expect(component.imagePreview).toBeNull();
    });
  });

  describe('onSubmit with selected file', () => {
    it('should upload the image after saving and navigate on success', () => {
      const file = new File(['data'], 'photo.png', { type: 'image/png' });
      component.selectedFile = file;

      const saveSubject = new Subject<any>();
      const uploadSubject = new Subject<any>();
      blogServiceSpy.createPost.mockReturnValue(saveSubject.asObservable());
      blogServiceSpy.uploadImage.mockReturnValue(uploadSubject.asObservable());

      component.onSubmit();

      saveSubject.next({ id: 42 });

      expect(blogServiceSpy.uploadImage).toHaveBeenCalledWith(42, file);
      expect(routerSpy.navigate).not.toHaveBeenCalled();

      uploadSubject.next(undefined);

      expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
    });

    it('should navigate anyway when the image upload fails', () => {
      const file = new File(['data'], 'photo.png', { type: 'image/png' });
      component.selectedFile = file;

      blogServiceSpy.createPost.mockReturnValue(of({ id: 7 }));
      blogServiceSpy.uploadImage.mockReturnValue({
        subscribe: (observer: any) => observer.error('upload failed'),
      });

      component.onSubmit();

      expect(blogServiceSpy.uploadImage).toHaveBeenCalledWith(7, file);
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
    });

    it('should navigate directly when a file is selected but saved post has no id', () => {
      const file = new File(['data'], 'photo.png', { type: 'image/png' });
      component.selectedFile = file;

      blogServiceSpy.createPost.mockReturnValue(of({ id: null }));

      component.onSubmit();

      expect(blogServiceSpy.uploadImage).not.toHaveBeenCalled();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
    });

    it('should navigate directly when no file is selected', () => {
      component.selectedFile = null;
      blogServiceSpy.createPost.mockReturnValue(of({ id: 5 }));

      component.onSubmit();

      expect(blogServiceSpy.uploadImage).not.toHaveBeenCalled();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/admin/posts']);
    });
  });
});
