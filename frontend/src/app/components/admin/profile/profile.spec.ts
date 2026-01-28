import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProfileComponent } from './profile';
import { AuthService } from '../../../services/auth.service';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let fixture: ComponentFixture<ProfileComponent>;
  let authServiceMock: any;

  beforeEach(async () => {
    authServiceMock = {
      changePassword: vi.fn().mockReturnValue(of(void 0))
    };

    await TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock }
      ]
    })
      .compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should handle successful password change', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    // reset mock if needed, or rely on vi.fn
    // But we defined it in beforeEach. 

    component.onSubmit();

    expect(authServiceMock.changePassword).toHaveBeenCalledWith('old', 'new');
    expect(component.message).toBe('Password changed successfully.');
    expect(component.oldPassword).toBe('');
    expect(component.newPassword).toBe('');
    expect(component.loading).toBe(false);
  });

  it('should handle password change error', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(throwError(() => ({ error: { detail: 'Incorrect password' } })));

    component.onSubmit();

    expect(component.error).toBe('Incorrect password');
    expect(component.loading).toBe(false);
  });

  it('should handle password change error without detail', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(throwError(() => ({ error: {} })));

    component.onSubmit();

    expect(component.error).toBe('Failed to change password.');
    expect(component.loading).toBe(false);
  });
});
