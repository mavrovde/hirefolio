import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { HomeComponent } from './home.component';
import { ProfileService } from '../../services/profile.service';
import { LanguageService } from '../../services/language.service';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { MockLanguageService } from '../../testing/mock-language.service';

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
      recommendations: [],
    });
  }
}

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        HomeComponent,
        HttpClientTestingModule, // For child components or service deps if any leak
      ],
      providers: [
        { provide: ProfileService, useClass: MockProfileService },
        { provide: LanguageService, useClass: MockLanguageService },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              fragment: 'about'
            }
          }
        }
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should fetch profile on init', () => {
    expect(component.profile$).toBeTruthy();
  });
});
