import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HeaderComponent } from './header.component';
import { By } from '@angular/platform-browser';
import { vi, afterEach } from 'vitest';
import { Router } from '@angular/router';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

import { LanguageService } from '../../services/language.service';
import { MockLanguageService } from '../../testing/mock-language.service';

describe('HeaderComponent', () => {
  let component: HeaderComponent;
  let fixture: ComponentFixture<HeaderComponent>;
  let router: any;

  beforeEach(async () => {
    router = {
      navigate: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [HeaderComponent],
      providers: [
        { provide: LanguageService, useClass: MockLanguageService },
        { provide: Router, useValue: router },
      ],
    })
      .compileComponents();

    fixture = TestBed.createComponent(HeaderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should have 6 nav items', () => {
    expect(component.navItems.length).toBe(7);
  });

  it('should render navigation links', () => {
    const DEBUG_ELEMENT = fixture.debugElement;
    const navLinks = DEBUG_ELEMENT.queryAll(By.css('nav a'));
    expect(navLinks.length).toBe(7);
  });

  it('should NOT have border-terminal on the header', () => {
    const terminalBorders = fixture.debugElement.queryAll(By.css('header.border-terminal'));
    expect(terminalBorders.length).toBe(0);
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

    component.scrollTo('#test', event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(document.querySelector).toHaveBeenCalledWith('#test');
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 20, // 100 (pos) + 0 (scrollY) - 80 (offset)
      behavior: 'smooth',
    });
  });

  it('scrollTo should navigate via router if href starts with /', () => {
    const event = new Event('click');
    component.scrollTo('/llm', event);
    expect(router.navigate).toHaveBeenCalledWith(['/llm']);
  });

  it('scrollTo should not call window.scrollTo if element is not found', () => {
    const event = new Event('click');
    vi.spyOn(document, 'querySelector').mockReturnValue(null);
    const scrollToSpy = vi.spyOn(window, 'scrollTo');

    component.scrollTo('#non-existent', event);
    expect(scrollToSpy).not.toHaveBeenCalled();
  });

  it('switchLanguage should call setLanguage on LanguageService', () => {
    const languageService = TestBed.inject(LanguageService);
    const setLanguageSpy = vi.spyOn(languageService, 'setLanguage');
    component.switchLanguage('de');
    expect(setLanguageSpy).toHaveBeenCalledWith('de');
  });

  it('should update currentLang when LanguageService emits new language', () => {
    const mockLangService = TestBed.inject(LanguageService) as any;
    mockLangService.setLanguage('de');
    expect(component.currentLang).toBe('de');
  });

  it('should have correct properties in navItems', () => {
    expect(component.navItems[0]).toEqual({ labelKey: 'NAV.ABOUT', href: '#about' });
    expect(component.navItems[4]).toEqual({ labelKey: 'NAV.CV', href: '/cv' });
    expect(component.navItems[component.navItems.length - 1]).toEqual({ labelKey: 'NAV.LLM', href: '/llm' });
  });
});
