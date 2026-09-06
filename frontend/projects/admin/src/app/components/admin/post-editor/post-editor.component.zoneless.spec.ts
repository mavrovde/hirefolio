/**
 * Zoneless repaint regression pin (#276) — see the header of
 * admin-layout.component.zoneless.spec.ts for why this TestBed opts into
 * `provideZonelessChangeDetection()` instead of relying on the zone.js that
 * src/test-setup.ts loads.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

import { PostEditorComponent } from './post-editor.component';
import { BlogService } from '@mavrov/shared';

describe('PostEditorComponent (zoneless repaint)', () => {
  let component: PostEditorComponent;
  let fixture: ComponentFixture<PostEditorComponent>;
  let host: HTMLElement;
  let blogServiceSpy: { getPostById: Mock; createPost: Mock; uploadImage: Mock };

  beforeEach(async () => {
    blogServiceSpy = {
      getPostById: vi.fn().mockReturnValue(of(null)),
      createPost: vi.fn(),
      uploadImage: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [PostEditorComponent, FormsModule, HttpClientTestingModule],
      providers: [
        provideZonelessChangeDetection(),
        { provide: BlogService, useValue: blogServiceSpy },
        { provide: Router, useValue: { navigate: vi.fn() } },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => null } } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PostEditorComponent);
    component = fixture.componentInstance;
    host = fixture.nativeElement as HTMLElement;
  });

  it('repaints the error banner when the save request fails', async () => {
    await fixture.whenStable();
    expect(host.querySelector('.error-message')).toBeNull();

    blogServiceSpy.createPost.mockReturnValue(
      throwError(() => ({ error: { detail: 'Slug already exists' } })),
    );
    vi.spyOn(console, 'error').mockImplementation(() => {});

    component.onSubmit();

    // Deliberately NO detectChanges() here: without the component's own
    // repaint the operator sees the form stuck on "[ Saving... ]" and never
    // learns why the save failed.
    expect(host.querySelector('.error-message')?.textContent).toContain(
      'Slug already exists',
    );
    expect(component.saving).toBe(false);
  });
});
