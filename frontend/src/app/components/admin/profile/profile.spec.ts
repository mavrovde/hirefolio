import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProfileComponent } from './profile';
import { AuthService } from '../../../services/auth.service';
import { TranslatePipe } from '../../../pipes/translate.pipe';
import { FormsModule } from '@angular/forms';
import { of, throwError, BehaviorSubject } from 'rxjs';
import { ChangeDetectorRef } from '@angular/core';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let fixture: ComponentFixture<ProfileComponent>;
  let authServiceSpy: any;
  const currentUserSubject = new BehaviorSubject<any>({
    username: 'admin',
    email: 'admin@mavrov.de',
    is_admin: true,
    gemini_api_key: 'initial-key'
  });

  beforeEach(async () => {
    authServiceSpy = {
      changePassword: vi.fn(),
      updateGeminiKey: vi.fn(),
      currentUser$: currentUserSubject.asObservable()
    };

    await TestBed.configureTestingModule({
      imports: [ProfileComponent, FormsModule, TranslatePipe],
      providers: [
        { provide: AuthService, useValue: authServiceSpy },
        ChangeDetectorRef
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load initial Gemini API Key', () => {
    expect(component.geminiApiKey).toBe('initial-key');
  });

  it('should start with key hidden', () => {
    expect(component.showKey).toBe(false);
  });

  it('should toggle key visibility', () => {
    component.toggleKeyVisibility();
    expect(component.showKey).toBe(true);
    component.toggleKeyVisibility();
    expect(component.showKey).toBe(false);
  });

  it('should toggle new password visibility', () => {
    expect(component.showNewPassword).toBe(false);
    component.toggleNewPasswordVisibility();
    expect(component.showNewPassword).toBe(true);
    component.toggleNewPasswordVisibility();
    expect(component.showNewPassword).toBe(false);
  });

  it('should call updateGeminiKey when saving', () => {
    const newKey = 'new-api-key';
    component.geminiApiKey = newKey;
    const mockUser = {
      username: 'admin',
      email: 'admin@mavrov.de',
      id: 1,
      is_admin: true,
      gemini_api_key: newKey,
      is_active: true,
      hashed_password: 'hash',
      created_at: new Date().toISOString()
    };
    // Fix: mockReturnValue needs to return an observable that matches the expected type
    authServiceSpy.updateGeminiKey.mockReturnValue(of(mockUser));

    component.onSaveKey();

    expect(component.loading).toBe(false);
    expect(component.message).toBe('API Key saved successfully');
    expect(authServiceSpy.updateGeminiKey).toHaveBeenCalledWith(newKey);
  });

  it('should handle save error', () => {
    authServiceSpy.updateGeminiKey.mockReturnValue(throwError(() => new Error('Error')));

    component.onSaveKey();

    expect(component.loading).toBe(false);
    expect(component.error).toBe('Failed to save API Key');
  });

  it('should not submit password change if fields are empty', () => {
    component.oldPassword = '';
    component.newPassword = '';
    component.onSubmit();
    expect(authServiceSpy.changePassword).not.toHaveBeenCalled();
  });

  it('should submit password change successfully', () => {
    vi.useFakeTimers();
    component.oldPassword = 'old';
    component.newPassword = 'new-strong-password';
    authServiceSpy.changePassword.mockReturnValue(of({}));

    component.onSubmit();

    expect(component.loading).toBe(false);
    expect(component.message).toBe('ADMIN.PASSWORD_CHANGED_SUCCESS');
    expect(component.oldPassword).toBe('');
    expect(component.newPassword).toBe('');
    expect(authServiceSpy.changePassword).toHaveBeenCalledWith('old', 'new-strong-password');

    // Test auto-clear message
    vi.advanceTimersByTime(5000);
    expect(component.message).toBe('');
    vi.useRealTimers();
  });

  it('should handle password change error', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';
    const errorResponse = { error: { detail: 'Incorrect password' } };
    authServiceSpy.changePassword.mockReturnValue(throwError(() => errorResponse));

    component.onSubmit();

    expect(component.loading).toBe(false);
    expect(component.error).toBe('Incorrect password');
  });

  it('should handle generic password change error', () => {
    component.oldPassword = 'old';
    component.newPassword = 'new';
    authServiceSpy.changePassword.mockReturnValue(throwError(() => new Error('Network error')));

    component.onSubmit();

    expect(component.loading).toBe(false);
    expect(component.error).toBe('ADMIN.PASSWORD_CHANGE_FAILED');
  });

  it('should handle API key save error', () => {
    component.geminiApiKey = 'new-key';
    authServiceSpy.updateGeminiKey.mockReturnValue(throwError(() => new Error('Save failed')));

    component.onSaveKey();

    expect(component.error).toBe('Failed to save API Key');
    expect(component.loading).toBe(false);
  });
});
