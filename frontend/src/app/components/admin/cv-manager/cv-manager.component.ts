import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminCvService, CvRequestSummary, CvVersion } from '../../../services/admin-cv.service';

@Component({
  selector: 'app-cv-manager',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="cv-manager">
      <div class="header">
        <h1 class="page-title">> CV Management</h1>
      </div>

      <div class="tabs">
        <button 
          [class.active]="activeTab === 'requests'"
          (click)="activeTab = 'requests'"
          class="tab-btn"
        >
          > REQUESTS_REPORT.sh
        </button>
        <button
          [class.active]="activeTab === 'versions'"
          (click)="activeTab = 'versions'"
          class="tab-btn"
        >
          > VERSION_CONTROL.sys
        </button>
      </div>

      <!-- Requests Tab -->
      <div *ngIf="activeTab === 'requests'" class="tab-content fade-in">
        <h3 class="section-title">> Download Requests</h3>

        <div class="table-container posts-table">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Name</th>
                <th>Email</th>
                <th>Company</th>
                <th>Version</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let req of requests">
                <td class="date-cell">{{ req.created_at | date: 'yyyy-MM-dd HH:mm' }}</td>
                <td class="title-cell">{{ req.name }}</td>
                <td class="slug-cell">{{ req.email }}</td>
                <td class="lang-cell">{{ req.company || '-' }}</td>
                <td class="id-cell">{{ req.cv_version || '-' }}</td>
                <td class="message-cell" [title]="req.message">{{ req.message || '-' }}</td>
              </tr>
              <tr *ngIf="requests.length === 0">
                <td colspan="6" class="empty-row">> No records in database.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Versions / Upload Tab -->
      <div *ngIf="activeTab === 'versions'" class="tab-content fade-in">
        <div class="upload-section terminal-box">
          <h3 class="section-title">> INITIALIZE_UPLOAD.bin</h3>
          <form [formGroup]="uploadForm" (ngSubmit)="onUpload()" class="terminal-form">
            <div class="form-group">
              <label>VERSION_ID: </label>
              <input type="text" formControlName="version" placeholder="e.g. v1.2">
            </div>

            <div class="form-group">
              <label>FILE_PATH: </label>
              <input type="file" (change)="onFileSelected($event)" accept=".pdf" class="file-input">
            </div>

            <div class="form-actions">
              <button type="submit" [disabled]="uploadForm.invalid || !selectedFile || uploading" class="btn-primary">
                {{ uploading ? '[ PROCESSING... ]' : '[ EXECUTE_UPLOAD ]' }}
              </button>
            </div>

            <div *ngIf="uploadError" class="error-text">> ERROR: {{ uploadError }}</div>
            <div *ngIf="uploadSuccess" class="success-text">> SUCCESS: CV_UPLOAD_COMPLETE</div>
          </form>
        </div>

        <div class="versions-list posts-table">
          <h3 class="section-title">> VERSION_HISTORY.log</h3>
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Filename</th>
                <th>Timestamp</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let ver of versions">
                <td class="title-cell">{{ ver.version }}</td>
                <td class="slug-cell">{{ ver.filename }}</td>
                <td class="date-cell">{{ ver.created_at | date: 'yyyy-MM-dd HH:mm' }}</td>
                <td class="status-cell">
                  <span [class]="ver.is_active ? 'status-published' : 'status-draft'">
                    {{ ver.is_active ? '✓ ACTIVE' : '○ INACTIVE' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .cv-manager { color: #0f0; }
    .header { margin-bottom: 30px; }
    .page-title { font-size: 32px; color: var(--primary-color, #0ea5e9); margin: 0; }
    
    .tabs { display: flex; gap: 10px; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .tab-btn {
      padding: 10px 20px;
      background: transparent;
      border: 1px solid #333;
      color: #666;
      cursor: pointer;
      font-family: var(--font-mono, 'Courier Prime', monospace);
      transition: all 0.3s;
    }
    .tab-btn:hover { border-color: var(--primary-color, #0ea5e9); color: var(--primary-color, #0ea5e9); }
    .tab-btn.active {
      border-color: var(--primary-color, #0ea5e9);
      color: var(--primary-color, #0ea5e9);
      background: rgb(14 165 233 / 10%);
    }

    .section-title { font-size: 1.2rem; color: #0f0; margin: 20px 0; }
    
    .posts-table { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; border: 2px solid var(--primary-color, #0ea5e9); }
    thead { background: rgb(14 165 233 / 10%); }
    th { padding: 15px; text-align: left; color: var(--primary-color, #0ea5e9); border-bottom: 2px solid var(--primary-color, #0ea5e9); }
    td { padding: 15px; border-bottom: 1px solid #333; }
    tr:hover { background: rgb(14 165 233 / 5%); }

    .date-cell { color: #666; font-family: var(--font-mono); font-size: 0.9rem; }
    .title-cell { color: #fff; font-weight: 500; }
    .slug-cell { color: var(--primary-color, #0ea5e9); font-family: var(--font-mono); }
    .lang-cell { color: #f0f; font-family: var(--font-mono); }
    .id-cell { color: #666; font-family: var(--font-mono); }
    .message-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #888; }
    .empty-row { text-align: center; padding: 40px; color: #666; font-style: italic; }

    .status-published { color: #0f0; }
    .status-draft { color: #f90; }

    .terminal-box {
      border: 1px solid #333;
      padding: 20px;
      margin-bottom: 30px;
      background: rgba(0, 0, 0, 0.2);
    }

    .terminal-form { display: flex; flex-direction: column; gap: 20px; max-width: 500px; }
    .form-group { display: flex; align-items: center; gap: 10px; }
    .form-group label { color: #0f0; min-width: 120px; font-family: var(--font-mono); }
    .form-group input[type="text"] {
      flex: 1;
      background: transparent;
      border: 1px solid #333;
      color: #fff;
      padding: 8px;
      outline: none;
    }
    .form-group input[type="text"]:focus { border-color: var(--primary-color, #0ea5e9); }
    
    .file-input { color: #666; }

    .btn-primary {
      display: inline-block;
      padding: 12px 24px;
      background: transparent;
      border: 2px solid var(--primary-color, #0ea5e9);
      color: var(--primary-color, #0ea5e9);
      text-decoration: none;
      transition: all 0.3s;
      cursor: pointer;
      font-family: var(--font-mono);
      font-weight: bold;
    }
    .btn-primary:hover:not(:disabled) { background: var(--primary-color, #0ea5e9); color: #000; }
    .btn-primary:disabled { border-color: #333; color: #333; cursor: not-allowed; }

    .error-text { color: #f00; margin-top: 10px; font-family: var(--font-mono); }
    .success-text { color: #0f0; margin-top: 10px; font-family: var(--font-mono); }

    .fade-in { animation: fadeIn 0.3s ease-in; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  `]
})
export class CvManagerComponent implements OnInit {
  activeTab: 'requests' | 'versions' = 'requests';
  requests: CvRequestSummary[] = [];
  versions: CvVersion[] = [];

  uploadForm: FormGroup;
  selectedFile: File | null = null;
  uploading = false;
  uploadError = '';
  uploadSuccess = false;

  constructor(
    private cvService: AdminCvService,
    private fb: FormBuilder
  ) {
    this.uploadForm = this.fb.group({
      version: ['', Validators.required]
    });
  }

  ngOnInit() {
    this.loadRequests();
    this.loadVersions();
  }

  loadRequests() {
    this.cvService.getRequests().subscribe({
      next: (data) => this.requests = data,
      error: (err) => console.error('Failed to load requests', err)
    });
  }

  loadVersions() {
    this.cvService.getVersions().subscribe({
      next: (data) => this.versions = data,
      error: (err) => console.error('Failed to load versions', err)
    });
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0] || null;
  }

  onUpload() {
    if (!this.selectedFile || this.uploadForm.invalid) return;

    this.uploading = true;
    this.uploadError = '';
    this.uploadSuccess = false;

    this.cvService.uploadCv(this.selectedFile, this.uploadForm.get('version')?.value)
      .subscribe({
        next: () => {
          this.uploading = false;
          this.uploadSuccess = true;
          this.uploadForm.reset();
          this.selectedFile = null;
          this.loadVersions(); // Refresh list
        },
        error: (err) => {
          this.uploading = false;
          this.uploadError = err.error?.detail || 'Upload failed';
        }
      });
  }
}
