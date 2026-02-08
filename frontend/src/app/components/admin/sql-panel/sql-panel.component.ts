import { Component, inject } from '@angular/core';
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
  private apiUrl = `${environment.apiPrefix}/admin/sql/execute`;

  executeQuery() {
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
      },
      error: (err) => {
        console.error('SQL Execution error:', err);
        this.error = err.error?.detail || 'ADMIN.SQL_ERROR';
        this.loading = false;
      }
    });
  }
}
