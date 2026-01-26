import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { StatsService, SystemStats } from '../../../services/stats.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css'],
})
export class DashboardComponent implements OnInit {
  stats: SystemStats | null = null;
  loading = true;
  error: string | null = null;

  constructor(
    private statsService: StatsService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    console.log('Dashboard: loadStats called');
    this.loading = true;
    this.error = null;
    this.statsService.getStats().subscribe({
      next: (data) => {
        console.log('Dashboard: Stats received', data);
        this.stats = data;
        this.loading = false;
        this.cdr.detectChanges(); // Force UI update
      },
      error: (error) => {
        console.error('Dashboard: Failed to load stats:', error);
        this.error = 'Failed to load dashboard statistics';
        this.loading = false;
        this.cdr.detectChanges(); // Force UI update
      },
      complete: () => {
        console.log('Dashboard: Stats request completed');
      },
    });
  }

  getLanguages(): string[] {
    return this.stats?.posts.by_language ? Object.keys(this.stats.posts.by_language) : [];
  }
}
