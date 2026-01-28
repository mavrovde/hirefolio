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

    beforeEach(async () => {
        mockCvService = {
            getRequests: vi.fn().mockReturnValue(of([])), // Use Vitest mock
            getVersions: vi.fn().mockReturnValue(of([])),
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
        component.onFileSelected(event);
        expect(component.selectedFile).toBe(file);
    });

    it('should handle file selection cancellation', () => {
        const event = { target: { files: [] } };
        component.onFileSelected(event);
        expect(component.selectedFile).toBeNull();
    });

    it('should upload cv successfully', () => {
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0' });

        component.onUpload();

        expect(mockCvService.uploadCv).toHaveBeenCalledWith(file, 'v1.0');
        expect(component.uploadSuccess).toBe(true);
        expect(component.uploading).toBe(false);
        expect(component.selectedFile).toBeNull(); // Should reset
        expect(mockCvService.getVersions).toHaveBeenCalledTimes(2); // Initial + after upload
    });

    it('should handle upload error', () => {
        mockCvService.uploadCv.mockReturnValue(throwError(() => ({ error: { detail: 'Error' } })));
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0' });

        component.onUpload();

        expect(component.uploadError).toBe('Error');
        expect(component.uploadSuccess).toBe(false);
        expect(component.uploading).toBe(false);
    });

    it('should use default error message if detail missing', () => {
        mockCvService.uploadCv.mockReturnValue(throwError(() => ({ error: {} })));
        const file = new File([''], 'test.pdf');
        component.selectedFile = file;
        component.uploadForm.setValue({ version: 'v1.0' });

        component.onUpload();

        expect(component.uploadError).toBe('Upload failed');
    });

    it('should not upload if form invalid or no file', () => {
        component.selectedFile = null;
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();

        component.selectedFile = new File([''], 'test.pdf');
        component.uploadForm.setValue({ version: '' }); // Invalid
        component.onUpload();
        expect(mockCvService.uploadCv).not.toHaveBeenCalled();
    });
});
