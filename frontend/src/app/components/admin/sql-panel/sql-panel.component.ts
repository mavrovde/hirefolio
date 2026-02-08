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
    this.loading = true;
    this.error = null;
    this.result = null;

    this.http.post<any>(this.apiUrl, { query: this.query }).subscribe({
      next: (data) => {
        console.log('SQL Check Result:', data); // DEBUG
        if (data.error) {
          this.error = data.error;
          this.loading = false;
          this.cdr.detectChanges();
          return;
        }
        this.result = data.rows || data; // Backend returns {columns, rows} or just list?
        // Wait, app/api/admin_sql.py returns {"columns": ..., "rows": ...}
        // Let's check admin_sql.py again.
        // It says: return {"columns": keys, "rows": [dict(row) for row in result]}

        if (data.columns) {
          this.columns = data.columns;
          this.result = data.rows;
        } else if (Array.isArray(data)) {
          // Fallback if it returns just array
          this.result = data;
          if (data.length > 0) {
            this.columns = Object.keys(data[0]);
          } else {
            this.columns = [];
          }
        }
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('SQL Execution error:', err);
        this.error = err.error?.detail || 'ADMIN.SQL_ERROR';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }
}
