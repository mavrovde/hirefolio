import { describe, it, expect, vi, beforeEach } from 'vitest';

const bootstrapApplicationMock = vi.fn();

vi.mock('@angular/platform-browser', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@angular/platform-browser')>();
  return {
    ...actual,
    bootstrapApplication: (...args: unknown[]) => bootstrapApplicationMock(...args),
  };
});

describe('main.server bootstrap', () => {
  beforeEach(() => {
    bootstrapApplicationMock.mockReset();
    vi.resetModules();
  });

  it('invokes bootstrapApplication with AppComponent, config and the passed context', async () => {
    const fakeResult = Symbol('appRef');
    bootstrapApplicationMock.mockReturnValue(fakeResult);

    const bootstrap = (await import('./main.server')).default;
    const { AppComponent } = await import('./app/app.component');
    const { config } = await import('./app/app.config.server');

    const context = { platformRef: {} } as unknown as import('@angular/platform-browser').BootstrapContext;
    const result = bootstrap(context);

    expect(bootstrapApplicationMock).toHaveBeenCalledTimes(1);
    expect(bootstrapApplicationMock).toHaveBeenCalledWith(AppComponent, config, context);
    expect(result).toBe(fakeResult);
  });
});
