import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { ProfileService } from './services/profile.service';
import { GoogleAnalyticsService } from './services/analytics.service';
import { LanguageService } from './services/language.service';
import { HttpClientTestingModule } from '@angular/common/http/testing'; // For icons? No, likely not needed if mocked.
import { of } from 'rxjs';
import { MockLanguageService } from '../app/testing/mock-language.service';
import { MockTranslatePipe } from '../app/testing/mock-translate.pipe'; // Can we use this globally? No.
import { TranslatePipe } from './pipes/translate.pipe';

// Mock Services
class MockProfileService {
    getProfile() {
        return of({
            name: 'Test',
            headline: 'Headline',
            location: 'Loc',
            about: 'About',
            contact: { email: 'e', linkedin: 'l' },
            experience: [],
            education: [],
            skills: [],
            certifications: [],
            languages: [],
            recommendations: []
        });
    }
}

class MockAnalyticsService {
    initializeGoogleAnalytics() { }
    trackPageViews() { }
}

describe('AppComponent', () => {
    let component: AppComponent;
    let fixture: ComponentFixture<AppComponent>;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [
                AppComponent,
                // We might need to import HttpClientTestingModule if real components use it?
                // Header uses LanguageService which uses HttpClient. But we mock LanguageService.
                // Other components are dumb (Hero, etc).
                // SystemStatsComponent? It uses TranslatePipe. Real TranslatePipe needs LanguageService.
                // But wait, children import REAL TranslatePipe.
                // Real TranslatePipe needs LanguageService.
                // We provide MockLanguageService.
                // Real TranslatePipe subscribes to MockLanguageService.translate().
                // MockLanguageService.translate() returns observable.
                // So this should work!
            ],
            providers: [
                { provide: ProfileService, useClass: MockProfileService },
                { provide: GoogleAnalyticsService, useClass: MockAnalyticsService },
                { provide: LanguageService, useClass: MockLanguageService }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(AppComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create the app', () => {
        expect(component).toBeTruthy();
    });

    it('should fetch profile on init', () => {
        expect(component.profile$).toBeTruthy();
    });
});
