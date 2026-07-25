import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe } from '@mavrov/shared';
import { StorageService } from '@mavrov/shared';

@Component({
    selector: 'app-cookie-consent',
    standalone: true,
    imports: [CommonModule, TranslatePipe],
    templateUrl: './cookie-consent.component.html',
    styleUrls: ['./cookie-consent.component.css'],
})
export class CookieConsentComponent {
    isVisible = false;

    constructor(private storageService: StorageService) {
        this.isVisible = !this.storageService.isDecisionMade();
    }

    accept() {
        this.storageService.setConsent(true);
        this.isVisible = false;
    }

    decline() {
        this.storageService.setConsent(false);
        this.isVisible = false;
    }
}
