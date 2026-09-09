import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { EngagementService, ENGAGEMENT_KINDS } from './engagement.service';
import { environment } from '../../environments/environment';

describe('EngagementService', () => {
  let service: EngagementService;
  let httpMock: HttpTestingController;
  const base = `${environment.apiUrl}${environment.apiPrefix}/admin/analytics`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), EngagementService],
    });
    service = TestBed.inject(EngagementService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('mirrors the kinds the backend emits', () => {
    expect([...ENGAGEMENT_KINDS]).toEqual([
      'cv_request',
      'cv_download',
      'contact_submitted',
    ]);
  });

  it('requests the summary with a default and an explicit window', () => {
    service.summary().subscribe();
    const req = httpMock.expectOne((r) => r.url === `${base}/engagement`);
    expect(req.request.params.get('weeks')).toBe('8');
    expect(req.request.params.get('limit')).toBe('20');
    req.flush({ kinds: [], totals: {}, weeks: [], recent: [] });

    service.summary(12, 5).subscribe();
    const req2 = httpMock.expectOne((r) => r.url === `${base}/engagement`);
    expect(req2.request.params.get('weeks')).toBe('12');
    expect(req2.request.params.get('limit')).toBe('5');
    req2.flush({ kinds: [], totals: {}, weeks: [], recent: [] });
  });

  it('purges and sends the digest via POST', () => {
    let purged = 0;
    service.purge().subscribe((r) => (purged = r.deleted));
    const purge = httpMock.expectOne(`${base}/purge`);
    expect(purge.request.method).toBe('POST');
    purge.flush({ deleted: 3, retention_days: 365 });
    expect(purged).toBe(3);

    let sent: boolean | null = null;
    service.sendDigest().subscribe((r) => (sent = r.sent));
    const digest = httpMock.expectOne(`${base}/digest`);
    expect(digest.request.method).toBe('POST');
    digest.flush({ sent: false });
    expect(sent).toBe(false);
  });
});
