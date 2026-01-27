import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';

export interface ChatMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
}

@Injectable({
    providedIn: 'root'
})
export class LlmService {
    private apiUrl = `${environment.apiUrl}/api/ai/chat`;

    constructor() { }

    async chat(messages: ChatMessage[], onChunk: (chunk: string) => void): Promise<void> {
        try {
            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ messages })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            if (!response.body) {
                throw new Error('Response body is null');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                onChunk(chunk);
            }
        } catch (error) {
            console.error('Chat error:', error);
            throw error;
        }
    }
}
