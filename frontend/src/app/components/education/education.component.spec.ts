
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EducationComponent } from './education.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('EducationComponent', () => {
    let component: EducationComponent;
    let fixture: ComponentFixture<EducationComponent>;

    const mockProfile: Profile = {
        name: 'Test Name',
        headline: 'Test Headline',
        location: 'Test Location',
        about: '',
        contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
        experience: [],
        education: [
            {
                school: 'Test University',
                degree: 'Master of Science',
                years: '2015 - 2017',
                skills: 'Computer Science'
            }
        ],
        skills: [],
        certifications: [
            {
                name: 'Test Certification',
                issuer: 'Test Issuer',
                date: '2020',
                credentialUrl: 'http://test.com'
            }
        ],
        languages: [],
        recommendations: []
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [EducationComponent]
        })
            .overrideComponent(EducationComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(EducationComponent);
        component = fixture.componentInstance;
        component.profile = mockProfile;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should display school name', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Test University');
    });

    it('should display degree', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Master of Science');
    });

    it('should display certification name', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Test Certification');
    });
});
