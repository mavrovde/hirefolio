import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EducationComponent } from './education.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '@mavrov/shared';
import { MockTranslatePipe } from '@mavrov/shared/testing';

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
        skills: 'Computer Science',
      },
    ],
    skills: [],
    certifications: [
      {
        name: 'Test Certification',
        issuer: 'Test Issuer',
        date: '2020',
        credentialUrl: 'http://test.com',
      },
    ],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EducationComponent],
    })
      .overrideComponent(EducationComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
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

  it('should display education focus/skills if provided', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Focus: Computer Science');
  });

  it('should display credential link if credentialUrl is provided', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const link = compiled.querySelector('a[href="http://test.com"]');
    expect(link).toBeTruthy();
  });
});

describe('EducationComponent - Missing Fields', () => {
  let component: EducationComponent;
  let fixture: ComponentFixture<EducationComponent>;

  const mockProfileMinimal: Profile = {
    name: 'Test Name',
    headline: 'Test Headline',
    location: 'Test Location',
    about: '',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [],
    education: [
      {
        school: 'Test School',
        degree: 'Degree',
        years: '2020',
        skills: '', // No skills
      },
    ],
    skills: [],
    certifications: [
      {
        name: 'Cert',
        issuer: 'Issuer',
        date: '2021',
        // No credentialUrl
      },
    ],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EducationComponent],
    })
      .overrideComponent(EducationComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(EducationComponent);
    component = fixture.componentInstance;
    component.profile = mockProfileMinimal;
    fixture.detectChanges();
  });

  it('should not display focus section if education skills are empty', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).not.toContain('Focus:');
  });

  it('should not display credential link if credentialUrl is missing', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const link = compiled.querySelector('a');
    expect(link).toBeNull();
  });
});

describe('EducationComponent - Null Profile', () => {
  let component: EducationComponent;
  let fixture: ComponentFixture<EducationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EducationComponent],
    })
      .overrideComponent(EducationComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(EducationComponent);
    component = fixture.componentInstance;
    component.profile = null;
    fixture.detectChanges();
  });

  it('should not display education or certifications list if profile is null', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const containers = compiled.querySelectorAll('.space-y-6, .space-y-4');
    containers.forEach((container) => {
      expect(container.children.length).toBe(0);
    });
  });
});
