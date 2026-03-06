import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
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
    private cdr = inject(ChangeDetectorRef);

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

    async syncProfile(): Promise<void> {
        this.isSyncingProfile = true;
        this.statusMessage = 'Scanning profile...';
        try {
            const data = await this.linkedinService.syncProfile();
            console.log('[DEBUG] PROFILE RECEIVED:', JSON.stringify(data));
            this.profileData = data;
            this.isSyncingProfile = false;
            this.statusMessage = 'Profile synced successfully.';
            this.clearMessageAfterDelay();
        } catch (err: any) {
            this.isSyncingProfile = false;
            console.error('Error syncing profile:', err);
            this.statusMessage = 'Error syncing profile.';
        } finally {
            this.cdr.detectChanges();
        }
    }

    async fetchPosts(): Promise<void> {
        this.isFetchingPosts = true;
        this.statusMessage = 'Fetching posts...';
        try {
            const posts = await this.linkedinService.getPosts();
            console.log('[DEBUG] POSTS RECEIVED:', JSON.stringify(posts));
            this.posts = posts;
            this.isFetchingPosts = false;
            this.statusMessage = `Fetched ${posts.length} posts.`;
            this.clearMessageAfterDelay();
        } catch (err: any) {
            this.isFetchingPosts = false;
            console.error('Error fetching posts:', err);
            this.statusMessage = err.message || 'Error fetching posts.';
        } finally {
            this.cdr.detectChanges();
        }
    }

    async transferPost(post: LinkedInPost): Promise<void> {
        if (this.transferringPostId) return;

        this.transferringPostId = post.id;
        this.statusMessage = `Transferring post...`;
        try {
            const res = await this.linkedinService.transferPost(post);
            this.transferringPostId = null;
            this.statusMessage = `Transferred as draft ${res.id}`;
            this.posts = this.posts.filter(p => p.id !== post.id);
            this.clearMessageAfterDelay();
        } catch (err: any) {
            this.transferringPostId = null;
            console.error('Error transferring post:', err);
            this.statusMessage = 'Error transferring post.';
        } finally {
            this.cdr.detectChanges();
        }
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
