import { BehaviorSubject } from 'rxjs';

export interface PaginationParams {
    page: number;
    pageSize: number;
    sortBy: string | null;
    sortOrder: 'asc' | 'desc';
    search: string | null;
}

/**
 * Server-side TableHelper manages pagination state and emits events
 * when the component needs to fetch new data from the backend.
 */
export class ServerTableHelper<T> {
    // Displayed items from server
    items: T[] = [];

    // Pagination state
    currentPage = 1;
    pageSize = 10;
    totalItems = 0;
    totalPages = 1;

    // Sorting state
    sortBy: string | null = null;
    sortOrder: 'asc' | 'desc' = 'desc';

    // Search state
    searchText: string | null = null;

    // Observable for components to subscribe to parameter changes
    params$ = new BehaviorSubject<PaginationParams>(this.getParams());

    constructor(
        initialSortBy: string | null = null,
        initialSortOrder: 'asc' | 'desc' = 'desc',
        initialPageSize: number = 10
    ) {
        this.sortBy = initialSortBy;
        this.sortOrder = initialSortOrder;
        this.pageSize = initialPageSize;
    }

    /**
     * Update table with paginated response from server
     */
    setData(response: {
        items: T[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
    }) {
        this.items = response.items || [];
        this.totalItems = response.total;
        this.currentPage = response.page;
        this.pageSize = response.page_size;
        this.totalPages = response.total_pages;
    }

    /**
     * Set search text and reset to first page
     */
    setSearch(text: string | null) {
        this.searchText = text;
        this.currentPage = 1;
        this.emitParams();
    }

    /**
     * Toggle sort or set new sort field
     */
    toggleSort(field: string) {
        if (this.sortBy === field) {
            this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortBy = field;
            this.sortOrder = 'asc';
        }
        this.currentPage = 1; // Reset to first page on sort change
        this.emitParams();
    }

    /**
     * Go to specific page
     */
    setPage(page: number) {
        if (page >= 1 && page <= this.totalPages) {
            this.currentPage = page;
            this.emitParams();
        }
    }

    /**
     * Go to next page
     */
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.currentPage++;
            this.emitParams();
        }
    }

    /**
     * Go to previous page
     */
    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.emitParams();
        }
    }

    /**
     * Get current pagination parameters for API call
     */
    getParams(): PaginationParams {
        return {
            page: this.currentPage,
            pageSize: this.pageSize,
            sortBy: this.sortBy,
            sortOrder: this.sortOrder,
            search: this.searchText,
        };
    }

    /**
     * Emit parameter change event
     */
    private emitParams() {
        this.params$.next(this.getParams());
    }

    /**
     * Check if a field is currently sorted
     */
    isSorted(field: string): boolean {
        return this.sortBy === field;
    }

    /**
     * Get sort direction for a field (if sorted)
     */
    getSortDirection(field: string): 'asc' | 'desc' | null {
        return this.sortBy === field ? this.sortOrder : null;
    }
}
