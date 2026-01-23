import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Language, LanguageService } from '../../services/language.service';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.css']
})
export class HeaderComponent {
  currentLang: Language = 'en';

  navItems = [
    { labelKey: 'NAV.ABOUT', href: '#about' },
    { labelKey: 'NAV.EXPERIENCE', href: '#experience' },
    { labelKey: 'NAV.SKILLS', href: '#skills' },
    { labelKey: 'NAV.EDUCATION', href: '#education' },
    { labelKey: 'NAV.RECOMMENDATIONS', href: '#recommendations' }
  ];

  constructor(private languageService: LanguageService) {
    this.languageService.currentLang$.subscribe(lang => this.currentLang = lang);
  }

  scrollTo(id: string, event: Event) {
    event.preventDefault();
    const element = document.querySelector(id);
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: "smooth"
      });
    }
  }

  switchLanguage(lang: Language): void {
    this.languageService.setLanguage(lang);
  }
}
