import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AdminChatComponent } from './chat.component';
import { LlmService } from '@mavrov/shared';
import { FormsModule } from '@angular/forms';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('AdminChatComponent (cov2)', () => {
    let component: AdminChatComponent;
    let fixture: ComponentFixture<AdminChatComponent>;
    let llmServiceMock: any;
    let originalLocalStorage: PropertyDescriptor | undefined;

    beforeEach(async () => {
        llmServiceMock = { chatGemini: vi.fn() };
        originalLocalStorage = Object.getOwnPropertyDescriptor(window, 'localStorage');

        await TestBed.configureTestingModule({
            imports: [AdminChatComponent, FormsModule],
            providers: [{ provide: LlmService, useValue: llmServiceMock }]
        }).compileComponents();

        fixture = TestBed.createComponent(AdminChatComponent);
        component = fixture.componentInstance;
    });

    afterEach(() => {
        if (originalLocalStorage) {
            Object.defineProperty(window, 'localStorage', originalLocalStorage);
        }
        vi.clearAllMocks();
        vi.unstubAllGlobals();
    });

    // Covers line 76: early return in loadFromLocalStorage when localStorage is undefined
    it('should return early from loadFromLocalStorage when localStorage is undefined', () => {
        vi.stubGlobal('localStorage', undefined);

        // ngOnInit -> loadFromLocalStorage; should not throw and leave messages empty
        expect(() => component.ngOnInit()).not.toThrow();
        expect(component.messages.length).toBe(0);
    });

    // Covers line 67: early return in saveToLocalStorage when localStorage is undefined
    it('should return early from saveToLocalStorage when localStorage is undefined', async () => {
        // Load first (with localStorage present) is skipped; directly drive sendMessage.
        vi.stubGlobal('localStorage', undefined);
        llmServiceMock.chatGemini.mockResolvedValue('Reply');

        component.userInput = 'Hi';
        await component.sendMessage();

        // Message flow still works even though persistence is skipped.
        expect(component.messages.length).toBe(2);
        expect(component.messages[1].content).toBe('Reply');
        expect(component.isLoading).toBe(false);
    });

    // Covers line 85 else-branch: parsed.messages missing -> fallback to []
    it('should fall back to empty array when parsed history has no messages field', () => {
        const stored = JSON.stringify({ timestamp: Date.now() }); // no messages key
        const lsMock = {
            getItem: vi.fn().mockReturnValue(stored),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        vi.stubGlobal('localStorage', lsMock);

        component.ngOnInit();

        expect(component.messages).toEqual([]);
        expect(lsMock.removeItem).not.toHaveBeenCalled();
    });

    // Covers lines 90-91: catch block when JSON.parse throws
    it('should handle corrupt history JSON and clear storage', () => {
        const lsMock = {
            getItem: vi.fn().mockReturnValue('{not valid json'),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        vi.stubGlobal('localStorage', lsMock);
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        component.ngOnInit();

        expect(component.messages).toEqual([]);
        expect(lsMock.removeItem).toHaveBeenCalledWith('gemini_chat_history_v1');
        expect(errorSpy).toHaveBeenCalledWith('Failed to parse chat history', expect.anything());

        errorSpy.mockRestore();
    });
});
