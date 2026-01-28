import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HeroComponent } from './hero.component';
import { Profile } from '../../services/profile.service';
import { By } from '@angular/platform-browser';
import { vi } from 'vitest';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('HeroComponent', () => {
  let component: HeroComponent;
  let fixture: ComponentFixture<HeroComponent>;

  const mockProfile: Profile = {
    name: 'Test Name',
    headline: 'Test Headline',
    location: 'Test Location',
    about: '',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [],
    education: [],
    skills: [],
    certifications: [],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HeroComponent],
    })
      .overrideComponent(HeroComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(HeroComponent);
    component = fixture.componentInstance;
    component.profile = mockProfile;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('create', () => {
    expect(component).toBeTruthy();
  });

  it('should display profile name', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test Name');
  });

  it('should display headline', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test Headline');
  });

  it('should display location', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test Location');
  });

  it('active scrollTo should prevent default behavior and scroll', () => {
    const event = new Event('click');
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault');

    // Mock document.querySelector
    const mockElement = document.createElement('div');
    vi.spyOn(mockElement, 'getBoundingClientRect').mockReturnValue({ top: 100 } as DOMRect);
    vi.spyOn(document, 'querySelector').mockReturnValue(mockElement);

    // Mock window.scrollTo
    const scrollToSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => { });

    component.scrollTo('#about', event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(document.querySelector).toHaveBeenCalledWith('#about');
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 20, // 100 (pos) + 0 (scrollY) - 80 (offset)
      behavior: 'smooth',
    });
  });

  it('scrollTo should do nothing if element is not found', () => {
    const event = new Event('click');
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault');

    vi.spyOn(document, 'querySelector').mockReturnValue(null);
    const scrollToSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => { });

    component.scrollTo('#non-existent', event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(document.querySelector).toHaveBeenCalledWith('#non-existent');
    expect(scrollToSpy).not.toHaveBeenCalled();
  });
});
