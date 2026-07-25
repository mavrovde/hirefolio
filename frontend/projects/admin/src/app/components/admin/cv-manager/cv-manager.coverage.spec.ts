import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CvManagerComponent } from './cv-manager.component';
import { AdminCvService } from '../../../services/admin-cv.service';
import { of } from 'rxjs';
import { ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

describe('CvManagerComponent sortBy fallback branches', () => {
  let component: CvManagerComponent;
  let fixture: ComponentFixture<CvManagerComponent>;
  let mockCvService: any;

  const resp = { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 };

  beforeEach(async () => {
    mockCvService = {
      getRequests: vi.fn().mockReturnValue(of(resp)),
      getVersions: vi.fn().mockReturnValue(of(resp)),
      uploadCv: vi.fn().mockReturnValue(of({ success: true })),
    };
    await TestBed.configureTestingModule({
      imports: [CommonModule, ReactiveFormsModule, CvManagerComponent],
      providers: [{ provide: AdminCvService, useValue: mockCvService }],
    }).compileComponents();

    fixture = TestBed.createComponent(CvManagerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loadRequests uses created_at default when sortBy is null', () => {
    component.requestsTable.sortBy = null;
    mockCvService.getRequests.mockClear();
    component.loadRequests();
    expect(mockCvService.getRequests).toHaveBeenCalledWith(1, 10, 'created_at', 'desc', null);
  });

  it('loadVersions uses created_at default when sortBy is null', () => {
    component.versionsTable.sortBy = null;
    mockCvService.getVersions.mockClear();
    component.loadVersions();
    expect(mockCvService.getVersions).toHaveBeenCalledWith(1, 10, 'created_at', 'desc', null);
  });
});
