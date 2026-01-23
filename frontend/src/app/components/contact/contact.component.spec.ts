import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ContactComponent } from './contact.component';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';
import { Profile } from '../../services/profile.service';

describe('ContactComponent', () => {
    let component: ContactComponent;
    let fixture: ComponentFixture<ContactComponent>;

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
        recommendations: []
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [ContactComponent]
        })
            .overrideComponent(ContactComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(ContactComponent);
        component = fixture.componentInstance;
        component.profile = mockProfile;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });
});
