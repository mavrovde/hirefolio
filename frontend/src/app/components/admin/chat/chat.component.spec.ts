
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { AdminChatComponent } from './chat.component';
import { LlmService } from '../../../services/llm.service';
import { FormsModule } from '@angular/forms';
import { By } from '@angular/platform-browser';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('AdminChatComponent', () => {
    let component: AdminChatComponent;
    let fixture: ComponentFixture<AdminChatComponent>;
    let llmServiceMock: any;

    beforeEach(async () => {
        llmServiceMock = {
            chatGemini: vi.fn()
        };

        await TestBed.configureTestingModule({
            imports: [AdminChatComponent, FormsModule],
            providers: [
                { provide: LlmService, useValue: llmServiceMock }
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(AdminChatComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });


    it('should send message and display response', async () => {
        llmServiceMock.chatGemini.mockResolvedValue('Response from Gemini');

        component.userInput = 'Hello';
        const promise = component.sendMessage();

        expect(component.messages.length).toBe(1);
        expect(component.messages[0].content).toBe('Hello');
        expect(component.isLoading).toBe(true);

        await promise;

        expect(component.messages.length).toBe(2);
        expect(component.messages[1].content).toBe('Response from Gemini');
        expect(component.isLoading).toBe(false);
    });

    it('should handle error from service', async () => {
        llmServiceMock.chatGemini.mockRejectedValue(new Error('Network error'));

        component.userInput = 'Hello';
        const promise = component.sendMessage();

        await promise;

        expect(component.messages.length).toBe(2);
        expect(component.messages[1].content).toContain('Error:');
        expect(component.isLoading).toBe(false);
    });

    it('should not send empty message', () => {
        component.userInput = '   ';
        component.sendMessage();
        expect(llmServiceMock.chatGemini).not.toHaveBeenCalled();
    });

    it('should scroll to bottom after view checked', () => {
        const scrollSpy = vi.spyOn(component, 'scrollToBottom');
        component.ngAfterViewChecked();
        expect(scrollSpy).toHaveBeenCalled();
    });
});
