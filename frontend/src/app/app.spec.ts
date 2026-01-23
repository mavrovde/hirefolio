
import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { ProfileService } from './services/profile.service';
import { of } from 'rxjs';
import { HttpClientTestingModule } from '@angular/common/http/testing';

describe('AppComponent', () => {
  beforeEach(async () => {
    const profileServiceMock = {
      getProfile: () => of({
        name: 'Test Name',
        headline: 'Test Headline',
        location: 'Test Location',
        about: 'Test About',
        experience: [],
        education: [],
        skills: [],
        certifications: [],
        languages: [],
        recommendations: []
      })
    };

    await TestBed.configureTestingModule({
      imports: [AppComponent, HttpClientTestingModule],
      providers: [
        { provide: ProfileService, useValue: profileServiceMock }
      ]
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render header', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-header')).toBeTruthy();
  });
});
