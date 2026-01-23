import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Profile } from '../../services/profile.service';

@Component({
  selector: 'app-skills',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './skills.component.html',
  styleUrls: ['./skills.component.css']

})
export class SkillsComponent {
  @Input() profile: Profile | null = null;
}
