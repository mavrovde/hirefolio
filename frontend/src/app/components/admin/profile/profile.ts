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
    console.log('DEBUG: onSubmit started');
    if (!this.oldPassword || !this.newPassword) {
      return;
    }

    this.loading = true;
    this.message = '';
    this.error = '';
    this.statusMessage = 'Requesting password change...';

    // Direct call without artificial delays
    this.authService.changePassword(this.oldPassword, this.newPassword).subscribe({
      next: () => {
        console.log('DEBUG: changePassword success');
        this.message = 'Password changed successfully.';
        this.statusMessage = '';
        this.oldPassword = '';
        this.newPassword = '';
        this.loading = false;

        // Auto-clear success message after 5 seconds
        setTimeout(() => {
          if (this.message === 'Password changed successfully.') {
            this.message = '';
          }
        }, 5000);
      },
      error: (err) => {
        console.error('DEBUG: changePassword error', err);
        this.error = err.error?.detail || 'Failed to change password.';
        this.statusMessage = '';
        this.loading = false;
      },
    });
  }
}
