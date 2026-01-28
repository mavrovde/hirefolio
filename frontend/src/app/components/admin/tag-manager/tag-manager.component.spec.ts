import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TagManagerComponent } from './tag-manager.component';
import { TagsService, TagStat } from '../../../services/tags.service';
import { of, throwError, Subject } from 'rxjs';
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';
import { By } from '@angular/platform-browser';

describe('TagManagerComponent', () => {
    let component: TagManagerComponent;
    let fixture: ComponentFixture<TagManagerComponent>;
    let tagsServiceSpy: { getAllTags: Mock; renameTag: Mock; deleteTag: Mock };

    const mockTags: TagStat[] = [
        { name: 'Angular', count: 5 },
        { name: 'Python', count: 3 },
    ];

    beforeEach(async () => {
        tagsServiceSpy = {
            getAllTags: vi.fn().mockReturnValue(of(mockTags)),
            renameTag: vi.fn(),
            deleteTag: vi.fn(),
        };

        await TestBed.configureTestingModule({
            imports: [TagManagerComponent],
            providers: [{ provide: TagsService, useValue: tagsServiceSpy }],
        }).compileComponents();

        fixture = TestBed.createComponent(TagManagerComponent);
        component = fixture.componentInstance;
        // Do NOT call detectChanges here to allow individual tests to setup mocks first
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should load tags on init', () => {
        fixture.detectChanges(); // Triggers ngOnInit
        expect(tagsServiceSpy.getAllTags).toHaveBeenCalled();
        expect(component.tags).toEqual(mockTags);
        expect(component.loading).toBe(false);
    });

    it('should show loading state', () => {
        const subject = new Subject<TagStat[]>();
        tagsServiceSpy.getAllTags.mockReturnValue(subject);

        fixture.detectChanges(); // Triggers ngOnInit -> loadTags -> subscribe

        expect(component.loading).toBe(true);
        const loadingEl = fixture.debugElement.query(By.css('.loading'));
        expect(loadingEl).toBeTruthy();


    });

    it('should handle load error', () => {
        tagsServiceSpy.getAllTags.mockReturnValue(throwError(() => new Error('Load error')));
        fixture.detectChanges(); // Triggers ngOnInit -> loadTags -> Error

        expect(component.error).toBe('Failed to load tags.');
        expect(component.loading).toBe(false);
    });

    it('should start edit', () => {
        fixture.detectChanges();
        const tag = mockTags[0];
        component.startEdit(tag);
        expect(component.editingTag).toBe(tag.name);
        expect(component.editName).toBe(tag.name);
    });

    it('should cancel edit', () => {
        fixture.detectChanges();
        component.editingTag = 'Angular';
        component.editName = 'NewName';
        component.cancelEdit();
        expect(component.editingTag).toBe(null);
        expect(component.editName).toBe('');
    });

    it('should save rename success', () => {
        fixture.detectChanges();
        const tag = mockTags[0];
        const newName = 'AngularJS';
        component.startEdit(tag);
        component.editName = newName;

        tagsServiceSpy.renameTag.mockReturnValue(of({ success: true }));

        const oldName = tag.name; // Store old name before optimistic update
        component.saveRename(tag);

        expect(tagsServiceSpy.renameTag).toHaveBeenCalledWith(oldName, newName);
        expect(tag.name).toBe(newName);
        expect(component.editingTag).toBeNull();
    });

    it('should handle rename error', () => {
        fixture.detectChanges();
        const tag = { name: 'Python', count: 3 };

        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => { });
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        component.startEdit(tag);
        component.editName = 'PyScript';
        tagsServiceSpy.renameTag.mockReturnValue(throwError(() => new Error('Rename error')));

        component.saveRename(tag);

        expect(tagsServiceSpy.renameTag).toHaveBeenCalled();
        expect(alertSpy).toHaveBeenCalledWith('Failed to rename tag.');
        expect(tag.name).toBe('Python');
    });

    it('should delete tag confirmed', () => {
        fixture.detectChanges();
        const tag = mockTags[1];
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        tagsServiceSpy.deleteTag.mockReturnValue(of({ success: true }));

        component.deleteTag(tag);

        expect(tagsServiceSpy.deleteTag).toHaveBeenCalledWith(tag.name);
        expect(tagsServiceSpy.getAllTags).toHaveBeenCalledTimes(2); // Init + Reload
    });

    it('should cancel delete', () => {
        fixture.detectChanges();
        const tag = mockTags[1];
        vi.spyOn(window, 'confirm').mockReturnValue(false);

        component.deleteTag(tag);

        expect(tagsServiceSpy.deleteTag).not.toHaveBeenCalled();
    });

    it('should not rename if name is same or empty', () => {
        fixture.detectChanges();
        const tag = { name: 'old', count: 5 };
        component.editingTag = 'old';
        component.editName = 'old';

        component.saveRename(tag);
        expect(component.editingTag).toBeNull();
        expect(tagsServiceSpy.renameTag).not.toHaveBeenCalled();

        component.editingTag = 'old';
        component.editName = '';
        component.saveRename(tag);
        expect(component.editingTag).toBeNull();
        expect(tagsServiceSpy.renameTag).not.toHaveBeenCalled();
    });

    it('should handle delete error', () => {
        fixture.detectChanges();
        const tag = { name: 'test', count: 1 };
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => { });
        vi.spyOn(console, 'error').mockImplementation(() => { }); // Mock console.error to prevent noise

        tagsServiceSpy.deleteTag.mockReturnValue(throwError(() => new Error('Delete error')));

        component.deleteTag(tag);
        expect(tagsServiceSpy.deleteTag).toHaveBeenCalledWith(tag.name);
        expect(alertSpy).toHaveBeenCalledWith('Failed to delete tag.');
        expect(tagsServiceSpy.getAllTags).toHaveBeenCalledTimes(1); // Only initial load, no reload on error
    });
});
