import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SqlPanelComponent } from './sql-panel.component';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { environment } from '../../../../environments/environment';
import { MockTranslatePipe } from '../../../testing/mock-translate.pipe';
import { TranslatePipe } from '../../../pipes/translate.pipe';

describe('SqlPanelComponent', () => {
    let component: SqlPanelComponent;
    let fixture: ComponentFixture<SqlPanelComponent>;
    let httpMock: HttpTestingController;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [SqlPanelComponent, HttpClientTestingModule, MockTranslatePipe]
        })
            .overrideComponent(SqlPanelComponent, {
                remove: { imports: [TranslatePipe] },
                add: { imports: [MockTranslatePipe] }
            })
            .compileComponents();

        fixture = TestBed.createComponent(SqlPanelComponent);
        component = fixture.componentInstance;
        httpMock = TestBed.inject(HttpTestingController);
        fixture.detectChanges();
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should execute query and display results', () => {
        const mockData = [{ id: 1, name: 'Test' }];
        component.query = 'SELECT * FROM test';
        component.executeQuery();

        const req = httpMock.expectOne(`${environment.apiPrefix}/admin/sql/execute`);
        expect(req.request.method).toBe('POST');
        req.flush(mockData);

        expect(component.result).toEqual(mockData);
        expect(component.columns).toEqual(['id', 'name']);
        expect(component.loading).toBe(false);
    });

    it('should handle error', () => {
        component.query = 'INVALID QUERY';
        component.executeQuery();

        const req = httpMock.expectOne(`${environment.apiPrefix}/admin/sql/execute`);
        req.flush({ detail: 'Syntax Error' }, { status: 400, statusText: 'Bad Request' });

        expect(component.error).toBe('Syntax Error');
        expect(component.loading).toBe(false);
    });
});
