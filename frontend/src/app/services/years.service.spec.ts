import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { YearsService } from './years.service';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('YearsService', () => {
    let service: YearsService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [
                YearsService,
                provideHttpClient(),
                provideHttpClientTesting(),
            ],
        });
        service = TestBed.inject(YearsService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should fetch years from the API', () => {
        const mockYears = [2025, 2024, 2021, 2014, 2009];

        service.getYears().subscribe((years) => {
            expect(years).toEqual(mockYears);
        });

        const req = httpMock.expectOne((r) =>
            r.url.includes('/cv/years') && r.method === 'GET',
        );
        req.flush({ years: mockYears });
    });

    it('should cache the result on subsequent calls', () => {
        const mockYears = [2025, 2024];

        // First call
        service.getYears().subscribe((years) => {
            expect(years).toEqual(mockYears);
        });

        const req = httpMock.expectOne((r) => r.url.includes('/cv/years'));
        req.flush({ years: mockYears });

        // Second call should use cache, no new HTTP request
        service.getYears().subscribe((years) => {
            expect(years).toEqual(mockYears);
        });

        httpMock.expectNone((r) => r.url.includes('/cv/years'));
    });

    it('should return empty array on error', () => {
        service.getYears().subscribe((years) => {
            expect(years).toEqual([]);
        });

        const req = httpMock.expectOne((r) => r.url.includes('/cv/years'));
        req.flush('Error', { status: 500, statusText: 'Server Error' });
    });
});
