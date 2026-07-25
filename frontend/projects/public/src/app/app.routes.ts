import { Routes } from '@angular/router';
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
];
