import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SystemStatsComponent } from './stats.component';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../testing/mock-translate.pipe';

describe('SystemStatsComponent', () => {
  let component: SystemStatsComponent;
  let fixture: ComponentFixture<SystemStatsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SystemStatsComponent],
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

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should have mock uptime', () => {
    expect(component.uptime).toBe('00:00:00');
  });

  it('should have visitor IP', () => {
    expect(component.visitorIp).toBe('127.0.0.1');
  });
});
