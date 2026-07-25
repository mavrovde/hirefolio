import { YearExtractPipe } from './year-extract.pipe';
import { describe, it, expect } from 'vitest';

describe('YearExtractPipe', () => {
    const pipe = new YearExtractPipe();

    it('should create an instance', () => {
        expect(pipe).toBeTruthy();
    });

    it('should extract year from "Mar 2025"', () => {
        expect(pipe.transform('Mar 2025')).toBe('2025');
    });

    it('should extract year from "Jan 2021"', () => {
        expect(pipe.transform('Jan 2021')).toBe('2021');
    });

    it('should extract year from "Apr 2014"', () => {
        expect(pipe.transform('Apr 2014')).toBe('2014');
    });

    it('should extract year from "Sep 2009"', () => {
        expect(pipe.transform('Sep 2009')).toBe('2009');
    });

    it('should return empty string for null', () => {
        expect(pipe.transform(null)).toBe('');
    });

    it('should return empty string for undefined', () => {
        expect(pipe.transform(undefined)).toBe('');
    });

    it('should return empty string for non-date text', () => {
        expect(pipe.transform('Present')).toBe('');
    });

    it('should extract year from complex strings', () => {
        expect(pipe.transform('Tiraspol, Transnistria autonomous territorial unit, Moldova')).toBe('');
    });

    it('should extract first year from string with multiple years', () => {
        expect(pipe.transform('Jun 2004 - Aug 2005 · 1 yr 3 mos')).toBe('2004');
    });
});
