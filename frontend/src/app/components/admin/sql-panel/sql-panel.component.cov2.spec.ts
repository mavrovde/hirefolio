import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SqlPanelComponent } from './sql-panel.component';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TranslatePipe } from '../../../pipes/translate.pipe';
import { MockTranslatePipe } from '../../../testing/mock-translate.pipe';
import { environment } from '../../../../environments/environment';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('SqlPanelComponent cov2', () => {
    let component: SqlPanelComponent;
    let fixture: ComponentFixture<SqlPanelComponent>;
    let httpMock: HttpTestingController;

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [SqlPanelComponent, HttpClientTestingModule, MockTranslatePipe],
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
        vi.restoreAllMocks();
    });

    // Line 72 false branch: Content-Disposition present but regex captures an empty filename
    it('should keep default filename when Content-Disposition has empty filename', () => {
        vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:url');
        vi.spyOn(window.URL, 'revokeObjectURL');
        vi.spyOn(HTMLAnchorElement.prototype, 'click');

        component.backup();

        const req = httpMock.expectOne(`${environment.apiPrefix}/admin/sql/backup`);
        const mockBlob = new Blob(['SQL DUMP'], { type: 'application/sql' });
        req.flush(mockBlob, {
            // filename="" -> matches[1] is empty string (falsy), so default retained
            headers: { 'Content-Disposition': 'attachment; filename=""' },
            status: 200,
            statusText: 'OK'
        });

        expect(component.result?.[0]?.filename).toBe('backup.sql');
    });

    // Lines 89/91 false branch: err.error is NOT a Blob, so fall through to message
    it('should use fallback message when backup error is not a Blob', () => {
        component.backup();
        const req = httpMock.expectOne(`${environment.apiPrefix}/admin/sql/backup`);
        // A network-style error: err.error is a ProgressEvent (not a Blob),
        // and has no .detail, so the code falls through to err.message.
        req.error(new ProgressEvent('error'));

        expect(component.error).toContain('Backup failed:');
        expect(component.error).not.toContain('Server error (check backend logs)');
        expect(component.result?.[0]?.status).toBe('❌ Backup failed');
        expect(component.loading).toBe(false);
    });

    // Line 103 false branch: no file selected -> restore not invoked
    it('should not restore when no file is selected', () => {
        const restoreSpy = vi.spyOn(component, 'restore');
        const event = { target: { files: [] } };

        component.onFileSelected(event);

        expect(restoreSpy).not.toHaveBeenCalled();
        httpMock.expectNone(`${environment.apiPrefix}/admin/sql/restore`);
    });
});
