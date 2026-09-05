import { ChangeDetectorRef, Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslatePipe } from '@mavrov/shared';
import { InteractionService } from '../../services/interaction.service';

/**
 * Public contact/inquiry form (#69): submissions land in the admin inbox as
 * `source=contact_form` interactions — the recruiter's message is provably
 * received and tracked, not dropped into a mailto: void.
 */
@Component({
    selector: 'app-contact-form',
    standalone: true,
    imports: [CommonModule, ReactiveFormsModule, TranslatePipe],
    templateUrl: './contact-form.component.html',
})
export class ContactFormComponent {
    contactForm: FormGroup;
    isLoading = false;
    successMessage: string | null = null;
    errorMessage: string | null = null;

    constructor(
        private fb: FormBuilder,
        private interactionService: InteractionService,
        private cdr: ChangeDetectorRef
    ) {
        this.contactForm = this.fb.group({
            name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(200)]],
            email: ['', [Validators.required, Validators.email]],
            company: ['', [Validators.maxLength(200)]],
            message: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(10000)]],
        });
    }

    onSubmit() {
        if (this.contactForm.invalid || this.isLoading) {
            return;
        }
        this.isLoading = true;
        this.successMessage = null;
        this.errorMessage = null;

        this.interactionService.submitContact(this.contactForm.value).subscribe({
            next: () => {
                this.isLoading = false;
                this.successMessage = 'CONTACT.SUCCESS';
                this.contactForm.reset();
                // Zoneless: async callback mutates template-read props (#105).
                this.cdr.markForCheck();
            },
            error: () => {
                this.isLoading = false;
                this.errorMessage = 'CONTACT.ERROR';
                // Zoneless: repaint after mutating isLoading/errorMessage (#105).
                this.cdr.markForCheck();
            },
        });
    }
}
