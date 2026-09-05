import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe } from '@mavrov/shared';
import { Profile } from '../../services/profile.service';
import { ContactFormComponent } from './contact-form.component';

@Component({
  selector: 'app-contact',
  standalone: true,
  imports: [CommonModule, TranslatePipe, ContactFormComponent],
  templateUrl: './contact.component.html',
  styleUrls: ['./contact.component.scss'],
})
export class ContactComponent {
  @Input() profile: Profile | null = null;
}
