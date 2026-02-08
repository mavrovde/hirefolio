import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../services/auth.service';
import { TranslatePipe } from '../../../pipes/translate.pipe';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
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
    this.statusMessage = 'ADMIN.REQUESTING_PASSWORD_CHANGE';

    // Direct call without artificial delays
    this.authService.changePassword(this.oldPassword, this.newPassword).subscribe({
      next: () => {
        console.log('DEBUG: changePassword success');
        this.message = 'ADMIN.PASSWORD_CHANGED_SUCCESS';
        this.statusMessage = '';
        this.oldPassword = '';
        this.newPassword = '';
        this.loading = false;

        // Auto-clear success message after 5 seconds
        setTimeout(() => {
          if (this.message === 'ADMIN.PASSWORD_CHANGED_SUCCESS') {
            this.message = '';
          }
        }, 5000);
      },
      error: (err) => {
        console.error('DEBUG: changePassword error', err);
        this.error = err.error?.detail || 'ADMIN.PASSWORD_CHANGE_FAILED';
        this.statusMessage = '';
        this.loading = false;
      },
    });
  }
}
