import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RecommendationsComponent } from './recommendations.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '@mavrov/shared';
import { MockTranslatePipe } from '@mavrov/shared/testing';

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
        text: 'Highly recommended!',
      },
    ],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RecommendationsComponent],
    })
      .overrideComponent(RecommendationsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
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

  it('should display LinkedIn link with correct URL', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const link = compiled.querySelector('a') as HTMLAnchorElement;
    expect(link.href).toContain('http://linkedin.com/janedoe');
  });

  it('should display author title', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Manager');
  });

  it('should display author initial in avatar', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const avatar = compiled.querySelector('.shrink-0.border.border-primary');
    expect(avatar?.textContent).toContain('J');
  });
});

describe('RecommendationsComponent - Null Profile', () => {
  let component: RecommendationsComponent;
  let fixture: ComponentFixture<RecommendationsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RecommendationsComponent],
    })
      .overrideComponent(RecommendationsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(RecommendationsComponent);
    component = fixture.componentInstance;
    component.profile = null;
    fixture.detectChanges();
  });

  it('should not display recommendations if profile is null', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const list = compiled.querySelector('.flex.overflow-x-auto');
    expect(list).toBeNull();
  });
});
