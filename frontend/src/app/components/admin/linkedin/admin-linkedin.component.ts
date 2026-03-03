import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LinkedinService, LinkedInPost } from '../../../services/linkedin.service';

@Component({
    selector: 'app-admin-linkedin',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './admin-linkedin.component.html',
    styleUrls: ['./admin-linkedin.component.css']
})
export class AdminLinkedinComponent implements OnInit {
    private linkedinService = inject(LinkedinService);

    isSyncingProfile = false;
    isFetchingPosts = false;
    transferringPostId: string | null = null;
    activeTab: 'profile' | 'posts' = 'posts';

    profileData: any = null;
    posts: LinkedInPost[] = [];
    statusMessage: string = '';

    ngOnInit(): void {
    }

    setTab(tab: 'profile' | 'posts') {
        this.activeTab = tab;
    }

    syncProfile(): void {
        this.isSyncingProfile = true;
        this.statusMessage = 'Scanning profile...';
        this.linkedinService.syncProfile().subscribe({
            next: (data) => {
                this.profileData = data;
                this.isSyncingProfile = false;
                this.statusMessage = 'Profile synced successfully.';
                this.clearMessageAfterDelay();
            },
            error: (err) => {
                this.isSyncingProfile = false;
                console.error('Error syncing profile:', err);
                this.statusMessage = 'Error syncing profile.';
            }
        });
    }

    fetchPosts(): void {
        this.isFetchingPosts = true;
        this.statusMessage = 'Fetching posts...';
        this.linkedinService.getPosts().subscribe({
            next: (posts) => {
                this.posts = posts;
                this.isFetchingPosts = false;
                this.statusMessage = `Fetched ${posts.length} posts.`;
                this.clearMessageAfterDelay();
            },
            error: (err) => {
                this.isFetchingPosts = false;
                console.error('Error fetching posts:', err);
                this.statusMessage = 'Error fetching posts.';
            }
        });
    }

    transferPost(post: LinkedInPost): void {
        if (this.transferringPostId) return;

        this.transferringPostId = post.id;
        this.statusMessage = `Transferring post...`;
        this.linkedinService.transferPost(post).subscribe({
            next: (res) => {
                this.transferringPostId = null;
                this.statusMessage = `Transferred as draft ${res.id}`;
                this.posts = this.posts.filter(p => p.id !== post.id);
                this.clearMessageAfterDelay();
            },
            error: (err) => {
                this.transferringPostId = null;
                console.error('Error transferring post:', err);
                this.statusMessage = 'Error transferring post.';
            }
        });
    }

    clearMessageAfterDelay() {
        setTimeout(() => {
            this.statusMessage = '';
        }, 5000);
    }

    truncateText(text: string, length: number = 150): string {
        if (!text) return '';
        if (text.length <= length) return text;
        return text.substring(0, length) + '...';
    }
}
