import { TestBed } from '@angular/core/testing';
import { TranslatePipe } from './translate.pipe';
import { LanguageService } from '../services/language.service';
import { MockLanguageService } from '../testing/mock-language.service';
import { ChangeDetectorRef } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('TranslatePipe', () => {
    let pipe: TranslatePipe;
    let languageService: MockLanguageService;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [
                TranslatePipe,
                { provide: LanguageService, useClass: MockLanguageService },
                { provide: ChangeDetectorRef, useValue: { markForCheck: vi.fn() } }
            ]
        });

        languageService = TestBed.inject(LanguageService) as unknown as MockLanguageService;
        pipe = TestBed.inject(TranslatePipe);
    });

    it('should create', () => {
        expect(pipe).toBeTruthy();
    });

    it('should translate a key', () => {
        const result = pipe.transform('HEADER.HOME');
        expect(result).toBe('HEADER.HOME'); // Mock returns key as-is
    });

    it('should return key if translation not found', () => {
        const result = pipe.transform('NONEXISTENT.KEY');
        expect(result).toBe('NONEXISTENT.KEY');
    });

    it('should handle empty key', () => {
        const result = pipe.transform('');
        expect(result).toBe('');
    });
});
