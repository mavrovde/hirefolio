import { Component, Input, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Profile } from '../../services/profile.service';

@Component({
  selector: 'app-hero',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './hero.component.html',
  styleUrls: ['./hero.component.css'],
})
export class HeroComponent {
  @Input() profile: Profile | null = null;

  constructor(@Inject(PLATFORM_ID) private platformId: Object) { }

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
