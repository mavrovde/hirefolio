import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { TagsService, TagStat } from './tags.service';
import { environment } from '../../environments/environment';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('TagsService', () => {
    let service: TagsService;
    let httpMock: HttpTestingController;

    beforeEach(() => {
        TestBed.configureTestingModule({
            imports: [HttpClientTestingModule],
            providers: [TagsService],
        });
        service = TestBed.inject(TagsService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
        httpMock.verify();
    });

    it('should be created', () => {
        expect(service).toBeTruthy();
    });

    it('should get all tags', () => {
        const mockTags: TagStat[] = [
            { name: 'Angular', count: 5 },
            { name: 'Python', count: 3 },
        ];

        service.getAllTags().subscribe((tags) => {
            expect(tags).toEqual(mockTags);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/tags`);
        expect(req.request.method).toBe('GET');
        req.flush(mockTags);
    });

    it('should rename tag', () => {
        const oldName = 'Angular';
        const newName = 'AngularJS';
        const mockResponse = { success: true };

        service.renameTag(oldName, newName).subscribe((response) => {
            expect(response).toEqual(mockResponse);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/tags/${oldName}`);
        expect(req.request.method).toBe('PUT');
        expect(req.request.body).toEqual({ new_name: newName });
        req.flush(mockResponse);
    });

    it('should delete tag', () => {
        const tagName = 'Python';
        const mockResponse = { success: true };

        service.deleteTag(tagName).subscribe((response) => {
            expect(response).toEqual(mockResponse);
        });

        const req = httpMock.expectOne(`${environment.apiUrl}/api/tags/${tagName}`);
        expect(req.request.method).toBe('DELETE');
        req.flush(mockResponse);
    });
});
