import { TestBed } from '@angular/core/testing';
import { LlmService } from './llm.service';
import { environment } from '../../environments/environment';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('LlmService uncovered branches', () => {
  let service: LlmService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LlmService);
    (globalThis as any).fetch = vi.fn();
  });

  afterEach(() => vi.restoreAllMocks());

  it('generateName throws on non-ok response (line 58)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
    await expect(service.generateName('x')).rejects.toThrow('Failed to generate name');
  });

  it('multiChat throws on non-ok response (line 80)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
    await expect(
      service.multiChat([{ id: 1, name: 'A', description: 'D' }], 'topic', vi.fn()),
    ).rejects.toThrow('Failed to start multi-agent chat');
  });

  it('multiChat throws when body is null (line 80)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: true, body: null });
    await expect(
      service.multiChat([{ id: 1, name: 'A', description: 'D' }], 'topic', vi.fn()),
    ).rejects.toThrow('Failed to start multi-agent chat');
  });

  it('multiChat breaks the loop on a done marker line', async () => {
    const onChunk = vi.fn();
    const values = [
      {
        done: false,
        value: new TextEncoder().encode(
          JSON.stringify({ agent: 1, content: 'hi' }) + '\n' + JSON.stringify({ done: true }) + '\n',
        ),
      },
      { done: true, value: undefined },
    ];
    let i = 0;
    const reader = {
      read: vi.fn().mockImplementation(() => Promise.resolve(values[i++])),
      releaseLock: vi.fn(),
    };
    (globalThis.fetch as any).mockResolvedValue({ ok: true, body: { getReader: () => reader } });

    await service.multiChat([{ id: 1, name: 'A', description: 'D' }], 'topic', onChunk);
    expect(onChunk).toHaveBeenCalledWith(1, 'hi', undefined);
    expect(reader.releaseLock).toHaveBeenCalled();
  });

  it('multiChat skips blank lines in the stream (line 99 continue)', async () => {
    const onChunk = vi.fn();
    const values = [
      {
        done: false,
        // A blank line, then a valid JSON line
        value: new TextEncoder().encode('   \n' + JSON.stringify({ agent: 1, content: 'ok' }) + '\n'),
      },
      { done: true, value: undefined },
    ];
    let i = 0;
    const reader = {
      read: vi.fn().mockImplementation(() => Promise.resolve(values[i++])),
      releaseLock: vi.fn(),
    };
    (globalThis.fetch as any).mockResolvedValue({ ok: true, body: { getReader: () => reader } });

    await service.multiChat([{ id: 1, name: 'A', description: 'D' }], 'topic', onChunk);
    expect(onChunk).toHaveBeenCalledTimes(1);
    expect(onChunk).toHaveBeenCalledWith(1, 'ok', undefined);
  });

  describe('chatGemini (lines 114-126)', () => {
    it('returns the response text on success', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ response: 'Gemini says hi' }),
      });
      const result = await service.chatGemini([{ role: 'user', content: 'hi' }]);
      expect(result).toBe('Gemini says hi');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `${environment.apiUrl}${environment.apiPrefix}/ai/gemini-chat`,
        expect.objectContaining({ method: 'POST' }),
      );
    });

    it('throws on non-ok response', async () => {
      (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
      await expect(service.chatGemini([{ role: 'user', content: 'hi' }])).rejects.toThrow(
        'Failed to chat with Gemini',
      );
    });
  });
});
