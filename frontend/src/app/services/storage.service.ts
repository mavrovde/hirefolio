import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({
    providedIn: 'root',
})
export class StorageService {
    private readonly CONSENT_KEY = 'cookie_consent';
    private consentSubject = new BehaviorSubject<boolean>(this.hasConsented());
    consent$ = this.consentSubject.asObservable();

    constructor() { }

    /**
     * Checks if the user has explicitly consented to cookies.
     */
    hasConsented(): boolean {
        return localStorage.getItem(this.CONSENT_KEY) === 'true';
    }

    /**
     * Checks if the user has made a decision (either accepted or declined).
     */
    isDecisionMade(): boolean {
        return localStorage.getItem(this.CONSENT_KEY) !== null;
    }

    /**
     * Sets the user's consent status.
     * @param granted True if consent is granted, false otherwise.
     */
    setConsent(granted: boolean): void {
        localStorage.setItem(this.CONSENT_KEY, String(granted));
        this.consentSubject.next(granted);

        if (!granted) {
            this.clearNonEssentialStorage();
        }
    }

    /**
     * Saves an item to local storage if consent is granted.
     * @param key The key to save.
     * @param value The value to save.
     */
    setItem(key: string, value: string): void {
        if (this.hasConsented()) {
            localStorage.setItem(key, value);
        }
    }

    /**
     * Retrieves an item from local storage.
     * @param key The key to retrieve.
     */
    getItem(key: string): string | null {
        return localStorage.getItem(key);
    }

    /**
     * Removes an item from local storage.
     * @param key The key to remove.
     */
    removeItem(key: string): void {
        localStorage.removeItem(key);
    }

    /**
     * Clears non-essential data if consent is revoked.
     * Keeps the consent decision itself.
     */
    private clearNonEssentialStorage(): void {
        // We iterate and remove everything except the consent key
        // In a real app, you'd might have a whitelist or specific keys to remove
        // For now, we'll assume everything else is non-essential (like 'language')
        const keysToRemove: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key !== this.CONSENT_KEY) {
                keysToRemove.push(key);
            }
        }

        keysToRemove.forEach(key => localStorage.removeItem(key));
    }
}
