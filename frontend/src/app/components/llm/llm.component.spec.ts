import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { LlmComponent } from './llm.component';
import { LlmService } from '../../services/llm.service';
import { FormsModule } from '@angular/forms';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { provideRouter, Router } from '@angular/router';

class MockLlmService {
    chat = vi.fn();
}

describe('LlmComponent', () => {
    let component: LlmComponent;
    let fixture: ComponentFixture<LlmComponent>;
    let llmService: MockLlmService;
    let router: Router;

    beforeEach(async () => {
        llmService = new MockLlmService();
        await TestBed.configureTestingModule({
            imports: [LlmComponent, FormsModule],
            providers: [
                { provide: LlmService, useValue: llmService },
                provideRouter([])
            ]
        })
            .compileComponents();

        fixture = TestBed.createComponent(LlmComponent);
        component = fixture.componentInstance;
        router = TestBed.inject(Router);
        fixture.detectChanges();
    });

    it('should create and have initial system message', () => {
        expect(component).toBeTruthy();
        expect(component.messages.length).toBe(1);
        expect(component.messages[0].role).toBe('system');
    });

    it('should clear messages when "clear" command is sent', async () => {
        component.userInput = 'clear';
        await component.sendMessage();
        expect(component.messages.length).toBe(1);
        expect(component.messages[0].content).toBe('Console cleared.');
    });

    it('should navigate to home on "exit" or "quit"', async () => {
        const navigateSpy = vi.spyOn(router, 'navigate');

        component.userInput = 'exit';
        await component.sendMessage();
        expect(navigateSpy).toHaveBeenCalledWith(['/']);

        component.userInput = 'quit';
        await component.sendMessage();
        expect(navigateSpy).toHaveBeenCalledTimes(2);
    });

    it('should not send message if input is empty or just whitespace', async () => {
        component.userInput = '   ';
        await component.sendMessage();
        expect(llmService.chat).not.toHaveBeenCalled();
        expect(component.messages.length).toBe(1);
    });

    it('should handle successful message sending and streaming', async () => {
        component.userInput = 'hello';

        llmService.chat.mockImplementation((msgs, onChunk) => {
            onChunk('Hi');
            onChunk(' there');
            return Promise.resolve();
        });

        await component.sendMessage();

        expect(llmService.chat).toHaveBeenCalled();
        expect(component.messages.length).toBe(3);
        expect(component.messages[1].content).toBe('hello');
        expect(component.messages[2].content).toBe('Hi there');
        expect(component.isThinking).toBe(false);
    });

    it('should handle errors during chat and show system message', async () => {
        component.userInput = 'fail';
        llmService.chat.mockRejectedValue(new Error('API Error'));

        await component.sendMessage();

        expect(component.messages.some(m => m.content.includes('Error'))).toBe(true);
        expect(component.isThinking).toBe(false);
    });

    it('should scroll to bottom after view check', () => {
        const scrollSpy = vi.spyOn(component, 'scrollToBottom');
        component.ngAfterViewChecked();
        expect(scrollSpy).toHaveBeenCalled();
    });

    it('should not send message if already thinking', async () => {
        component.isThinking = true;
        component.userInput = 'busy';
        await component.sendMessage();
        expect(llmService.chat).not.toHaveBeenCalled();
    });

    it('should handle scrollToBottom error gracefully', () => {
        // @ts-ignore - trigger null check branch
        component['scrollContainer'] = null;
        expect(() => component.scrollToBottom()).not.toThrow();
    });

    it('should handle multiline assistant messages', async () => {
        component.userInput = 'multiline';
        llmService.chat.mockImplementation((msgs, onChunk) => {
            onChunk('Line 1\nLine 2');
            return Promise.resolve();
        });

        await component.sendMessage();
        expect(component.messages[2].content).toBe('Line 1\nLine 2');
    });

    it('should update assistant message and stop thinking on first chunk', async () => {
        component.userInput = 'stream test';
        let chunkCallback: any;
        let resolveChat: any;
        llmService.chat.mockImplementation((msgs, onChunk) => {
            chunkCallback = onChunk;
            return new Promise(resolve => { resolveChat = resolve; });
        });

        const promise = component.sendMessage();
        // Allow microtasks to run to reach the first await
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(component.isThinking).toBe(true);

        chunkCallback('part 1');
        expect(component.isThinking).toBe(false);
        expect(component.messages[2].content).toBe('part 1');

        resolveChat();
        await promise;
    });

    it('should maintain focus on terminal input', async () => {
        vi.useFakeTimers();
        const mockInput = { nativeElement: { focus: vi.fn() } };
        // @ts-ignore
        component.terminalInput = mockInput as any;

        vi.runAllTimers();
        expect(mockInput.nativeElement.focus).toHaveBeenCalled();
        vi.useRealTimers();
    });

    it('should call focusInput on click', () => {
        const focusSpy = vi.spyOn(component, 'focusInput');
        fixture.nativeElement.querySelector('.terminal-container').click();
        expect(focusSpy).toHaveBeenCalled();
    });
});
