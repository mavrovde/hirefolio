import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { StatsService, SystemStats } from './stats.service';
import { provideSharedEnvironment } from '../config/environment.token';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('StatsService', () => {
    let service: StatsService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [
                StatsService,
                provideSharedEnvironment({ production: false, apiUrl: '', apiPrefix: '/api/app', googleAnalyticsId: '' }),
            ],
        });
        service = TestBed.inject(StatsService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should get stats', () => {
        const mockStats: SystemStats = {
            posts: { total: 10, published: 8, drafts: 2, by_language: { en: 5, de: 5 } },
            users: 1,
            subscribers: 0,
            visitors: '100',
            top_tags: { angular: 5 },
            recent_posts: [],
            system_health: { database: true, ai_service: true },
        };

        service.getStats().subscribe((stats) => {
            expect(stats).toEqual(mockStats);
        });

        const req = httpMock.expectOne('/api/app/stats');
        expect(req.request.method).toBe('GET');
        req.flush(mockStats);
    });
    it('should get public stats', () => {
        const mockPublicStats = { visitor_ip: '1.2.3.4' };

        service.getPublicStats().subscribe((stats) => {
            expect(stats).toEqual(mockPublicStats);
        });

        const req = httpMock.expectOne('/api/app/stats/public');
        expect(req.request.method).toBe('GET');
        req.flush(mockPublicStats);
    });
});
