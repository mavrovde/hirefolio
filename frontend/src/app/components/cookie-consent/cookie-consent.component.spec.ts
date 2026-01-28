import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CookieConsentComponent } from './cookie-consent.component';
import { StorageService } from '../../services/storage.service';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';
import { By } from '@angular/platform-browser';
import { vi } from 'vitest';

describe('CookieConsentComponent', () => {
    let component: CookieConsentComponent;
    let fixture: ComponentFixture<CookieConsentComponent>;
    let storageServiceMock: any;

    beforeEach(async () => {
        storageServiceMock = {
            isDecisionMade: vi.fn(),
            setConsent: vi.fn(),
        };

        await TestBed.configureTestingModule({
            imports: [CookieConsentComponent], // TranslatePipe removed here, logic handled in override
            providers: [
                { provide: StorageService, useValue: storageServiceMock },
            ],
        })
            .overrideComponent(CookieConsentComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();
    });

    const createComponent = (decisionMade: boolean) => {
        storageServiceMock.isDecisionMade.mockReturnValue(decisionMade);
        fixture = TestBed.createComponent(CookieConsentComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    };

    it('should create', () => {
        createComponent(false);
        expect(component).toBeTruthy();
    });

    it('should be visible if decision NOT made', () => {
        createComponent(false);
        expect(component.isVisible).toBe(true);
        const banner = fixture.debugElement.query(By.css('.fixed'));
        expect(banner).toBeTruthy();
    });

    it('should be hidden if decision ALREADY made', () => {
        createComponent(true);
        expect(component.isVisible).toBe(false);
        const banner = fixture.debugElement.query(By.css('.fixed'));
        expect(banner).toBeNull();
    });

    it('should call setConsent(true) on accept', () => {
        createComponent(false);
        // Button order depends on template, assume accept is second or has specific class/text
        // We can query by click handler in logic or text content if we used real pipe
        // But simplified: call method directly or find button
        component.accept();
        expect(storageServiceMock.setConsent).toHaveBeenCalledWith(true);
        expect(component.isVisible).toBe(false);
    });

    it('should call setConsent(false) on decline', () => {
        createComponent(false);
        component.decline();
        expect(storageServiceMock.setConsent).toHaveBeenCalledWith(false);
        expect(component.isVisible).toBe(false);
    });
});
