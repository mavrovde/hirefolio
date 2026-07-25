import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { of, throwError } from 'rxjs';
import { ProfileDataComponent } from './profile-data.component';
import { AdminProfileService, ProfileVersion } from '../../../services/admin-profile.service';

const page = (items: ProfileVersion[] = []) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 10,
  total_pages: 1,
});

const version = (over: Partial<ProfileVersion> = {}): ProfileVersion => ({
  id: 'id-1',
  version: 'v1',
  language: 'en',
  is_active: false,
  created_at: '2026-07-25T00:00:00Z',
  ...over,
});

describe('ProfileDataComponent', () => {
  let component: ProfileDataComponent;
  let fixture: ComponentFixture<ProfileDataComponent>;
  let svc: {
    getVersions: ReturnType<typeof vi.fn>;
    uploadProfile: ReturnType<typeof vi.fn>;
    activateVersion: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    svc = {
      getVersions: vi.fn().mockReturnValue(of(page())),
      uploadProfile: vi.fn().mockReturnValue(of({ success: true })),
      activateVersion: vi.fn().mockReturnValue(of({ success: true })),
    };

    await TestBed.configureTestingModule({
      imports: [CommonModule, ReactiveFormsModule, FormsModule, ProfileDataComponent],
      providers: [{ provide: AdminProfileService, useValue: svc }],
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileDataComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('creates and loads versions on init', () => {
    expect(component).toBeTruthy();
    expect(svc.getVersions).toHaveBeenCalled();
  });

  it('shows an error when loading versions fails', () => {
    svc.getVersions.mockReturnValueOnce(throwError(() => new Error('boom')));
    component.loadVersions();
    expect(component.errorMessage).toBe('ADMIN.PROFILE_DATA_LOAD_FAILED');
    expect(component.loading).toBe(false);
  });

  it('applies a language filter and reloads', () => {
    component.setLanguageFilter('de');
    expect(component.languageFilter).toBe('de');
    expect(svc.getVersions).toHaveBeenLastCalledWith(1, 10, 'created_at', 'desc', 'de');
    component.setLanguageFilter(null);
    expect(svc.getVersions).toHaveBeenLastCalledWith(1, 10, 'created_at', 'desc', null);
  });

  it('selects and cancels a file', () => {
    const file = new File(['{}'], 'profile.json', { type: 'application/json' });
    component.onFileSelected({ target: { files: [file] } } as unknown as Event);
    expect(component.selectedFile).toBe(file);

    component.onFileSelected({ target: { files: [] } } as unknown as Event);
    expect(component.selectedFile).toBe(file); // unchanged when nothing picked
  });

  it('does nothing on upload when form invalid or no file', () => {
    component.selectedFile = null;
    component.onUpload();
    expect(svc.uploadProfile).not.toHaveBeenCalled();
  });

  it('uploads successfully and resets', () => {
    const file = new File(['{}'], 'profile.json', { type: 'application/json' });
    component.selectedFile = file;
    component.selectedLanguage = 'de';
    component.uploadForm.setValue({ version: 'v2' });

    component.onUpload();

    expect(svc.uploadProfile).toHaveBeenCalledWith(file, 'v2', 'de');
    expect(component.successMessage).toBe('ADMIN.PROFILE_DATA_UPLOAD_COMPLETE');
    expect(component.selectedFile).toBeNull();
    expect(component.uploading).toBe(false);
  });

  it('surfaces the server detail on upload error', () => {
    svc.uploadProfile.mockReturnValueOnce(
      throwError(() => ({ error: { detail: 'Version already exists' } })),
    );
    component.selectedFile = new File(['{}'], 'p.json');
    component.uploadForm.setValue({ version: 'v1' });
    component.onUpload();
    expect(component.errorMessage).toBe('Version already exists');
  });

  it('falls back to a generic message on upload error without detail', () => {
    svc.uploadProfile.mockReturnValueOnce(throwError(() => ({})));
    component.selectedFile = new File(['{}'], 'p.json');
    component.uploadForm.setValue({ version: 'v1' });
    component.onUpload();
    expect(component.errorMessage).toBe('ADMIN.PROFILE_DATA_UPLOAD_FAILED');
  });

  it('does not activate an already-active version', () => {
    component.onActivate(version({ is_active: true }));
    expect(svc.activateVersion).not.toHaveBeenCalled();
  });

  it('activates an inactive version', () => {
    component.onActivate(version({ id: 'x', is_active: false }));
    expect(svc.activateVersion).toHaveBeenCalledWith('x');
    expect(component.successMessage).toBe('ADMIN.PROFILE_DATA_ACTIVATE_COMPLETE');
  });

  it('shows an error when activation fails', () => {
    svc.activateVersion.mockReturnValueOnce(throwError(() => new Error('nope')));
    component.onActivate(version({ is_active: false }));
    expect(component.errorMessage).toBe('ADMIN.PROFILE_DATA_ACTIVATE_FAILED');
    expect(component.loading).toBe(false);
  });

  it('falls back to created_at when the table has no sort field', () => {
    component.versionsTable.sortBy = null;
    component.loadVersions();
    expect(svc.getVersions).toHaveBeenLastCalledWith(1, 10, 'created_at', 'desc', null);
  });

  it('unsubscribes on destroy', () => {
    expect(() => fixture.destroy()).not.toThrow();
  });
});
