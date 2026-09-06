import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  OpportunitiesService,
  Opportunity,
  OPPORTUNITY_STAGES,
  OPPORTUNITY_SOURCES,
} from '../../../services/opportunities.service';

/**
 * Job-search pipeline board (#247): opportunities by stage, with a detail
 * panel (notes timeline, stage moves, next action) and a quick-create form.
 */
@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pipeline.component.html',
})
export class PipelineComponent implements OnInit {
  readonly stages = OPPORTUNITY_STAGES;
  readonly sources = OPPORTUNITY_SOURCES;

  all: Opportunity[] = [];
  selected: Opportunity | null = null;

  loading = false;
  error: string | null = null;

  // quick-create form
  showCreate = false;
  draft = { company: '', role_title: '', source: 'recruiter_outreach' };

  noteDraft = '';

  constructor(
    private opportunitiesService: OpportunitiesService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit() {
    this.load();
  }

  byStage(stage: string): Opportunity[] {
    return this.all.filter((o) => o.stage === stage);
  }

  load() {
    this.loading = true;
    this.error = null;
    this.opportunitiesService.list().subscribe({
      next: (res) => {
        this.all = res.items;
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error loading pipeline:', err);
        this.error = 'Failed to load the pipeline';
        this.loading = false;
        this.cdr.detectChanges();
      },
    });
  }

  create() {
    if (!this.draft.company.trim() || !this.draft.role_title.trim()) {
      return;
    }
    this.opportunitiesService.create(this.draft).subscribe({
      next: (opp) => {
        this.all = [opp, ...this.all];
        this.showCreate = false;
        this.draft = { company: '', role_title: '', source: 'recruiter_outreach' };
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error creating opportunity:', err);
        this.error = 'Failed to create the opportunity';
        this.cdr.detectChanges();
      },
    });
  }

  open(opportunity: Opportunity) {
    this.opportunitiesService.get(opportunity.id).subscribe({
      next: (full) => {
        this.selected = full;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error loading opportunity:', err);
        this.error = 'Failed to load the opportunity';
        this.cdr.detectChanges();
      },
    });
  }

  close() {
    this.selected = null;
    this.noteDraft = '';
  }

  moveStage(stage: string) {
    if (!this.selected || stage === this.selected.stage) {
      return;
    }
    this.opportunitiesService.moveStage(this.selected.id, stage).subscribe({
      next: (updated) => {
        this.selected = updated;
        this.all = this.all.map((o) => (o.id === updated.id ? updated : o));
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error moving stage:', err);
        this.error = 'Failed to move the stage';
        this.cdr.detectChanges();
      },
    });
  }

  addNote() {
    if (!this.selected || !this.noteDraft.trim()) {
      return;
    }
    this.opportunitiesService.addNote(this.selected.id, this.noteDraft).subscribe({
      next: (updated) => {
        this.selected = updated;
        this.noteDraft = '';
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error adding note:', err);
        this.error = 'Failed to add the note';
        this.cdr.detectChanges();
      },
    });
  }
}
