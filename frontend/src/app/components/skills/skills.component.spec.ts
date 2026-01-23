
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SkillsComponent } from './skills.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('SkillsComponent', () => {
    let component: SkillsComponent;
    let fixture: ComponentFixture<SkillsComponent>;

    const mockProfile: Profile = {
        name: 'Test Name',
        headline: 'Test Headline',
        location: 'Test Location',
        about: '',
        contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
        experience: [],
        education: [],
        skills: ['Angular', 'TypeScript', 'TailwindCSS'],
        certifications: [],
        languages: [],
        recommendations: []
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [SkillsComponent]
        })
            .overrideComponent(SkillsComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(SkillsComponent);
        component = fixture.componentInstance;
        component.profile = mockProfile;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should display all skills', () => {
        const compiled = fixture.nativeElement as HTMLElement;
        expect(compiled.textContent).toContain('Angular');
        expect(compiled.textContent).toContain('TypeScript');
        expect(compiled.textContent).toContain('TailwindCSS');
    });
});
