import { Component, OnInit, OnDestroy, PLATFORM_ID, Inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
    selector: 'app-system-stats',
    standalone: true,
    imports: [CommonModule, TranslatePipe],
    templateUrl: './stats.component.html',
    styleUrls: ['./stats.component.css']
})
export class SystemStatsComponent implements OnInit, OnDestroy {
    uptime: string = '00:00:00';
    private startTime: number = Date.now();
    private intervalId: any;
    visitorIp: string = '127.0.0.1'; // Mock for now
    memoryUsage: number = 24; // Mock MB usage

    constructor(@Inject(PLATFORM_ID) private platformId: Object) { }

    ngOnInit(): void {
        if (isPlatformBrowser(this.platformId)) {
            this.startUptimeCounter();
            this.simulateMemoryFluctuation();
        }
    }

    ngOnDestroy(): void {
        if (this.intervalId) clearInterval(this.intervalId);
    }

    private startUptimeCounter(): void {
        this.intervalId = setInterval(() => {
            const now = Date.now();
            const diff = now - this.startTime;
            this.uptime = this.formatTime(diff);
        }, 1000);
    }

    private formatTime(ms: number): string {
        const seconds = Math.floor((ms / 1000) % 60);
        const minutes = Math.floor((ms / (1000 * 60)) % 60);
        const hours = Math.floor((ms / (1000 * 60 * 60)) % 24);

        return `${this.pad(hours)}:${this.pad(minutes)}:${this.pad(seconds)}`;
    }

    private pad(num: number): string {
        return num < 10 ? '0' + num : num.toString();
    }

    private simulateMemoryFluctuation(): void {
        if (isPlatformBrowser(this.platformId)) {
            setInterval(() => {
                // Fluctuate between 20MB and 60MB
                this.memoryUsage = Math.floor(Math.random() * (60 - 20 + 1) + 20);
            }, 5000);
        }
    }
}
