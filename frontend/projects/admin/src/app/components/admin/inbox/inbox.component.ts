import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  InteractionsService,
  Interaction,
  INTERACTION_STATUSES,
  INTERACTION_SOURCES,
} from '../../../services/interactions.service';

/**
 * Unified recruiter inbox (#69): every inbound interaction — contact form,
 * CV request, (later) bookings — in one list with a status workflow.
 */
@Component({
  selector: 'app-inbox',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './inbox.component.html',
})
export class InboxComponent implements OnInit {
  readonly statuses = INTERACTION_STATUSES;
  readonly sources = INTERACTION_SOURCES;

  items: Interaction[] = [];
  total = 0;
  page = 1;
  pages = 1;
  pageSize = 20;

  statusFilter = '';
  sourceFilter = '';

  loading = false;
  error: string | null = null;
  expandedId: string | null = null;

  constructor(
    private interactionsService: InteractionsService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading = true;
    this.error = null;
    this.interactionsService
      .list({
        status: this.statusFilter || undefined,
        source: this.sourceFilter || undefined,
        page: this.page,
        pageSize: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.items = res.items;
          this.total = res.total;
          this.pages = res.pages;
          this.loading = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error('Error loading inbox:', err);
          this.error = 'Failed to load the inbox';
          this.loading = false;
          this.cdr.detectChanges();
        },
      });
  }

  onFilterChange() {
    this.page = 1;
    this.load();
  }

  goToPage(page: number) {
    if (page < 1 || page > this.pages || page === this.page) {
      return;
    }
    this.page = page;
    this.load();
  }

  toggleExpand(id: string) {
    this.expandedId = this.expandedId === id ? null : id;
  }

  setStatus(interaction: Interaction, status: string) {
    if (status === interaction.status) {
      return;
    }
    this.interactionsService.updateStatus(interaction.id, status).subscribe({
      next: (updated) => {
        interaction.status = updated.status;
        interaction.updated_at = updated.updated_at;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error updating status:', err);
        this.error = 'Failed to update the status';
        this.cdr.detectChanges();
      },
    });
  }
}
