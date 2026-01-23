
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ProfileService, Profile } from './profile.service';
import { LanguageService } from './language.service';
import { MockLanguageService } from '../testing/mock-language.service';

describe('ProfileService', () => {
    let service: ProfileService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [
                ProfileService,
                { provide: LanguageService, useClass: MockLanguageService }
            ]
        });
        service = TestBed.inject(ProfileService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should fetch profile data from assets', () => {
        const dummyProfile: Profile = {
            name: 'John Doe',
            headline: 'Developer',
            location: 'City',
            about: 'Bio',
            contact: { email: 'test@example.com', linkedin: 'https://linkedin.com/test' },
            experience: [],
            education: [],
            skills: ['Angular'],
            certifications: [],
            languages: [],
            recommendations: []
        };

        service.getProfile().subscribe(profile => {
            expect(profile).toEqual(dummyProfile);
        });

        const req = httpMock.expectOne('assets/profile_data_en.json');
        expect(req.request.method).toBe('GET');
        req.flush(dummyProfile);
    });
});
