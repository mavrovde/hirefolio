
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

  it('should call updateGeminiKey when saving', () => {
    const newKey = 'new-api-key';
    component.geminiApiKey = newKey;
    authServiceSpy.updateGeminiKey.mockReturnValue(of({
      username: 'admin',
      email: 'admin@mavrov.de',
      id: 1,
      is_admin: true,
      gemini_api_key: newKey
    }));

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
});
