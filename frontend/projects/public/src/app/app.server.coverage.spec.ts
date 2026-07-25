import { describe, it, expect } from 'vitest';
import { serverRoutes } from './app.routes.server';
import { config } from './app.config.server';
import { RenderMode } from '@angular/ssr';
import bootstrap from '../main.server';

describe('server-side app configuration', () => {
  it('defines admin as client-rendered and everything else as server-rendered', () => {
    expect(serverRoutes.length).toBe(2);
    const admin = serverRoutes.find((r) => r.path === 'admin/**');
    const rest = serverRoutes.find((r) => r.path === '**');
    expect(admin?.renderMode).toBe(RenderMode.Client);
    expect(rest?.renderMode).toBe(RenderMode.Server);
  });

  it('merges the browser app config with server rendering providers', () => {
    expect(config).toBeTruthy();
    expect(Array.isArray(config.providers)).toBe(true);
    expect(config.providers.length).toBeGreaterThan(0);
  });

  it('exposes a bootstrap function from main.server', () => {
    expect(typeof bootstrap).toBe('function');
  });
});
