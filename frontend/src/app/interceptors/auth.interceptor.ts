import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
    const authService = inject(AuthService);
    const router = inject(Router);
    const token = authService.getToken();

    // Clone request and add authorization header if token exists AND not logging in
    if (token && !req.url.includes('/api/auth/login')) {
        req = req.clone({
            setHeaders: {
                Authorization: `Bearer ${token}`
            }
        });
    }

    return next(req).pipe(
        catchError((error) => {
            // Handle 401 Unauthorized (unless it's the login request itself)
            if (error.status === 401 && !req.url.includes('/api/auth/login')) {
                authService.logout();
                router.navigate(['/admin/login']);
            }

            // Handle 403 Forbidden
            if (error.status === 403) {
                console.error('Access denied: insufficient permissions');
            }

            return throwError(() => error);
        })
    );
};
