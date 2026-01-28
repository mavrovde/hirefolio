import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminCvService, CvRequestSummary, CvVersion } from '../../../services/admin-cv.service';

@Component({
    selector: 'app-cv-manager',
    standalone: true,
    imports: [CommonModule, ReactiveFormsModule],
    template: `
    <div class="cv-manager-container">
      <h2>CV Management</h2>
      
      <div class="tabs">
        <button [class.active]="activeTab === 'requests'" (click)="activeTab = 'requests'">Requests Report</button>
        <button [class.active]="activeTab === 'versions'" (click)="activeTab = 'versions'">Upload & Versions</button>
      </div>

      <!-- Requests Tab -->
      <div *ngIf="activeTab === 'requests'" class="tab-content">
        <h3>Download Requests</h3>
        
        <div class="table-container">
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
                <td>{{ req.created_at | date:'short' }}</td>
                <td>{{ req.name }}</td>
                <td>{{ req.email }}</td>
                <td>{{ req.company || '-' }}</td>
                <td>{{ req.cv_version || '-' }}</td>
                <td class="message-cell" [title]="req.message">{{ req.message || '-' }}</td>
              </tr>
              <tr *ngIf="requests.length === 0">
                <td colspan="6">No requests found.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Versions/Upload Tab -->
      <div *ngIf="activeTab === 'versions'" class="tab-content">
        <div class="upload-section">
          <h3>Upload New Version</h3>
          <form [formGroup]="uploadForm" (ngSubmit)="onUpload()">
            <div class="form-group">
              <label>Version Name (e.g. v1.2)</label>
              <input type="text" formControlName="version" placeholder="v1.x">
            </div>
            
            <div class="form-group">
              <label>PDF File</label>
              <input type="file" (change)="onFileSelected($event)" accept=".pdf">
            </div>

            <button type="submit" [disabled]="uploadForm.invalid || !selectedFile || uploading">
              {{ uploading ? 'Uploading...' : 'Upload New Version' }}
            </button>
            
            <div *ngIf="uploadError" class="error">{{ uploadError }}</div>
            <div *ngIf="uploadSuccess" class="success">CV Uploaded Successfully!</div>
          </form>
        </div>

        <div class="versions-list">
          <h3>Version History</h3>
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Filename</th>
                <th>Uploaded At</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let ver of versions">
                <td>{{ ver.version }}</td>
                <td>{{ ver.filename }}</td>
                <td>{{ ver.created_at | date:'short' }}</td>
                <td>
                  <span class="badge" [class.active-badge]="ver.is_active">
                    {{ ver.is_active ? 'ACTIVE' : 'Inactive' }}
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
    .cv-manager-container { padding: 20px; }
    .tabs { margin-bottom: 20px; border-bottom: 1px solid #ddd; }
    .tabs button {
      padding: 10px 20px;
      margin-right: 5px;
      border: none;
      background: none;
      cursor: pointer;
      font-size: 1rem;
    }
    .tabs button.active {
      border-bottom: 2px solid #007bff;
      font-weight: bold;
      color: #007bff;
    }
    .table-container { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }
    th { background-color: #f9f9f9; }
    .message-cell { max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    
    .upload-section { background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
    .form-group input[type="text"] { width: 100%; padding: 8px; }
    button[type="submit"] {
      background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;
    }
    button[type="submit"]:disabled { background: #ccc; }
    .error { color: red; margin-top: 10px; }
    .success { color: green; margin-top: 10px; }
    
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; background: #eee; }
    .active-badge { background: #28a745; color: white; }
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
