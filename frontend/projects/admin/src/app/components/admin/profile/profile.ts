import { Component, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../services/auth.service';
import { TranslatePipe } from '@mavrov/shared';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './profile.html',
  styleUrls: ['./profile.scss'],
})
export class ProfileComponent {
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  oldPassword = '';
  newPassword = '';
  loading = false;
  message = '';
  error = '';
  statusMessage = '';
  currentUser$ = this.authService.currentUser$;

  geminiApiKey = '';
  hasGeminiKey = false;
  showKey = false;
  showNewPassword = false;

  constructor() { }

  ngOnInit() {
    // SECURITY (issue #143): the raw key is never sent to the browser. We only
    // learn whether one is configured (has_gemini_key) and offer a write-only
    // set/replace field that is never pre-filled with the secret.
    this.currentUser$.subscribe(user => {
      if (user) {
        this.hasGeminiKey = !!user.has_gemini_key;
      }
    });
  }

  toggleKeyVisibility() {
    this.showKey = !this.showKey;
  }

  toggleNewPasswordVisibility() {
    this.showNewPassword = !this.showNewPassword;
  }

  onSaveKey() {
    this.loading = true;
    this.message = '';
    this.error = '';
    this.statusMessage = 'Saving API Key...';

    this.authService.updateGeminiKey(this.geminiApiKey).subscribe({
      next: (user) => {
        this.message = 'API Key saved successfully';
        this.statusMessage = '';
        this.loading = false;
        this.hasGeminiKey = !!user.has_gemini_key;
        // Never keep the secret in memory / the DOM after a successful write.
        this.geminiApiKey = '';
        this.cdr.detectChanges();
        setTimeout(() => this.message = '', 3000);
      },
      error: (err) => {
        this.error = 'Failed to save API Key';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  onSubmit() {
    console.log('DEBUG: onSubmit started');
    if (!this.oldPassword || !this.newPassword) {
      return;
    }

    this.loading = true;
    this.message = '';
    this.error = '';
    this.statusMessage = 'ADMIN.REQUESTING_PASSWORD_CHANGE';
    this.cdr.detectChanges();

    // Direct call without artificial delays
    this.authService.changePassword(this.oldPassword, this.newPassword).subscribe({
      next: () => {
        console.log('DEBUG: changePassword success');
        this.message = 'ADMIN.PASSWORD_CHANGED_SUCCESS';
        this.statusMessage = '';
        this.oldPassword = '';
        this.newPassword = '';
        this.loading = false;
        this.cdr.detectChanges();

        // Auto-clear success message after 5 seconds
        setTimeout(() => {
          if (this.message === 'ADMIN.PASSWORD_CHANGED_SUCCESS') {
            this.message = '';
            this.cdr.detectChanges();
          }
        }, 5000);
      },
      error: (err) => {
        console.error('DEBUG: changePassword error', err);
        this.error = err.error?.detail || 'ADMIN.PASSWORD_CHANGE_FAILED';
        this.statusMessage = '';
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }
}
