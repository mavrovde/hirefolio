import { Component, Inject, PLATFORM_ID, OnInit } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { Language, LanguageService } from '../../services/language.service';
import { YearsService } from '../../services/years.service';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, TranslatePipe, RouterLink, RouterLinkActive],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.css'],
})
export class HeaderComponent implements OnInit {
  currentLang: Language = 'en';
  years: number[] = [];
  selectedYearIndex: number = 0;

  navItems = [
    { labelKey: 'NAV.BLOG', href: '#blog' },
    { labelKey: 'NAV.ABOUT', href: '#about' },
    { labelKey: 'NAV.EXPERIENCE', href: '#experience' },
    { labelKey: 'NAV.SKILLS', href: '#skills' },
    { labelKey: 'NAV.EDUCATION', href: '#education' },
    { labelKey: 'NAV.CV', href: '/cv' },
    { labelKey: 'NAV.CONTACT', href: '#contact' },
    { labelKey: 'NAV.LLM', href: '/llm' },
  ];

  constructor(
    private languageService: LanguageService,
    private yearsService: YearsService,
    private router: Router,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    this.languageService.currentLang$.subscribe((lang) => (this.currentLang = lang));
  }

  ngOnInit(): void {
    this.yearsService.getYears().subscribe((years) => {
      // Reverse to ascending order: oldest (left) → newest (right)
      this.years = [...years].reverse();
      this.selectedYearIndex = this.years.length - 1; // default to newest
    });
  }

  absDiff(a: number, b: number): number {
    return Math.abs(a - b);
  }

  prevYear(): void {
    if (this.selectedYearIndex > 0) {
      this.selectedYearIndex--;
      this.scrollToYear(this.years[this.selectedYearIndex]);
    }
  }

  nextYear(): void {
    if (this.selectedYearIndex < this.years.length - 1) {
      this.selectedYearIndex++;
      this.scrollToYear(this.years[this.selectedYearIndex]);
    }
  }

  selectYearByIndex(index: number): void {
    this.selectedYearIndex = index;
    this.scrollToYear(this.years[index]);
  }

  scrollToYear(year: number): void {
    if (!isPlatformBrowser(this.platformId)) {
      this.router.navigate(['/'], { fragment: 'experience' });
      return;
    }

    const currentUrl = this.router.url.split('#')[0].split('?')[0];
    if (currentUrl !== '/' && currentUrl !== '') {
      this.router.navigate(['/'], { fragment: 'experience' }).then(() => {
        setTimeout(() => this._scrollToYearElement(year), 500);
      });
    } else {
      this._scrollToYearElement(year);
    }
  }

  private _scrollToYearElement(year: number): void {
    const element = document.querySelector(`[data-year="${year}"]`);
    if (element) {
      const headerOffset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;
      window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
    } else {
      const experienceSection = document.querySelector('#experience');
      if (experienceSection) {
        const headerOffset = 80;
        const elementPosition = experienceSection.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.scrollY - headerOffset;
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      }
    }
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
      window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
    } else {
      this.router.navigate(['/'], { fragment: href.substring(1) });
    }
  }

  switchLanguage(lang: Language): void {
    this.languageService.setLanguage(lang);
  }
}
