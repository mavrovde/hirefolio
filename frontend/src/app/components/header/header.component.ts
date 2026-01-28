import { Component, Inject, PLATFORM_ID } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { Language, LanguageService } from '../../services/language.service';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.css'],
})
export class HeaderComponent {
  currentLang: Language = 'en';

  navItems = [
    { labelKey: 'NAV.ABOUT', href: '#about' },
    { labelKey: 'NAV.EXPERIENCE', href: '#experience' },
    { labelKey: 'NAV.SKILLS', href: '#skills' },
    { labelKey: 'NAV.EDUCATION', href: '#education' },
    { labelKey: 'NAV.CV', href: '/cv' },
    { labelKey: 'NAV.BLOG', href: '#blog' },
    { labelKey: 'NAV.CONTACT', href: '#contact' },
    { labelKey: 'NAV.LLM', href: '/llm' },
  ];

  constructor(
    private languageService: LanguageService,
    private router: Router,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    this.languageService.currentLang$.subscribe((lang) => (this.currentLang = lang));
  }

  scrollTo(href: string, event: Event) {
    event.preventDefault();
    if (href.startsWith('/')) {
      this.router.navigate([href]);
      return;
    }

    if (!isPlatformBrowser(this.platformId)) {
      this.router.navigate(['/'], { fragment: href.substring(1) });
      return;
    }

    const element = document.querySelector(href);
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth',
      });
    } else {
      // If element not found, navigate to home with the fragment
      this.router.navigate(['/'], { fragment: href.substring(1) });
    }
  }

  switchLanguage(lang: Language): void {
    this.languageService.setLanguage(lang);
  }
}
