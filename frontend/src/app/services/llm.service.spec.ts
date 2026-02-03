import { TestBed } from '@angular/core/testing';
import { LlmService, ChatMessage } from './llm.service';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('LlmService', () => {
    let service: LlmService;

    beforeEach(() => {
        TestBed.configureTestingModule({});
        service = TestBed.inject(LlmService);
        (globalThis as any).fetch = vi.fn();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    describe('chat', () => {
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

            await expect(service.chat(messages, onChunk)).rejects.toThrow();
        });

        it('should throw error if response body is null', async () => {
            const messages: ChatMessage[] = [{ role: 'user', content: 'test' }];
            const onChunk = vi.fn();

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                body: null
            });

            await expect(service.chat(messages, onChunk)).rejects.toThrow();
        });

        it('should handle network error', async () => {
            const messages: ChatMessage[] = [{ role: 'user', content: 'test' }];
            const onChunk = vi.fn();

            (globalThis.fetch as any).mockRejectedValue(new Error('Network error'));

            await expect(service.chat(messages, onChunk)).rejects.toThrow('Network error');
        });
    });


    describe('generateName', () => {
        it('should generate name successfully', async () => {
            const description = 'A wise teacher';
            const mockName = 'Professor Wise';

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                json: async () => ({ name: mockName })
            });

            const result = await service.generateName(description);

            expect(result).toBe(mockName);
        });
    });

    describe('multiChat', () => {
        const agents = [
            { id: 1, name: 'A1', description: 'D1' },
            { id: 2, name: 'A2', description: 'D2' }
        ];
        const topic = 'Test Topic';

        it('should stream multi-agent conversation', async () => {
            const onChunk = vi.fn();
            const onDone = vi.fn();

            const mockValues = [
                { done: false, value: new TextEncoder().encode(JSON.stringify({ agent: 1, content: 'Hello' }) + '\n') },
                { done: false, value: new TextEncoder().encode(JSON.stringify({ agent: 1, content: ' World', turn_complete: true }) + '\n') },
                { done: true, value: undefined }
            ];

            let callCount = 0;
            const mockReader = {
                read: vi.fn().mockImplementation(() => Promise.resolve(mockValues[callCount++])),
                releaseLock: vi.fn()
            };

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                body: {
                    getReader: () => mockReader
                }
            });

            await service.multiChat(agents, topic, onChunk, onDone);

            expect(globalThis.fetch).toHaveBeenCalledWith('/api/ai/multi-chat', expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ agents, topic })
            }));

            // Should be called 2 times
            expect(onChunk).toHaveBeenCalledTimes(2);
            expect(onChunk).toHaveBeenCalledWith(1, 'Hello', undefined);
            expect(onChunk).toHaveBeenCalledWith(1, ' World', true);
            expect(onDone).toHaveBeenCalled();
        });

        it('should handle API errors', async () => {
            const onChunk = vi.fn();
            const onDone = vi.fn();

            (globalThis.fetch as any).mockResolvedValue({
                ok: false,
                status: 500
            });

            await expect(service.multiChat(agents, topic, onChunk, onDone)).rejects.toThrow();
            expect(onDone).not.toHaveBeenCalled();
        });

        it('should throw error if response body is null', async () => {
            const onChunk = vi.fn();
            const onDone = vi.fn();

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                body: null
            });

            await expect(service.multiChat(agents, topic, onChunk, onDone)).rejects.toThrow();
        });
    });
});
