import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { SeoService } from './seo.service';
import { Title, Meta } from '@angular/platform-browser';
import { RouterTestingModule } from '@angular/router/testing';

describe('SeoService', () => {
  let service: SeoService;
  let titleService: Title;
  let metaService: Meta;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [RouterTestingModule],
      providers: [
        SeoService,
        Title,
        Meta
      ]
    });
    service = TestBed.inject(SeoService);
    titleService = TestBed.inject(Title);
    metaService = TestBed.inject(Meta);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  // Additional basic tests for SEO service
  it('should set title via updateSeo', () => {
    vi.spyOn(titleService, 'setTitle');
    service.updateSeo({ title: 'Test Title' });
    expect(titleService.setTitle).toHaveBeenCalledWith('Test Title | Sergii Mavrov');
  });

  it('should fall back to the base title when no title is provided', () => {
    vi.spyOn(titleService, 'setTitle');
    service.updateSeo({});
    expect(titleService.setTitle).toHaveBeenCalledWith(
      'Sergii Mavrov | Principal Software Engineer'
    );
  });

  it('should update description and Open Graph meta tags', () => {
    const updateSpy = vi.spyOn(metaService, 'updateTag');
    service.updateSeo({ title: 'X', description: 'Hello', image: '/img.png', url: '/page' });
    expect(updateSpy).toHaveBeenCalledWith({ name: 'description', content: 'Hello' });
    expect(updateSpy).toHaveBeenCalledWith({ property: 'og:title', content: 'X | Sergii Mavrov' });
    expect(updateSpy).toHaveBeenCalledWith({
      property: 'og:image',
      content: 'https://mavrov.de/img.png',
    });
  });

  it('should publish a JSON-LD schema', () => {
    const schema = { '@type': 'Person', name: 'Sergii Mavrov' };
    service.setJsonLd(schema);
    expect(service.jsonLdSchema$.value).toEqual(schema);
  });
});
