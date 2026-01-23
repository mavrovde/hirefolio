import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Profile } from '../../services/profile.service';

@Component({
  selector: 'app-recommendations',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  templateUrl: './recommendations.component.html',
  styleUrls: ['./recommendations.component.css']

})
export class RecommendationsComponent {
  @Input() profile: Profile | null = null;
}
