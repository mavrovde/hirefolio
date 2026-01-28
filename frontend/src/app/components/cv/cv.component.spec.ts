import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CvComponent } from './cv.component';
import { CvService } from '../../services/cv.service';
import { of, throwError } from 'rxjs';
import { ReactiveFormsModule } from '@angular/forms';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Pipe, PipeTransform } from '@angular/core';

// Mock TranslatePipe
@Pipe({ name: 'translate', standalone: true })
class MockTranslatePipe implements PipeTransform {
    transform(value: string): string {
        return value;
    }
}

describe('CvComponent', () => {
    let component: CvComponent;
    let fixture: ComponentFixture<CvComponent>;
    let cvService: any; // Use any for mock to avoid type issues with jasmine vs vitest

    beforeEach(async () => {
        // Mock CvService manually
        cvService = {
            requestCv: vi.fn(),
            getDownloadUrl: vi.fn()
        };

        await TestBed.configureTestingModule({
            imports: [ReactiveFormsModule, HttpClientTestingModule, CvComponent],
            providers: [
                { provide: CvService, useValue: cvService }
            ]
        })
            .overrideComponent(CvComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(CvComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should initialize form invalid', () => {
        expect(component.cvForm.valid).toBe(false);
    });

    it('should be valid when filled correctly', () => {
        component.cvForm.controls['name'].setValue('John Doe');
        component.cvForm.controls['email'].setValue('john@example.com');
        component.cvForm.controls['message'].setValue('Hello, I would like to request your CV.');
        expect(component.cvForm.valid).toBe(true);
    });



    it('should call requestCv on submit', () => {
        component.cvForm.controls['name'].setValue('John Doe');
        component.cvForm.controls['email'].setValue('john@example.com');
        component.cvForm.controls['message'].setValue('Relevant message');

        cvService.requestCv.mockReturnValue(of({ success: true, message: 'Success', download_url: '/url' }));
        cvService.getDownloadUrl.mockReturnValue('http://full/url');

        // Mock window.open
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

        component.onSubmit();

        expect(cvService.requestCv).toHaveBeenCalledWith(expect.objectContaining({
            name: 'John Doe',
            email: 'john@example.com'
        }));
        expect(component.successMessage).toBe('Success');

        openSpy.mockRestore();
    });

    it('should not call requestCv on submit if form is invalid', () => {
        component.cvForm.controls['name'].setValue(''); // Invalid
        component.onSubmit();
        expect(cvService.requestCv).not.toHaveBeenCalled();
    });

    it('should handle response.success = false', () => {
        component.cvForm.controls['name'].setValue('John Doe');
        component.cvForm.controls['email'].setValue('john@example.com');
        component.cvForm.controls['message'].setValue('Msg');

        cvService.requestCv.mockReturnValue(of({ success: false, message: 'Failed' }));

        component.onSubmit();

        expect(component.isLoading).toBe(false);
        expect(component.successMessage).toBeNull();
    });

    it('should handle error', () => {
        component.cvForm.controls['name'].setValue('John Doe');
        component.cvForm.controls['email'].setValue('john@example.com');
        component.cvForm.controls['message'].setValue('Relevant message');

        cvService.requestCv.mockReturnValue(throwError(() => new Error('Err')));

        component.onSubmit();

        expect(component.errorMessage).toBe('Failed to submit request. Please try again later.');
        expect(component.isLoading).toBe(false);
    });
});
