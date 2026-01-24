import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { LoginComponent } from './components/admin/login/login.component';
import { AdminLayoutComponent } from './components/admin/layout/admin-layout.component';
import { DashboardComponent } from './components/admin/dashboard/dashboard.component';
import { PostListComponent } from './components/admin/post-list/post-list.component';
import { HomeComponent } from './components/home/home.component';

export const routes: Routes = [
    {
        path: '',
        component: HomeComponent
    },
    {
        path: 'admin/login',
        component: LoginComponent
    },
    {
        path: 'admin/posts/new',
        loadComponent: () => import('./components/admin/post-editor/post-editor.component').then(m => m.PostEditorComponent),
        canActivate: [authGuard]
    },
    {
        path: 'admin/posts/edit/:slug',
        loadComponent: () => import('./components/admin/post-editor/post-editor.component').then(m => m.PostEditorComponent),
        canActivate: [authGuard]
    },
    {
        path: 'admin/tags',
        loadComponent: () => import('./components/admin/tag-manager/tag-manager.component').then(m => m.TagManagerComponent),
        canActivate: [authGuard]
    },
    {
        path: 'admin',
        component: AdminLayoutComponent,
        canActivate: [authGuard],
        data: { requireAdmin: true },
        children: [
            {
                path: '',
                redirectTo: 'dashboard',
                pathMatch: 'full'
            },
            {
                path: 'dashboard',
                component: DashboardComponent
            },
            {
                path: 'posts',
                component: PostListComponent
            },
            {
                path: 'posts/new',
                loadComponent: () => import('./components/admin/post-editor/post-editor.component').then(m => m.PostEditorComponent)
            },
            {
                path: 'posts/edit/:slug',
                loadComponent: () => import('./components/admin/post-editor/post-editor.component').then(m => m.PostEditorComponent)
            }
        ]
    }
];
