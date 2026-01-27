import { TestBed } from '@angular/core/testing';
import { LlmService, ChatMessage } from './llm.service';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('LlmService', () => {
    let service: LlmService;

    beforeEach(() => {
        TestBed.configureTestingModule({});
        service = TestBed.inject(LlmService);
        // @ts-ignore
        globalThis.fetch = vi.fn();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should stream chat response successfully', async () => {
        const messages: ChatMessage[] = [{ role: 'user', content: 'hello' }];
        const onChunk = vi.fn();

        const mockValues = [
            { done: false, value: new TextEncoder().encode('Hello') },
            { done: false, value: new TextEncoder().encode(' world') },
            { done: true, value: undefined }
        ];

        let callCount = 0;
        const mockReader = {
            read: vi.fn().mockImplementation(() => Promise.resolve(mockValues[callCount++]))
        };

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            body: {
                getReader: () => mockReader
            }
        });

        await service.chat(messages, onChunk);

        expect(onChunk).toHaveBeenCalledTimes(2);
        expect(onChunk).toHaveBeenNthCalledWith(1, 'Hello');
        expect(onChunk).toHaveBeenNthCalledWith(2, ' world');
    });

    it('should throw error on non-ok HTTP response', async () => {
        const messages: ChatMessage[] = [{ role: 'user', content: 'test' }];
        const onChunk = vi.fn();

        (globalThis.fetch as any).mockResolvedValue({
            ok: false,
            status: 500
        });

        await expect(service.chat(messages, onChunk)).rejects.toThrow('HTTP error! status: 500');
    });

    it('should throw error if response body is null', async () => {
        const messages: ChatMessage[] = [{ role: 'user', content: 'test' }];
        const onChunk = vi.fn();

        (globalThis.fetch as any).mockResolvedValue({
            ok: true,
            body: null
        });

        await expect(service.chat(messages, onChunk)).rejects.toThrow('Response body is null');
    });

    it('should handle network error', async () => {
        const messages: ChatMessage[] = [{ role: 'user', content: 'test' }];
        const onChunk = vi.fn();

        (globalThis.fetch as any).mockRejectedValue(new Error('Network error'));

        await expect(service.chat(messages, onChunk)).rejects.toThrow('Network error');
    });
});
