import { TestBed } from '@angular/core/testing';
import { Title, Meta } from '@angular/platform-browser';
import { SeoService } from './seo.service';
import { vi, describe, it, expect, beforeEach } from 'vitest';

/**
 * #109 — not-found SEO: a not-found <title> plus a `robots: noindex` meta so an
 * unknown blog slug's 404 body is never indexed.
 */
describe('SeoService.setNotFound (#109)', () => {
  let service: SeoService;
  let titleService: Title;
  let metaService: Meta;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [SeoService, Title, Meta] });
    service = TestBed.inject(SeoService);
    titleService = TestBed.inject(Title);
    metaService = TestBed.inject(Meta);
  });

  it('sets a not-found title and a noindex robots meta', () => {
    const titleSpy = vi.spyOn(titleService, 'setTitle');
    const metaSpy = vi.spyOn(metaService, 'updateTag');

    service.setNotFound();

    expect(titleSpy).toHaveBeenCalledWith('Post not found | Sergii Mavrov');
    expect(metaSpy).toHaveBeenCalledWith({ name: 'robots', content: 'noindex' });
  });
});
