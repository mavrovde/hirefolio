import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';

import { HeaderComponent } from '../header/header.component';
import { HeroComponent } from '../hero/hero.component';
import { AboutComponent } from '../about/about.component';
import { ExperienceComponent } from '../experience/experience.component';
import { SkillsComponent } from '../skills/skills.component';
import { EducationComponent } from '../education/education.component';
import { RecommendationsComponent } from '../recommendations/recommendations.component';
import { BlogComponent } from '../blog/blog.component';
import { ContactComponent } from '../contact/contact.component';
import { SystemStatsComponent } from '../stats/stats.component';

import { ProfileService, Profile } from '../../services/profile.service';
import { GoogleAnalyticsService } from '../../services/analytics.service';

@Component({
    selector: 'app-home',
    standalone: true,
    imports: [
        CommonModule,
        HeaderComponent,
        HeroComponent,
        AboutComponent,
        ExperienceComponent,
        SkillsComponent,
        EducationComponent,
        RecommendationsComponent,
        BlogComponent,
        ContactComponent,
        SystemStatsComponent
    ],
    template: `
    <div class="bg-black min-h-screen text-primary selection:bg-primary selection:text-black font-mono">
      <app-header></app-header>
      
      <main *ngIf="profile$ | async as profile" class="pb-16">
        <app-hero [profile]="profile"></app-hero>
        <app-about [profile]="profile"></app-about>
        <app-experience [profile]="profile"></app-experience>
        <app-skills [profile]="profile"></app-skills>
        <app-education [profile]="profile"></app-education>
        <app-recommendations [profile]="profile"></app-recommendations>
        <app-blog></app-blog>
        <app-contact [profile]="profile"></app-contact>
      </main>

      <app-system-stats></app-system-stats>

      <footer class="bg-black py-8 text-center text-secondary text-sm border-t border-terminal">
        <p>&copy; {{ currentYear }} Sergii Mavrov. All rights reserved.</p>
      </footer>
    </div>
  `
})
export class HomeComponent implements OnInit {
    profile$: Observable<Profile> | null = null;
    currentYear = new Date().getFullYear();

    constructor(
        private profileService: ProfileService,
        private analyticsService: GoogleAnalyticsService
    ) { }

    ngOnInit() {
        this.profile$ = this.profileService.getProfile();
        this.analyticsService.initializeGoogleAnalytics();
        this.analyticsService.trackPageViews();
    }
}
