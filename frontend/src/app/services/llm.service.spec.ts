import { TestBed } from '@angular/core/testing';
import { LlmService, ChatMessage } from './llm.service';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('LlmService', () => {
    let service: LlmService;
    let mockAuthService: any;

    beforeEach(() => {
        mockAuthService = {
            getToken: vi.fn().mockReturnValue('test-token')
        };

        TestBed.configureTestingModule({
            providers: [
                LlmService,
                { provide: AuthService, useValue: mockAuthService }
            ]
        });
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

        it('should throw error on generateName API failure', async () => {
            (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
            await expect(service.generateName('test')).rejects.toThrow('Failed to generate name');
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

            expect(globalThis.fetch).toHaveBeenCalledWith(`${environment.apiUrl}${environment.apiPrefix}/ai/multi-chat`, expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ agents, topic })
            }));

            // Should be called 2 times
            expect(onChunk).toHaveBeenCalledTimes(2);
            expect(onChunk).toHaveBeenCalledWith(1, 'Hello', undefined);
            expect(onChunk).toHaveBeenCalledWith(1, ' World', true);
            expect(onDone).toHaveBeenCalled();
        });

        it('should handle JSON parse errors, empty lines, and done signals in stream', async () => {
            const onChunk = vi.fn();
            const spy = vi.spyOn(console, 'error').mockImplementation(() => { });

            const mockValues = [
                { done: false, value: new TextEncoder().encode('\n\n') },
                { done: false, value: new TextEncoder().encode('invalid json\n') },
                { done: false, value: new TextEncoder().encode(JSON.stringify({ agent: 1, content: 'Valid' }) + '\n') },
                { done: false, value: new TextEncoder().encode(JSON.stringify({ done: true }) + '\n') },
                { done: true, value: undefined }
            ];

            let callCount = 0;
            const mockReader = {
                read: vi.fn().mockImplementation(() => Promise.resolve(mockValues[callCount++])),
                releaseLock: vi.fn()
            };

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                body: { getReader: () => mockReader }
            });

            await service.multiChat(agents, topic, onChunk);

            expect(spy).toHaveBeenCalled();
            expect(onChunk).toHaveBeenCalledWith(1, 'Valid', undefined);
            spy.mockRestore();
        });

        it('should handle abort signal', async () => {
            const controller = new AbortController();
            const onChunk = vi.fn();

            (globalThis.fetch as any).mockImplementation((url: string, init: any) => {
                if (init.signal.aborted) {
                    return Promise.reject(new Error('AbortError'));
                }
                return new Promise((resolve, reject) => {
                    init.signal.addEventListener('abort', () => reject(new Error('AbortError')));
                });
            });

            const promise = service.multiChat(agents, topic, onChunk, undefined, controller.signal);
            controller.abort();

            await expect(promise).rejects.toThrow('AbortError');
        });

        it('should notify onDone even if stream ends abruptly', async () => {
            const onChunk = vi.fn();
            const onDone = vi.fn();

            const mockReader = {
                read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
                releaseLock: vi.fn()
            };

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                body: { getReader: () => mockReader }
            });

            await service.multiChat(agents, topic, onChunk, onDone);
            expect(onDone).toHaveBeenCalled();
        });

        it('should throw error on multiChat API failure (non-ok response)', async () => {
            (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
            await expect(service.multiChat(agents, 'topic', vi.fn())).rejects.toThrow('Failed to start multi-agent chat');
        });

        it('should throw error on multiChat failure (null body)', async () => {
            (globalThis.fetch as any).mockResolvedValue({ ok: true, body: null });
            await expect(service.multiChat(agents, 'topic', vi.fn())).rejects.toThrow('Failed to start multi-agent chat');
        });
    });

    describe('chatGemini', () => {
        it('should send auth token in headers', async () => {
            const messages: ChatMessage[] = [{ role: 'user', content: 'hello' }];
            const mockResponse = { response: 'Hi' };

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                json: async () => mockResponse
            });

            const result = await service.chatGemini(messages);

            expect(result).toBe('Hi');
            expect(globalThis.fetch).toHaveBeenCalledWith(
                `${environment.apiUrl}${environment.apiPrefix}/ai/gemini-chat`,
                expect.objectContaining({
                    method: 'POST',
                    headers: expect.objectContaining({
                        'Authorization': 'Bearer test-token',
                        'Content-Type': 'application/json'
                    })
                })
            );
        });

        it('should not send auth header if no token', async () => {
            mockAuthService.getToken.mockReturnValue(null);
            const messages: ChatMessage[] = [{ role: 'user', content: 'hello' }];
            const mockResponse = { response: 'Hi' };

            (globalThis.fetch as any).mockResolvedValue({
                ok: true,
                json: async () => mockResponse
            });

            await service.chatGemini(messages);

            expect(globalThis.fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
            );
        });

        it('should throw error on chatGemini API failure', async () => {
            (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 500 });
            await expect(service.chatGemini([])).rejects.toThrow('Failed to chat with Gemini');
        });
    });
});
