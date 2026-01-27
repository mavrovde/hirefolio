import { MockTranslatePipe } from './mock-translate.pipe';
import { describe, it, expect } from 'vitest';

describe('MockTranslatePipe', () => {
    it('should return the input value', () => {
        const pipe = new MockTranslatePipe();
        expect(pipe.transform('TEST')).toBe('TEST');
    });
});
