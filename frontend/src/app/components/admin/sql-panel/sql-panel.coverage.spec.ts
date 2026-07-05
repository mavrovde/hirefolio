import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { SqlPanelComponent } from './sql-panel.component';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { environment } from '../../../../environments/environment';
import { MockTranslatePipe } from '../../../testing/mock-translate.pipe';
import { TranslatePipe } from '../../../pipes/translate.pipe';

describe('SqlPanelComponent branches', () => {
  let component: SqlPanelComponent;
  let fixture: ComponentFixture<SqlPanelComponent>;
  let httpMock: HttpTestingController;
  const url = `${environment.apiPrefix}/admin/sql/execute`;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SqlPanelComponent, HttpClientTestingModule, MockTranslatePipe],
    })
      .overrideComponent(SqlPanelComponent, {
        remove: { imports: [TranslatePipe] },
        add: { imports: [MockTranslatePipe] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SqlPanelComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => httpMock.verify());

  it('sets error and returns early when payload has an error field (lines 33-38)', () => {
    component.query = 'SELECT 1';
    component.executeQuery();
    httpMock.expectOne(url).flush({ error: 'boom' });
    expect(component.error).toBe('boom');
    expect(component.result).toBeNull();
    expect(component.loading).toBe(false);
  });

  it('maps columns/rows response shape (lines 44-46)', () => {
    component.query = 'SELECT * FROM t';
    component.executeQuery();
    httpMock.expectOne(url).flush({ columns: ['a', 'b'], rows: [{ a: 1, b: 2 }] });
    expect(component.columns).toEqual(['a', 'b']);
    expect(component.result).toEqual([{ a: 1, b: 2 }]);
    expect(component.loading).toBe(false);
  });

  it('handles an empty array response (line 53)', () => {
    component.query = 'SELECT * FROM empty';
    component.executeQuery();
    httpMock.expectOne(url).flush([]);
    expect(component.result).toEqual([]);
    expect(component.columns).toEqual([]);
  });

  it('handles an object with rows but no columns (line 47 else-if false branch)', () => {
    component.query = 'SELECT 1';
    component.executeQuery();
    // {rows} object: result = data.rows; not columns; data itself is not an Array
    httpMock.expectOne(url).flush({ rows: [{ a: 1 }] });
    expect(component.result).toEqual([{ a: 1 }]);
    expect(component.loading).toBe(false);
  });

  it('falls back to generic error message when detail missing', () => {
    component.query = 'BAD';
    component.executeQuery();
    httpMock.expectOne(url).flush({}, { status: 500, statusText: 'Server Error' });
    expect(component.error).toBe('ADMIN.SQL_ERROR');
    expect(component.loading).toBe(false);
  });
});
