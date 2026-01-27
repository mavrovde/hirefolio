import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
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
    // { labelKey: 'NAV.RECOMMENDATIONS', href: '#recommendations' },
    { labelKey: 'NAV.BLOG', href: '#blog' },
    { labelKey: 'NAV.LLM', href: '/llm' },
  ];

  constructor(private languageService: LanguageService, private router: Router) {
    this.languageService.currentLang$.subscribe((lang) => (this.currentLang = lang));
  }

  scrollTo(href: string, event: Event) {
    event.preventDefault();
    if (href.startsWith('/')) {
      this.router.navigate([href]);
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
    }
  }

  switchLanguage(lang: Language): void {
    this.languageService.setLanguage(lang);
  }
}
