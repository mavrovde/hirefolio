import { Component, Input, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Observable, map } from 'rxjs';
import { TranslatePipe } from '@mavrov/shared';
import { Profile } from '../../services/profile.service';
import { SiteConfigService } from '../../services/site-config.service';

@Component({
  selector: 'app-hero',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './hero.component.html',
  styleUrls: ['./hero.component.css'],
})
export class HeroComponent {
  @Input() profile: Profile | null = null;

  /** Job-search state (#271), rendered via the async pipe (rule 5 — the app
   *  is zoneless; a stream keeps the repaint automatic). The i18n key is
   *  derived here so the template stays dumb. */
  readonly availability$: Observable<{ state: string; key: string }>;

  constructor(
    @Inject(PLATFORM_ID) private platformId: Object,
    siteConfigService: SiteConfigService,
  ) {
    this.availability$ = siteConfigService.config$.pipe(
      map((config) => ({
        state: config.availability,
        key: `AVAILABILITY.${config.availability.toUpperCase()}`,
      })),
    );
  }

  scrollTo(id: string, event: Event) {
    event.preventDefault();

    if (!isPlatformBrowser(this.platformId)) {
      return;
    }

    const element = document.querySelector(id);
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth',
      });
    }
  }
}
