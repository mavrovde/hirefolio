import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './profile.html',
  styleUrls: ['./profile.scss'],
})
export class ProfileComponent {
  private authService = inject(AuthService);
  oldPassword = '';
  newPassword = '';
  loading = false;
  message = '';
  error = '';
  statusMessage = '';
  currentUser$ = this.authService.currentUser$;

  constructor() { }

  onSubmit() {
    this.loading = true;
    this.message = '';
    this.error = '';
    this.statusMessage = 'Requesting password change...';

    // Phase 1: Verification feedback
    setTimeout(() => {
      this.statusMessage = 'Verifying credentials...';

      // Phase 2: Actual request
      this.authService.changePassword(this.oldPassword, this.newPassword).subscribe({
        next: () => {
          this.statusMessage = 'Password updated successfully.';

          // Phase 3: Success feedback
          setTimeout(() => {
            this.message = 'Password changed successfully.';
            this.statusMessage = '';
            this.oldPassword = '';
            this.newPassword = '';
            this.loading = false;

            // Phase 4: Auto-clear success message
            setTimeout(() => {
              if (this.message === 'Password changed successfully.') {
                this.message = '';
              }
            }, 5000);
          }, 500);
        },
        error: (err) => {
          this.error = err.error?.detail || 'Failed to change password.';
          this.statusMessage = '';
          this.loading = false;
        },
      });
    }, 500);
  }
}
