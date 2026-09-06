import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CvManagerComponent } from './cv-manager.component';
import { AdminCvService } from '../../../services/admin-cv.service';
import { of, throwError } from 'rxjs';
import { ReactiveFormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

describe('CvManagerComponent', () => {
    let component: CvManagerComponent;
    let fixture: ComponentFixture<CvManagerComponent>;
    let mockCvService: any;

    const mockPaginatedResponse = {
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        total_pages: 1
    };

    beforeEach(async () => {
        mockCvService = {
            getRequests: vi.fn().mockReturnValue(of(mockPaginatedResponse)),
            getVersions: vi.fn().mockReturnValue(of(mockPaginatedResponse)),
            uploadCv: vi.fn().mockReturnValue(of({ success: true }))
        };

        await TestBed.configureTestingModule({
            imports: [CommonModule, ReactiveFormsModule, CvManagerComponent],
            providers: [
                { provide: AdminCvService, useValue: mockCvService }
            ]
        })
            .compileComponents();

        fixture = TestBed.createComponent(CvManagerComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should load initial data', () => {
        expect(mockCvService.getRequests).toHaveBeenCalled();
        expect(mockCvService.getVersions).toHaveBeenCalled();
    });

    it('should switch tabs', () => {
        component.activeTab = 'requests';
        component.activeTab = 'versions';
        expect(component.activeTab).toBe('versions');
    });

    it('should handle file selection', () => {
        const file = new File([''], 'test.pdf');
        const event = { target: { files: [file] } };
        component.onFileSelected(event as any);
        expect(component.selectedFile).toBe(file);
    });

    it('should handle file selection cancellation', () => {
        const event = { target: { files: [] } };
        component.onFileSelected(event as any);
        expect(component.selectedFile).toBeNull();
    });

    it('should upload cv successfully', () => {
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0', activate: true });

        component.onUpload();

        expect(mockCvService.uploadCv).toHaveBeenCalledWith(file, 'v1.0', true);
        expect(component.successMessage).toBe('ADMIN.CV_UPLOAD_COMPLETE');
        expect(component.uploading).toBe(false);
        expect(component.selectedFile).toBeNull(); // Should reset
        expect(mockCvService.getVersions).toHaveBeenCalledTimes(2); // Initial + after upload
        // reset() must RE-SEED activate=true (#294 round-2 note): a plain
        // reset() nulls the control, renders an UNCHECKED box, and the ?? true
        // fallback still uploads as default — the UI would lie. Pin the
        // control's post-reset value, which only reset({activate:true}) gives.
        expect(component.uploadForm.controls['activate'].value).toBe(true);
    });

    it('uploads a VARIANT when the default checkbox is cleared — and a null control value falls back to true', () => {
        const file = new File(['x'], 'cv.pdf', { type: 'application/pdf' });
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'acme-v1', activate: false });
        mockCvService.uploadCv.mockReturnValue(of({ success: true }));
        component.onUpload();
        expect(mockCvService.uploadCv).toHaveBeenCalledWith(file, 'acme-v1', false);

        // form.reset() nulls controls; the ?? true branch keeps the historical
        // default so the NEXT upload never silently becomes a variant.
        component.selectedFile = file;
        component.uploadForm.controls['version'].setValue('v2');
        component.uploadForm.controls['activate'].setValue(null);
        component.onUpload();
        expect(mockCvService.uploadCv).toHaveBeenLastCalledWith(file, 'v2', true);
    });

    it('should handle upload error', () => {
        mockCvService.uploadCv.mockReturnValue(throwError(() => ({ error: { detail: 'Error' } })));
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0', activate: true });

        component.onUpload();

        expect(component.errorMessage).toBe('Upload failed. Please try again.');
        expect(component.successMessage).toBeNull();
        expect(component.uploading).toBe(false);
    });

    it('should use default error message if detail missing', () => {
        mockCvService.uploadCv.mockReturnValue(throwError(() => ({ error: {} })));
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0', activate: true });

        component.onUpload();

        expect(component.errorMessage).toBe('Upload failed. Please try again.');
    });

    it('should not upload if form invalid or no file', () => {
        component.selectedFile = null;
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();

        component.selectedFile = new File([''], 'test.pdf');
        component.uploadForm.setValue({ version: '', activate: true }); // Invalid
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();
    });

    it('should handle loadRequests error', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
        mockCvService.getRequests.mockReturnValue(throwError(() => new Error('Load failed')));
        component.loadRequests();
        expect(consoleSpy).toHaveBeenCalledWith('Error loading requests:', expect.anything());
    });

    it('should handle loadVersions error', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
        mockCvService.getVersions.mockReturnValue(throwError(() => new Error('Load failed')));
        component.loadVersions();
        expect(consoleSpy).toHaveBeenCalledWith('Error loading versions:', expect.anything());
    });

    it('should handle file selection with no files', () => {
        const event = { target: { files: [] } } as any;
        component.onFileSelected(event);
        expect(component.selectedFile).toBeNull();
    });

    it('should not upload if form is invalid', () => {
        component.uploadForm.setValue({ version: '', activate: true }); // Invalid
        component.selectedFile = new File([''], 'test.pdf');
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();
    });

    it('should not upload if file is missing', () => {
        component.uploadForm.setValue({ version: '1.0', activate: true });
        component.selectedFile = null; // Missing
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();
    });
});
