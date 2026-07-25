import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TagManagerComponent } from './tag-manager.component';
import { TagsService } from '../../../services/tags.service';
import { of } from 'rxjs';

describe('TagManagerComponent sortBy fallback', () => {
  let component: TagManagerComponent;
  let fixture: ComponentFixture<TagManagerComponent>;
  let tagsServiceSpy: any;
  const resp = { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 };

  beforeEach(async () => {
    tagsServiceSpy = { getAllTags: vi.fn().mockReturnValue(of(resp)), renameTag: vi.fn(), deleteTag: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [TagManagerComponent],
      providers: [{ provide: TagsService, useValue: tagsServiceSpy }],
    }).compileComponents();
    fixture = TestBed.createComponent(TagManagerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('uses count default when table.sortBy is null', () => {
    component.table.sortBy = null;
    tagsServiceSpy.getAllTags.mockClear();
    component.loadTags();
    expect(tagsServiceSpy.getAllTags).toHaveBeenCalledWith(1, 10, 'count', 'desc', null);
  });
});
