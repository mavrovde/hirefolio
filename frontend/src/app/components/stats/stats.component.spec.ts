import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SystemStatsComponent } from './stats.component';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';
import { PLATFORM_ID } from '@angular/core';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('SystemStatsComponent - Browser', () => {
  let component: SystemStatsComponent;
  let fixture: ComponentFixture<SystemStatsComponent>;

  beforeEach(async () => {
    vi.useFakeTimers();
    await TestBed.configureTestingModule({
      imports: [SystemStatsComponent],
      providers: [{ provide: PLATFORM_ID, useValue: 'browser' }],
    })
      .overrideComponent(SystemStatsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SystemStatsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should start uptime counter in browser', () => {
    // Initial uptime
    expect(component.uptime).toBe('00:00:00');

    // Fast forward 2 seconds
    vi.advanceTimersByTime(2000);
    expect(component.uptime).toBe('00:00:02');
  });

  it('should simulate memory fluctuation in browser', () => {
    vi.advanceTimersByTime(5001); // Interval is 5000ms
    // Since it's random, we just check it's within bounds [20, 60]
    expect(component.memoryUsage).toBeGreaterThanOrEqual(20);
    expect(component.memoryUsage).toBeLessThanOrEqual(60);
  });

  it('should pad single digits correctly', () => {
    const result = (component as any).formatTime(1000);
    expect(result).toBe('00:00:01');

    const result2 = (component as any).formatTime(3661000); // 1h 1m 1s
    expect(result2).toBe('01:01:01');

    const result3 = (component as any).formatTime(36610000); // 10h 10m 10s
    expect(result3).toBe('10:10:10');
  });

  it('should clear interval on destroy', () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    component.ngOnDestroy();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});

describe('SystemStatsComponent - Non-Browser', () => {
  let component: SystemStatsComponent;
  let fixture: ComponentFixture<SystemStatsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SystemStatsComponent],
      providers: [{ provide: PLATFORM_ID, useValue: 'server' }],
    })
      .overrideComponent(SystemStatsComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SystemStatsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should not start uptime counter on server', () => {
    expect((component as any).intervalId).toBeUndefined();

    // Explicitly call private method to test the safe guard
    (component as any).simulateMemoryFluctuation();
    // No side effect expected, just line coverage
  });
});
