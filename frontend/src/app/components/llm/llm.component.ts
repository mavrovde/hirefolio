import { Component, ElementRef, ViewChild, AfterViewChecked, OnInit, ChangeDetectorRef, Inject, PLATFORM_ID, Input } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { LlmService, ChatMessage } from '../../services/llm.service';

import { HeaderComponent } from '../header/header.component';
import { SeoService } from '../../services/seo.service';

@Component({
  selector: 'app-llm',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, HeaderComponent],
  templateUrl: './llm.component.html',
  styleUrls: ['./llm.component.css']
})
export class LlmComponent implements OnInit, AfterViewChecked {
  @Input() standalone = true;
  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

  private terminalInputRef: ElementRef | null = null;
  @ViewChild('terminalInput') set terminalInput(content: ElementRef) {
    if (content) {
      this.terminalInputRef = content;
      this.focusInput();
    }
  }

  messages: ChatMessage[] = [];
  userInput = '';
  isThinking = false;

  constructor(
    private llmService: LlmService,
    private cdr: ChangeDetectorRef,
    private router: Router,
    private seoService: SeoService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) { }

  ngOnInit() {
    if (this.standalone) {
      this.seoService.updateSeo({
        title: 'Local AI Terminal',
        description: 'Interactive terminal interface for communicating with a local AI assistant. Developed by Sergii Mavrov.',
        url: '/llm',
        keywords: 'AI, LLM, Ollama, Terminal, Local AI, Chatbot, Sergii Mavrov'
      });
    }
    this.messages.push({ role: 'system', content: 'Connected to local AI agent. Ready for input.' });
  }

  ngAfterViewChecked() {
    if (isPlatformBrowser(this.platformId)) {
      this.scrollToBottom();
      this.focusInput();
    }
  }

  scrollToBottom(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    try {
      if (this.scrollContainer) {
        this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
      }
    } catch (err) { }
  }

  focusInput() {
    if (!isPlatformBrowser(this.platformId)) return;
    if (this.terminalInputRef && !this.isThinking) {
      this.terminalInputRef.nativeElement.focus();
    }
  }

  async sendMessage() {
    if (!this.userInput.trim() || this.isThinking) return;

    const content = this.userInput.trim();
    this.userInput = '';

    if (content.toLowerCase() === 'clear') {
      this.messages = [{ role: 'system', content: 'Console cleared.' }];
      return;
    }

    if (content.toLowerCase() === 'exit' || content.toLowerCase() === 'quit') {
      this.router.navigate(['/']);
      return;
    }

    // Add user message
    this.messages.push({ role: 'user', content });

    // Prepare for response
    this.isThinking = true;
    const assistantMsg: ChatMessage = { role: 'assistant', content: '' };
    this.messages.push(assistantMsg);
    this.cdr.detectChanges();

    try {
      const apiMessages = this.messages
        .filter(m => m.role !== 'system')
        .slice(0, -1);

      await this.llmService.chat(apiMessages, (chunk) => {
        if (this.isThinking) {
          this.isThinking = false;
          this.cdr.detectChanges();
        }
        assistantMsg.content += chunk;
        this.cdr.detectChanges();
        this.scrollToBottom();
      });

    } catch (error) {
      this.isThinking = false;
      this.messages.push({ role: 'system', content: 'Error: Failed to communicate with AI agent.' });
    } finally {
      this.isThinking = false;
      this.cdr.detectChanges();
    }
  }
}
