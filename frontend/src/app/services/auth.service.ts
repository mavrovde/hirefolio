import { Injectable } from '@angular/core';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable, tap, switchMap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface LoginResponse {
    access_token: string;
    token_type: string;
    expires_in: number;
}

export interface User {
    id: number;
    username: string;
    email: string;
    is_admin: boolean;
}

@Injectable({
    providedIn: 'root'
})
export class AuthService {
    private readonly TOKEN_KEY = 'auth_token';
    private readonly apiUrl = environment.apiUrl;

    private currentUserSubject = new BehaviorSubject<User | null>(null);
    public currentUser$ = this.currentUserSubject.asObservable();

    private isInitializingSubject = new BehaviorSubject<boolean>(true);
    public isInitializing$ = this.isInitializingSubject.asObservable();

    constructor(private http: HttpClient) {
        // Load user on service initialization if token exists
        if (this.getToken()) {
            this.loadCurrentUser();
        } else {
            this.isInitializingSubject.next(false);
        }
    }

    login(username: string, password: string): Observable<User> {
        const body = new HttpParams()
            .set('username', username)
            .set('password', password);

        return this.http.post<LoginResponse>(`${this.apiUrl}/api/auth/login`, body)
            .pipe(
                // Wait for the user to be loaded before completing the login observable
                switchMap(response => {
                    this.setToken(response.access_token);
                    return this.fetchCurrentUser();
                })
            );
    }

    logout(): void {
        this.removeToken();
        this.currentUserSubject.next(null);
    }

    getToken(): string | null {
        return localStorage.getItem(this.TOKEN_KEY);
    }

    private setToken(token: string): void {
        localStorage.setItem(this.TOKEN_KEY, token);
    }

    private removeToken(): void {
        localStorage.removeItem(this.TOKEN_KEY);
    }

    isAuthenticated(): boolean {
        return !!this.getToken();
    }

    isAdmin(): boolean {
        const user = this.currentUserSubject.value;
        return user?.is_admin ?? false;
    }

    getCurrentUser(): User | null {
        return this.currentUserSubject.value;
    }

    private loadCurrentUser(): void {
        this.fetchCurrentUser().subscribe();
    }

    private fetchCurrentUser(): Observable<User> {
        return this.http.get<User>(`${this.apiUrl}/api/auth/me`)
            .pipe(
                tap({
                    next: (user) => {
                        this.currentUserSubject.next(user);
                        this.isInitializingSubject.next(false);
                    },
                    error: (error) => {
                        // Only logout on definitive auth errors
                        if (error.status === 401 || error.status === 403) {
                            this.logout();
                        }
                        this.isInitializingSubject.next(false);
                    }
                })
            );
    }
}
