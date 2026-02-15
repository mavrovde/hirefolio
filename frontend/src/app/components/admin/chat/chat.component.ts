
import { Component, ElementRef, ViewChild, AfterViewChecked, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LlmService, ChatMessage } from '../../../services/llm.service';

@Component({
    selector: 'app-admin-chat',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './chat.component.html',
    styles: [`
    .chat-container {
      height: calc(100vh - 200px);
    }
  `]
})
export class AdminChatComponent implements AfterViewChecked {
    @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

    messages: ChatMessage[] = [];
    userInput: string = '';
    isLoading: boolean = false;

    constructor(private llmService: LlmService, private cdr: ChangeDetectorRef) { }

    ngAfterViewChecked() {
        this.scrollToBottom();
    }

    scrollToBottom(): void {
        try {
            this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
        } catch (err) { }
    }

    async sendMessage() {
        if (!this.userInput.trim() || this.isLoading) return;

        const userMsg: ChatMessage = { role: 'user', content: this.userInput };
        this.messages.push(userMsg);
        this.userInput = '';
        this.isLoading = true;

        try {
            const response = await this.llmService.chatGemini(this.messages);
            this.messages.push({ role: 'assistant', content: response });
        } catch (error) {
            console.error('Chat error:', error);
            this.messages.push({ role: 'assistant', content: 'Error: Failed to get response from Gemini.' });
        } finally {
            this.isLoading = false;
            this.cdr.detectChanges(); // Force update for E2E tests
        }
    }
}
