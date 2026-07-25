import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ExperienceComponent } from './experience.component';
import { Profile } from '../../services/profile.service';

import { TranslatePipe } from '@mavrov/shared';
import { MockTranslatePipe } from '@mavrov/shared/testing';

describe('ExperienceComponent', () => {
  let component: ExperienceComponent;
  let fixture: ComponentFixture<ExperienceComponent>;

  const mockProfile: Profile = {
    name: 'Test Name',
    headline: 'Test Headline',
    location: 'Test Location',
    about: '',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [
      {
        title: 'Software Engineer',
        company: 'Tech Corp',
        startDate: '2020',
        endDate: 'Present',
        description: 'Developing things',
        skills: ['Angular', 'TypeScript'],
      },
    ],
    education: [],
    skills: [],
    certifications: [],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ExperienceComponent],
    })
      .overrideComponent(ExperienceComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(ExperienceComponent);
    component = fixture.componentInstance;
    component.profile = mockProfile;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display experience title', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Software Engineer');
  });

  it('should display company name', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Tech Corp');
  });

  it('should display experience skills', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Angular');
    expect(compiled.textContent).toContain('TypeScript');
  });
});

describe('ExperienceComponent - Missing Fields', () => {
  let component: ExperienceComponent;
  let fixture: ComponentFixture<ExperienceComponent>;

  const mockProfileMinimal: Profile = {
    name: 'Test Name',
    headline: 'Test Headline',
    location: 'Test Location',
    about: '',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [
      {
        title: 'Software Engineer',
        company: 'Tech Corp',
        startDate: '2020',
        endDate: 'Present',
        description: '', // Empty description
        skills: [],      // No skills
      },
    ],
    education: [],
    skills: [],
    certifications: [],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ExperienceComponent],
    })
      .overrideComponent(ExperienceComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(ExperienceComponent);
    component = fixture.componentInstance;
    component.profile = mockProfileMinimal;
    fixture.detectChanges();
  });

  it('should not display skills container if skills are empty', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const skillsContainer = compiled.querySelector('.flex.flex-wrap.gap-2.mt-4');
    expect(skillsContainer).toBeNull();
  });

  it('should not display description if description is empty', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const description = compiled.querySelector('p.text-primary');
    expect(description).toBeNull();
  });
});

describe('ExperienceComponent - Optional Fields', () => {
  let component: ExperienceComponent;
  let fixture: ComponentFixture<ExperienceComponent>;

  const mockProfileOptional: Profile = {
    name: 'Test Name',
    headline: 'Test Headline',
    location: 'Test Location',
    about: '',
    contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
    experience: [
      {
        title: 'Software Engineer',
        company: 'Tech Corp',
        companyLinkedInUrl: 'https://linkedin.com/company/techcorp',
        startDate: '2020',
        endDate: 'Present',
        location: 'Berlin',
        workType: 'Remote',
        employmentType: 'Full-time',
        description: 'Details',
        skills: ['Angular'],
      },
    ],
    education: [],
    skills: [],
    certifications: [],
    languages: [],
    recommendations: [],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ExperienceComponent],
    })
      .overrideComponent(ExperienceComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(ExperienceComponent);
    component = fixture.componentInstance;
    component.profile = mockProfileOptional;
    fixture.detectChanges();
  });

  it('should display LinkedIn link if companyLinkedInUrl is provided', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const link = compiled.querySelector('a[href="https://linkedin.com/company/techcorp"]');
    expect(link).toBeTruthy();
    expect(link?.textContent).toContain('Tech Corp');
  });

  it('should display location, workType, and employmentType', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Berlin');
    expect(compiled.textContent).toContain('Remote');
    expect(compiled.textContent).toContain('Full-time');
  });
});
