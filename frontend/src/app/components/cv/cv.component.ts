import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { CvService } from '../../services/cv.service';
import { HeaderComponent } from '../header/header.component';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
    selector: 'app-cv',
    standalone: true,
    imports: [CommonModule, ReactiveFormsModule, TranslatePipe, HeaderComponent],
    templateUrl: './cv.component.html',
    styleUrl: './cv.component.css'
})
export class CvComponent {
    cvForm: FormGroup;
    isLoading = false;
    successMessage: string | null = null;
    errorMessage: string | null = null;

    constructor(
        private fb: FormBuilder,
        private cvService: CvService
    ) {
        this.cvForm = this.fb.group({
            name: ['', [Validators.required, Validators.minLength(2)]],
            email: ['', [Validators.required, Validators.email]],
            company: [''],
            message: ['', Validators.required]
        });
    }

    onSubmit() {
        if (this.cvForm.invalid) {
            return;
        }

        this.isLoading = true;
        this.successMessage = null;
        this.errorMessage = null;

        this.cvService.requestCv(this.cvForm.value).subscribe({
            next: (response) => {
                this.isLoading = false;
                if (response.success) {
                    this.successMessage = response.message;
                    // Open download link in new tab
                    const fullUrl = this.cvService.getDownloadUrl(response.download_url);
                    window.open(fullUrl, '_blank');
                    this.cvForm.reset();
                }
            },
            error: (error) => {
                this.isLoading = false;
                this.errorMessage = 'Failed to submit request. Please try again later.';
                console.error('CV Request Error:', error);
            }
        });
    }
}
