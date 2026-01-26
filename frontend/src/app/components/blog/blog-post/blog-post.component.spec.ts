import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BlogPostComponent } from './blog-post.component';
import { BlogService } from '../../../services/blog.service';
import { ActivatedRoute, Router } from '@angular/router';
import { of, throwError, BehaviorSubject } from 'rxjs';
import { MockTranslatePipe } from '../../../testing/mock-translate.pipe';
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('BlogPostComponent', () => {
    let component: BlogPostComponent;
    let fixture: ComponentFixture<BlogPostComponent>;
    let blogServiceSpy: any;
    let routerSpy: any;
    let paramMapSubject: BehaviorSubject<any>;

    const mockPost = {
        id: 1,
        title: 'Test Post',
        slug: 'test-post',
        date: '2026-01-24',
        summary: 'Summary',
        content: '<p>Content</p>',
        language: 'en',
        tags: ['tag1'],
    };

    beforeEach(async () => {
        blogServiceSpy = {
            getPost: vi.fn(),
        };

        routerSpy = {
            navigate: vi.fn(),
        };

        paramMapSubject = new BehaviorSubject({ get: (key: string) => (key === 'slug' ? 'test-post' : null) });

        await TestBed.configureTestingModule({
            imports: [BlogPostComponent, MockTranslatePipe],
            providers: [
                { provide: BlogService, useValue: blogServiceSpy },
                { provide: Router, useValue: routerSpy },
                {
                    provide: ActivatedRoute,
                    useValue: { paramMap: paramMapSubject.asObservable() }
                },
            ],
        }).compileComponents();

        fixture = TestBed.createComponent(BlogPostComponent);
        component = fixture.componentInstance;
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should load post from route slug', () => {
        blogServiceSpy.getPost.mockReturnValue(of(mockPost));
        fixture.detectChanges();

        expect(blogServiceSpy.getPost).toHaveBeenCalledWith('test-post');
        // Verify post data is in stream
        component.post$?.subscribe((post) => {
            expect(post).toEqual(mockPost);
        });
    });

    it('should redirect home if slug is missing', () => {
        // Update subject to emit empty slug
        paramMapSubject.next({ get: () => null });

        // We need new subscription, so re-init component or just trigger ngOnChanges if input based? 
        // ngOnInit runs once. We need to trigger it relative to the stream emission.
        // Since ngOnInit subscribes to paramMap, pushing a new value should trigger the pipeline.

        // NOTE: The previous subscription from beforeEach (if any) might interfere if we don't manage subscriptions, 
        // but in this test case, we haven't called fixture.detectChanges() yet in THIS test, 
        // except if we shared fixture. But beforeEach creates new fixture.

        // So:
        // 1. Component created (ctor)
        // 2. paramMapSubject has initial value 'test-post' (set in beforeEach) - wait, we want to start with null?
        //    Actually, we can just push null before ngOnInit (first detectChanges).

        fixture.detectChanges(); // This triggers ngOnInit with 'test-post' from beforeEach... wait
        // If we want to test missing slug, we should ensure the FIRST emission is null, OR that it handles subsequent updates.
        // Our component subscribes to paramMap. 

        // Let's reset the subject before detectChanges for this test.
        paramMapSubject.next({ get: () => null });

        // Re-subscribe? No, ngOnInit hasn't run yet if we didn't call detectChanges.
        // Wait, TestBed.createComponent creates the instance but doesn't run ngOnInit.
        // fixture.detectChanges() runs ngOnInit.

        // So if we update subject BEFORE detectChanges, it should pick up the latest value.
        // BehaviorSubject emits current value on subscription.

        // But we initialized it with 'test-post'.
        // Let's create a fresh subject or just update it.

        // Actually, simply:
        fixture.detectChanges(); // ngOnInit runs, sees null (because we called next(null) above?)

        // Wait, I updated it after beforeEach but before detectChanges. 
        // Yes, BehaviorSubject holds the value. When ngOnInit subscribes, it gets the LATEST value.

        expect(routerSpy.navigate).toHaveBeenCalledWith(['/']);
    });

    it('should redirect home on service error', () => {
        blogServiceSpy.getPost.mockReturnValue(throwError(() => new Error('Not found')));
        fixture.detectChanges();

        expect(routerSpy.navigate).toHaveBeenCalledWith(['/']);
    });

    it('should navigate back on goBack()', () => {
        component.goBack();
        expect(routerSpy.navigate).toHaveBeenCalledWith(['/'], { fragment: 'blog' });
    });
});
