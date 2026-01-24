import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { filter, map, take } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route, state) => {
    const authService = inject(AuthService);
    const router = inject(Router);

    if (!authService.isAuthenticated()) {
        router.navigate(['/admin/login'], { queryParams: { returnUrl: state.url } });
        return false;
    }

    // specific check for admin route
    if (route.data?.['requireAdmin']) {
        return authService.currentUser$.pipe(
            filter(user => user !== null || !authService.isAuthenticated()), // Wait for user to load if auth'd
            take(1),
            map(user => {
                if (user?.is_admin) {
                    return true;
                }
                // User loaded but not admin -> redirect
                router.navigate(['/']); // or login
                return false;
            })
        );
    }

    return true;
};
