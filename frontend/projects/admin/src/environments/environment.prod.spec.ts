import { describe, it, expect } from 'vitest';
import { environment } from './environment.prod';

describe('environment.prod', () => {
  it('should be the production configuration', () => {
    expect(environment.production).toBe(true);
    expect(environment.apiPrefix).toBe('/api/app');
  });
});
