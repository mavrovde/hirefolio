import { TestBed } from '@angular/core/testing';
import { provideHttpClient, HttpErrorResponse } from '@angular/common/http';
import {
    HttpTestingController,
    provideHttpClientTesting,
} from '@angular/common/http/testing';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { InteractionService, InteractionResponse } from './interaction.service';
import { environment } from '../../environments/environment';

describe('InteractionService', () => {
    let service: InteractionService;
    let httpMock: HttpTestingController;
    const url = `${environment.apiUrl}${environment.apiPrefix}/interactions/contact`;

    beforeEach(() => {
        TestBed.configureTestingModule({
            providers: [provideHttpClient(), provideHttpClientTesting(), InteractionService],
        });
        service = TestBed.inject(InteractionService);
        httpMock = TestBed.inject(HttpTestingController);
    });

    afterEach(() => httpMock.verify());

    it('POSTs the contact payload and returns the created interaction', () => {
        const payload = { name: 'Rita', email: 'r@a.example', company: 'A', message: 'Hi' };
        let result: InteractionResponse | undefined;
        service.submitContact(payload).subscribe((r) => (result = r));

        const req = httpMock.expectOne(url);
        expect(req.request.method).toBe('POST');
        expect(req.request.body).toEqual(payload);
        req.flush({ id: 'x', source: 'contact_form', status: 'new', ...payload, created_at: 'now' });
        expect(result!.status).toBe('new');
    });

    it('propagates server errors to the caller', () => {
        let error: HttpErrorResponse | undefined;
        service
            .submitContact({ name: 'R', email: 'r@a.example', message: 'Hi' })
            .subscribe({ error: (e) => (error = e) });
        httpMock.expectOne(url).flush('nope', { status: 500, statusText: 'Server Error' });
        expect(error!.status).toBe(500);
    });
});
