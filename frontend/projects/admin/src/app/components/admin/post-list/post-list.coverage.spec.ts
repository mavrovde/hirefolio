import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { PostListComponent } from './post-list.component';
import { BlogService } from '@mavrov/shared';
import { of } from 'rxjs';
import { RouterTestingModule } from '@angular/router/testing';

describe('PostListComponent sortBy fallback', () => {
  let component: PostListComponent;
  let fixture: ComponentFixture<PostListComponent>;
  let blogServiceSpy: any;
  const resp = { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 };

  beforeEach(async () => {
    blogServiceSpy = { getPosts: vi.fn().mockReturnValue(of(resp)), deletePostById: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [PostListComponent, RouterTestingModule],
      providers: [{ provide: BlogService, useValue: blogServiceSpy }],
    }).compileComponents();
    fixture = TestBed.createComponent(PostListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('uses created_at default when table.sortBy is null', () => {
    component.table.sortBy = null;
    blogServiceSpy.getPosts.mockClear();
    component.loadPosts();
    expect(blogServiceSpy.getPosts).toHaveBeenCalledWith(
      false,
      null,
      null,
      1,
      10,
      'created_at',
      'desc',
      null,
    );
  });
});
