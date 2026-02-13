import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';

export interface ChatMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
}

export interface AgentConfig {
    id: number;
    name: string;
    description: string;
    role?: string;
    goal?: string;
}

@Injectable({
    providedIn: 'root'
})
export class LlmService {
    private apiUrl = `${environment.apiUrl}${environment.apiPrefix}/ai`;

    constructor() { }

    async chat(messages: ChatMessage[], onChunk: (chunk: string) => void, signal?: AbortSignal): Promise<void> {
        const response = await fetch(`${this.apiUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages }),
            signal
        });

        if (!response.ok || !response.body) {
            throw new Error('Failed to connect to AI service');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            onChunk(chunk);
        }
    }


    async generateName(description: string): Promise<string> {
        const response = await fetch(`${this.apiUrl}/generate-name`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });

        if (!response.ok) {
            throw new Error('Failed to generate name');
        }

        const data = await response.json();
        return data.name;
    }

    async multiChat(
        agents: AgentConfig[],
        topic: string,
        onChunk: (agentId: number, chunk: string, turnComplete?: boolean) => void,
        onDone?: () => void,
        signal?: AbortSignal
    ): Promise<void> {
        const response = await fetch(`${this.apiUrl}/multi-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agents, topic }),
            signal
        });

        if (!response.ok || !response.body) {
            throw new Error('Failed to start multi-agent chat');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.done) break;
                        onChunk(data.agent, data.content, data.turn_complete);
                    } catch (e) {
                        console.error('Error parsing JSON chunk', e);
                    }
                }
            }
        } finally {
            reader.releaseLock();
            if (onDone) onDone();
        }
    }
    async chatGemini(messages: ChatMessage[]): Promise<string> {
        const response = await fetch(`${this.apiUrl}/gemini-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages })
        });

        if (!response.ok) {
            throw new Error('Failed to chat with Gemini');
        }

        const data = await response.json();
        return data.response;
    }
}
