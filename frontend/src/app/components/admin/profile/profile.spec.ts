import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
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
      changePassword: vi.fn().mockReturnValue(of(void 0)),
      currentUser$: of({
        id: 1,
        username: 'testadmin',
        email: 'admin@test.com',
        is_admin: true
      })
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

  it('should handle successful password change', fakeAsync(() => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    component.onSubmit();

    expect(component.statusMessage).toBe('Requesting password change...');

    tick(500); // Phase 1 & 2 (request happens here)
    expect(component.statusMessage).toBe('Password updated successfully.');

    tick(500); // Phase 3 (success message appears)
    expect(authServiceMock.changePassword).toHaveBeenCalledWith('old', 'new');
    expect(component.message).toBe('Password changed successfully.');
    expect(component.statusMessage).toBe('');
    expect(component.oldPassword).toBe('');
    expect(component.newPassword).toBe('');
    expect(component.loading).toBe(false);

    // Phase 4: Verify message clears after 5 seconds
    tick(5000);
    expect(component.message).toBe('');
  }));

  it('should not clear messsage if it was changed before timeout', fakeAsync(() => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    component.onSubmit();
    tick(1000); // Trigger original success

    component.message = 'Something else';

    tick(5000);
    expect(component.message).toBe('Something else');
  }));

  it('should handle password change error', fakeAsync(() => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(throwError(() => ({ error: { detail: 'Incorrect password' } })));

    component.onSubmit();
    tick(800); // Pass the status update timeouts

    expect(component.error).toBe('Incorrect password');
    expect(component.loading).toBe(false);
    expect(component.statusMessage).toBe('');
  }));

  it('should handle password change error without detail', fakeAsync(() => {
    component.oldPassword = 'old';
    component.newPassword = 'new';

    authServiceMock.changePassword.mockReturnValue(throwError(() => ({ error: {} })));

    component.onSubmit();
    tick(800); // Pass the status update timeouts

    expect(component.error).toBe('Failed to change password.');
    expect(component.loading).toBe(false);
  }));

  it('should display user details', () => {
    fixture.detectChanges();
    const nativeElement = fixture.nativeElement as HTMLElement;
    const details = nativeElement.querySelector('.user-details');
    expect(details).toBeTruthy();
    expect(details?.textContent).toContain('testadmin');
    expect(details?.textContent).toContain('admin@test.com');
    expect(details?.textContent).toContain('Superuser/Admin');
  });
});
