import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { SiteSettingsService } from './site-settings.service';
import { environment } from '../../environments/environment';

describe('SiteSettingsService', () => {
    let service: SiteSettingsService;
    let httpMock: HttpTestingController;
    const base = `${environment.apiUrl}${environment.apiPrefix}/admin/site-settings`;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [provideHttpClient(), provideHttpClientTesting(), SiteSettingsService],
        });
        service = TestBed.inject(SiteSettingsService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => httpMock.verify());

    it('reads and writes the availability state', () => {
        service.getAvailability().subscribe();
        httpMock.expectOne(`${base}/availability`).flush({ value: 'listening' });

        service.setAvailability('open').subscribe();
        const put = httpMock.expectOne(`${base}/availability`);
        expect(put.request.method).toBe('PUT');
        expect(put.request.body).toEqual({ value: 'open' });
        put.flush({ value: 'open' });
    });
});
