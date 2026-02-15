import { Component, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';
import { TranslatePipe } from '../../../pipes/translate.pipe';

@Component({
  selector: 'app-sql-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './sql-panel.component.html',
  styles: []
})
export class SqlPanelComponent {
  query = '';
  result: any[] | null = null;
  columns: string[] = [];
  loading = false;
  error: string | null = null;
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  private apiUrl = `${environment.apiPrefix}/admin/sql/execute`;

  executeQuery() {
    if (!this.query.trim()) return;

    this.loading = true;
    this.error = null;
    this.result = null;

    this.http.post<any[]>(this.apiUrl, { query: this.query }).subscribe({
      next: (data) => {
        this.result = data;
        if (data && data.length > 0) {
          this.columns = Object.keys(data[0]);
        } else {
          this.columns = [];
        }
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('SQL Error:', err);
        this.error = err.error?.detail || 'Execution failed';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  backup() {
    this.loading = true;
    this.error = null;
    this.result = null;

    this.http.get(`${environment.apiPrefix}/admin/sql/backup`, {
      responseType: 'blob',
      observe: 'response'
    }).subscribe({
      next: (response) => {
        const blob = new Blob([response.body!], { type: 'application/sql' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;

        // Extract filename from header or default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'backup.sql';
        if (contentDisposition) {
          const matches = /filename="?([^"]*)"?/.exec(contentDisposition);
          if (matches && matches[1]) {
            filename = matches[1];
          }
        }

        link.download = filename;
        link.click();
        window.URL.revokeObjectURL(url);
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Backup error:', err);
        this.error = 'Failed to download backup';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  onFileSelected(event: any) {
    const file: File = event.target.files[0];
    if (file) {
      this.restore(file);
    }
  }

  restore(file: File) {
    if (!confirm('WARNING: This will overwrite the current database. Are you sure?')) {
      return;
    }

    this.loading = true;
    this.error = null;
    this.result = null;

    const formData = new FormData();
    formData.append('file', file);

    this.http.post<any>(`${environment.apiPrefix}/admin/sql/restore`, formData).subscribe({
      next: (data) => {
        this.result = [{ message: data.message, output: data.output }];
        this.columns = ['message', 'output'];
        this.loading = false;
        this.cdr.detectChanges();
        alert('Database restored successfully!');
      },
      error: (err) => {
        console.error('Restore error:', err);
        this.error = err.error?.detail || 'Restore failed';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }
}
