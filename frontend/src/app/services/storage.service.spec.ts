import { TestBed } from '@angular/core/testing';
import { StorageService } from './storage.service';

describe('StorageService', () => {
    let service: StorageService;

    beforeEach(() => {
        TestBed.configureTestingModule({});
        service = TestBed.inject(StorageService);
        localStorage.clear();
    });

    afterEach(() => {
        localStorage.clear();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should return false for hasConsented initially', () => {
        expect(service.hasConsented()).toBe(false);
    });

    it('should return false for isDecisionMade initially', () => {
        expect(service.isDecisionMade()).toBe(false);
    });

    it('should save consent as true', () => {
        service.setConsent(true);
        expect(service.hasConsented()).toBe(true);
        expect(service.isDecisionMade()).toBe(true);
        expect(localStorage.getItem('cookie_consent')).toBe('true');
    });

    it('should save consent as false', () => {
        service.setConsent(false);
        expect(service.hasConsented()).toBe(false);
        expect(service.isDecisionMade()).toBe(true);
        expect(localStorage.getItem('cookie_consent')).toBe('false');
    });

    it('should save item if consented', () => {
        service.setConsent(true);
        service.setItem('test_key', 'test_value');
        expect(localStorage.getItem('test_key')).toBe('test_value');
    });

    it('should NOT save item if NOT consented', () => {
        service.setConsent(false);
        service.setItem('test_key', 'test_value');
        expect(localStorage.getItem('test_key')).toBeNull();
    });

    it('should retrieve item', () => {
        localStorage.setItem('test_key', 'test_value');
        expect(service.getItem('test_key')).toBe('test_value');
    });

    it('should clear non-essential storage when consent is revoked', () => {
        localStorage.setItem('test_key', 'test_value');
        service.setConsent(false);
        expect(localStorage.getItem('test_key')).toBeNull();
        // Consent itself should remain
        expect(localStorage.getItem('cookie_consent')).toBe('false');
    });
});
