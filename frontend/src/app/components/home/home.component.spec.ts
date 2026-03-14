import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { ViewportScroller } from '@angular/common';
import { vi } from 'vitest';
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

  let mockActivatedRoute: any;

  beforeEach(async () => {
    mockActivatedRoute = {
      snapshot: {
        fragment: 'about'
      },
      fragment: of('about')
    };

    await TestBed.configureTestingModule({
      imports: [
        HomeComponent,
        HttpClientTestingModule,
      ],
      providers: [
        { provide: ProfileService, useClass: MockProfileService },
        { provide: LanguageService, useClass: MockLanguageService },
        { provide: ActivatedRoute, useValue: mockActivatedRoute }
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    // fixture.detectChanges(); // Removed to allow tests to configure mock before init
  });

  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('should fetch profile on init', () => {
    fixture.detectChanges();
    expect(component.profile$).toBeTruthy();
  });

  it('should attempt scrolling if fragment exists', fakeAsync(() => {
    // We mocked 'about' in providers
    const viewportScroller = TestBed.inject(ViewportScroller);
    const scrollSpy = vi.spyOn(viewportScroller, 'scrollToAnchor');

    // Create a dummy element for the fragment
    const div = document.createElement('div');
    div.id = 'about';
    document.body.appendChild(div);

    fixture.detectChanges(); // triggers ngOnInit

    // First interval tick: scrollAttempts === 0 branch
    tick(100);
    expect(scrollSpy).toHaveBeenCalledWith('about');

    // Multiple ticks: scrollAttempts > 0 branch
    tick(100);
    tick(100);

    // Fast forward to finish loop: maxScrollAttempts branch
    tick(1500);

    document.body.removeChild(div);
  }));

  it('should stop trying after max attempts if element not found', fakeAsync(() => {
    mockActivatedRoute.snapshot.fragment = 'non-existent';
    const viewportScroller = TestBed.inject(ViewportScroller);
    const scrollSpy = vi.spyOn(viewportScroller, 'scrollToAnchor');

    fixture.detectChanges(); // triggers ngOnInit

    // Fast forward just below max attempts
    tick(2900);
    expect(scrollSpy).not.toHaveBeenCalled();

    // Hit max attempts (30)
    tick(100);

    // Verify it doesn't run anymore
    tick(1000);

    expect(scrollSpy).not.toHaveBeenCalled();
  }));

  it('should do nothing if no fragment', fakeAsync(() => {
    mockActivatedRoute.snapshot.fragment = null;
    fixture.detectChanges();
    tick(1000);
    // No interval started/everything cleared
  }));
});
