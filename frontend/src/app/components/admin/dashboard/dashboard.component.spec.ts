import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DashboardComponent } from './dashboard.component';
import { StatsService, SystemStats } from '../../../services/stats.service';
import { of, throwError } from 'rxjs';
import { RouterTestingModule } from '@angular/router/testing';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

describe('DashboardComponent', () => {
    let component: DashboardComponent;
    let fixture: ComponentFixture<DashboardComponent>;
    let statsServiceSpy: { getStats: Mock };

    const mockStats: SystemStats = {
        posts: {
            total: 10,
            published: 8,
            drafts: 2,
            by_language: { en: 5, de: 5 }
        },
        users: 1,
        subscribers: 0,
        visitors: '0',
        top_tags: { 'angular': 5 },
        recent_posts: [],
        system_health: {
            database: true,
            ai_service: true
        }
    };

    beforeEach(async () => {
        statsServiceSpy = { getStats: vi.fn() };

        await TestBed.configureTestingModule({
            imports: [DashboardComponent, RouterTestingModule],
            providers: [
                { provide: StatsService, useValue: statsServiceSpy }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(DashboardComponent);
        component = fixture.componentInstance;
    });

    it('should create', () => {
        statsServiceSpy.getStats.mockReturnValue(of(mockStats));
        fixture.detectChanges();
        expect(component).toBeTruthy();
    });

    it('should load stats correctly', () => {
        statsServiceSpy.getStats.mockReturnValue(of(mockStats));
        fixture.detectChanges();

        expect(component.stats).toEqual(mockStats);
        expect(component.loading).toBe(false);
        expect(component.error).toBeNull();
    });

    it('should handle error when loading stats', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });
        statsServiceSpy.getStats.mockReturnValue(throwError(() => new Error('Network error')));
        fixture.detectChanges();

        expect(component.stats).toBeNull();
        expect(component.loading).toBe(false);
        expect(component.error).toContain('Failed to load');
        expect(consoleSpy).toHaveBeenCalledWith('Dashboard: Failed to load stats:', expect.any(Error));

        consoleSpy.mockRestore();
    });
});
