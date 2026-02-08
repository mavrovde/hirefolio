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
    component: HomeComponent,
  },
  {
    path: 'llm',
    loadComponent: () =>
      import('./components/llm/llm.component').then((m) => m.LlmComponent),
  },
  {
    path: 'blog',
    loadComponent: () =>
      import('./components/blog/blog.component').then((m) => m.BlogComponent),
  },
  {
    path: 'blog/:slug',
    loadComponent: () =>
      import('./components/blog/blog-post/blog-post.component').then(
        (m) => m.BlogPostComponent
      ),
  },
  {
    path: 'cv',
    loadComponent: () =>
      import('./components/cv/cv.component').then((m) => m.CvComponent),
  },
  {
    path: 'admin/login',
    component: LoginComponent,
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
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        component: DashboardComponent,
      },
      {
        path: 'posts',
        component: PostListComponent,
      },
      {
        path: 'posts/new',
        loadComponent: () =>
          import('./components/admin/post-editor/post-editor.component').then(
            (m) => m.PostEditorComponent,
          ),
      },
      {
        path: 'posts/edit/:id',
        loadComponent: () =>
          import('./components/admin/post-editor/post-editor.component').then(
            (m) => m.PostEditorComponent,
          ),
      },
      {
        path: 'cv-manager',
        loadComponent: () =>
          import('./components/admin/cv-manager/cv-manager.component').then(
            (m) => m.CvManagerComponent,
          ),
      },
      {
        path: 'tag-manager',
        loadComponent: () =>
          import('./components/admin/tag-manager/tag-manager.component').then(
            (m) => m.TagManagerComponent,
          ),
      },

      {
        path: 'profile',
        loadComponent: () =>
          import('./components/admin/profile/profile').then(
            (m) => m.ProfileComponent,
          ),
      },
    ],
  },
];
