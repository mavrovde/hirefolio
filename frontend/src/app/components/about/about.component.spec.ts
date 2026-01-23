
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AboutComponent } from './about.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('AboutComponent', () => {
    let component: AboutComponent;
    let fixture: ComponentFixture<AboutComponent>;

    const mockProfile: Profile = {
        name: 'Test Name',
        headline: 'Test Headline',
        location: 'Test Location',
        about: 'Test About Description',
        contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
        experience: [],
        education: [],
        skills: [],
        certifications: [],
        languages: [],
        recommendations: []
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [AboutComponent]
        })
            .overrideComponent(AboutComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(AboutComponent);
        component = fixture.componentInstance;
        component.profile = mockProfile;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should display about text', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Test About Description');
    });

    it('should display section title', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.querySelector('h2')?.textContent).toContain('SECTION.ABOUT');
    });
});
