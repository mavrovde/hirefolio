import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  OpportunitiesService,
  Opportunity,
  OPPORTUNITY_STAGES,
  OPPORTUNITY_SOURCES,
} from '../../../services/opportunities.service';
import { AdminCvService, CvVersion } from '../../../services/admin-cv.service';

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

  // CV variants (#247 criterion 4): loaded lazily when the detail panel opens,
  // because most panel opens never touch the CV control.
  cvVersions: CvVersion[] = [];
  cvChoice = '';
  sendingCv = false;

  constructor(
    private opportunitiesService: OpportunitiesService,
    private adminCvService: AdminCvService,
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
    // A stale selection from the PREVIOUS panel must never carry over: with it,
    // one click records the wrong variant against the wrong company — the one
    // datum this feature exists to record (#294 review round 1, reproduced).
    this.cvChoice = '';
    this.loadCvVersions();
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

  loadCvVersions() {
    // 100 is the backend's le=100 page bound (admin_cv.py): variants beyond
    // the 100th are unpickable here until the control grows pagination —
    // an accepted limit, recorded rather than hidden (#294 review nit 10).
    this.adminCvService.getVersions(1, 100).subscribe({
      next: (page) => {
        this.cvVersions = page.items;
        this.cdr.detectChanges();
      },
      error: (err) => {
        // Not fatal to the panel: the rest of the detail view works without
        // the CV list; the control simply stays empty.
        console.error('Error loading CV versions:', err);
        this.cdr.detectChanges();
      },
    });
  }

  /** The variant currently recorded on the selected opportunity, if the list
   *  has it (it may have been deleted — the FK is SET NULL server-side). */
  sentCvLabel(): string | null {
    if (!this.selected?.sent_cv_id) {
      return null;
    }
    const doc = this.cvVersions.find((v) => v.id === this.selected!.sent_cv_id);
    return doc ? `${doc.version} (${doc.filename})` : 'a since-deleted version';
  }

  recordCvSent() {
    if (!this.selected || !this.cvChoice || this.sendingCv) {
      return;
    }
    this.sendingCv = true;
    this.opportunitiesService.recordCvSent(this.selected.id, this.cvChoice).subscribe({
      next: (full) => {
        this.selected = full;
        this.all = this.all.map((o) => (o.id === full.id ? full : o));
        this.cvChoice = '';
        this.sendingCv = false;
        this.error = null; // a stale failure banner must not outlive a success
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error recording the sent CV:', err);
        this.error = 'Failed to record the sent CV';
        this.sendingCv = false;
        this.cdr.detectChanges();
      },
    });
  }
}
