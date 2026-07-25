import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { SeoService } from './seo.service';
import { Title, Meta } from '@angular/platform-browser';
import { PLATFORM_ID } from '@angular/core';

describe('SeoService canonical URL handling', () => {
  afterEach(() => {
    document.querySelectorAll("link[rel='canonical']").forEach((l) => l.remove());
  });

  it('creates then reuses the canonical link on browser platform (line 71-77)', () => {
    TestBed.configureTestingModule({
      providers: [SeoService, Title, Meta, { provide: PLATFORM_ID, useValue: 'browser' }],
    });
    const service = TestBed.inject(SeoService);

    service.updateSeo({ url: '/first' });
    let link = document.querySelector("link[rel='canonical']") as HTMLLinkElement;
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('https://mavrov.de/first');

    // Second call should reuse the existing link element (else-branch not taken)
    service.updateSeo({ url: '/second' });
    const links = document.querySelectorAll("link[rel='canonical']");
    expect(links.length).toBe(1);
    expect((links[0] as HTMLLinkElement).getAttribute('href')).toBe('https://mavrov.de/second');
  });

  it('skips canonical update on server platform (line 61 false branch)', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [SeoService, Title, Meta, { provide: PLATFORM_ID, useValue: 'server' }],
    });
    const service = TestBed.inject(SeoService);

    service.updateSeo({ url: '/server' });
    const link = document.querySelector("link[rel='canonical']");
    expect(link).toBeNull();
  });
});
