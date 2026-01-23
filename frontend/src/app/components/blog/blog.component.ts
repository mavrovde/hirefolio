import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BlogService, BlogPost } from '../../services/blog.service';
import { Observable } from 'rxjs';
import { TranslatePipe } from '../../pipes/translate.pipe';

@Component({
    selector: 'app-blog',
    standalone: true,
    imports: [CommonModule, TranslatePipe],
    templateUrl: './blog.component.html',
    styleUrls: ['./blog.component.css']
})
export class BlogComponent implements OnInit {
    posts$: Observable<BlogPost[]> | null = null;
    expandedPostId: string | null = null;

    constructor(private blogService: BlogService) { }

    ngOnInit() {
        this.posts$ = this.blogService.getPosts();
    }

    togglePost(id: string) {
        if (this.expandedPostId === id) {
            this.expandedPostId = null;
        } else {
            this.expandedPostId = id;
        }
    }
}
