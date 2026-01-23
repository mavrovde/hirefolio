
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RecommendationsComponent } from './recommendations.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('RecommendationsComponent', () => {
    let component: RecommendationsComponent;
    let fixture: ComponentFixture<RecommendationsComponent>;

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
        recommendations: [
            {
                author: 'Jane Doe',
                authorTitle: 'Manager',
                authorLinkedInUrl: 'http://linkedin.com/janedoe',
                text: 'Highly recommended!'
            }
        ]
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [RecommendationsComponent]
        })
            .overrideComponent(RecommendationsComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(RecommendationsComponent);
        component = fixture.componentInstance;
        component.profile = mockProfile;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should display author name', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Jane Doe');
    });

    it('should display recommendation text', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Highly recommended!');
    });
});
