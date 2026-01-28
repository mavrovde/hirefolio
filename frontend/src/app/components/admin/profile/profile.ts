import { Component } from '@angular/core';
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
  oldPassword = '';
  newPassword = '';
  loading = false;
  message = '';
  error = '';

  constructor(private authService: AuthService) { }

  onSubmit() {
    this.loading = true;
    this.message = '';
    this.error = '';

    this.authService.changePassword(this.oldPassword, this.newPassword).subscribe({
      next: () => {
        this.message = 'Password changed successfully.';
        this.oldPassword = '';
        this.newPassword = '';
        this.loading = false;
      },
      error: (err) => {
        this.error = err.error?.detail || 'Failed to change password.';
        this.loading = false;
      },
    });
  }
}
