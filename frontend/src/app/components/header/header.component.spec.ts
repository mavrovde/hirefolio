
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HeaderComponent } from './header.component';
import { By } from '@angular/platform-browser';
import { vi } from 'vitest';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

import { LanguageService } from '../../services/language.service';
import { MockLanguageService } from '../../testing/mock-language.service';

describe('HeaderComponent', () => {
    let component: HeaderComponent;
    let fixture: ComponentFixture<HeaderComponent>;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [HeaderComponent],
            providers: [
                { provide: LanguageService, useClass: MockLanguageService }
            ]
        })
            .overrideComponent(HeaderComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(HeaderComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should have 5 nav items', () => {
        expect(component.navItems.length).toBe(5);
    });

    it('should render navigation links', () => {
        const DEBUG_ELEMENT = fixture.debugElement;
        const navLinks = DEBUG_ELEMENT.queryAll(By.css('nav a'));
        expect(navLinks.length).toBe(5);
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
            behavior: 'smooth'
        });
    });
});
