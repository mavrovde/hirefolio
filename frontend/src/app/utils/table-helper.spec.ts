import { describe, it, expect, beforeEach } from 'vitest';
import { TableHelper } from './table-helper';

interface TestItem {
    id: number;
    name: string;
    value: number;
}

describe('TableHelper', () => {
    let helper: TableHelper<TestItem>;
    const mockData: TestItem[] = [
        { id: 1, name: 'Alpha', value: 100 },
        { id: 2, name: 'Beta', value: 200 },
        { id: 3, name: 'Gamma', value: 150 },
        { id: 4, name: 'Delta', value: 50 },
        { id: 5, name: 'Epsilon', value: 175 },
    ];

    beforeEach(() => {
        helper = new TableHelper<TestItem>();
    });

    describe('setData', () => {
        it('should set data and initialize pagination', () => {
            helper.setData(mockData);

            expect(helper.filteredItems).toEqual(mockData);
            expect(helper.paginatedItems.length).toBe(5); // Default page size is 10
            expect(helper.totalPages).toBe(1);
            expect(helper.currentPage).toBe(1);
        });

        it('should handle empty array', () => {
            helper.setData([]);

            expect(helper.filteredItems).toEqual([]);
            expect(helper.paginatedItems).toEqual([]);
            expect(helper.totalPages).toBe(1);
        });

        it('should handle null/undefined gracefully', () => {
            helper.setData(null as any);

            expect(helper.filteredItems).toEqual([]);
            expect(helper.paginatedItems).toEqual([]);
        });
    });

    describe('setSearch', () => {
        beforeEach(() => {
            helper.setData(mockData);
        });

        it('should filter items by search text', () => {
            helper.setSearch('alpha', ['name']);

            expect(helper.filteredItems.length).toBe(1);
            expect(helper.filteredItems[0].name).toBe('Alpha');
        });

        it('should be case-insensitive', () => {
            helper.setSearch('BETA', ['name']);

            expect(helper.filteredItems.length).toBe(1);
            expect(helper.filteredItems[0].name).toBe('Beta');
        });

        it('should search across multiple fields', () => {
            helper.setSearch('2', ['id', 'name', 'value']);

            expect(helper.filteredItems.length).toBe(1); // Only id:2 matches '2' as string
        });


        it('should reset to page 1 after search', () => {
            helper.pageSize = 2;
            helper.setData(mockData);
            helper.setPage(2);

            expect(helper.currentPage).toBe(2);

            helper.setSearch('a', ['name']);

            expect(helper.currentPage).toBe(1);
        });

        it('should handle empty search text', () => {
            helper.setSearch('', ['name']);

            expect(helper.filteredItems).toEqual(mockData);
        });

        it('should handle null/undefined values in items', () => {
            const dataWithNulls = [
                { id: 1, name: 'Test', value: null as any },
                { id: 2, name: null as any, value: 100 },
            ];
            helper.setData(dataWithNulls);

            helper.setSearch('100', ['value']);

            expect(helper.filteredItems.length).toBe(1);
            expect(helper.filteredItems[0].id).toBe(2);
        });
    });

    describe('toggleSort', () => {
        beforeEach(() => {
            helper.setData(mockData);
        });

        it('should sort ascending on first click', () => {
            helper.toggleSort('name');

            expect(helper.sortField).toBe('name');
            expect(helper.sortDirection).toBe('asc');
            expect(helper.filteredItems[0].name).toBe('Alpha');
            expect(helper.filteredItems[4].name).toBe('Gamma');
        });

        it('should toggle to descending on second click', () => {
            helper.toggleSort('name');
            helper.toggleSort('name');

            expect(helper.sortDirection).toBe('desc');
            expect(helper.filteredItems[0].name).toBe('Gamma');
            expect(helper.filteredItems[4].name).toBe('Alpha');
        });

        it('should reset to ascending when changing field', () => {
            helper.toggleSort('name');
            helper.toggleSort('name'); // Now desc
            helper.toggleSort('value'); // Should reset to asc

            expect(helper.sortField).toBe('value');
            expect(helper.sortDirection).toBe('asc');
            expect(helper.filteredItems[0].value).toBe(50);
        });

        it('should sort numbers correctly', () => {
            helper.toggleSort('value');

            expect(helper.filteredItems[0].value).toBe(50);
            expect(helper.filteredItems[1].value).toBe(100);
            expect(helper.filteredItems[4].value).toBe(200);
        });

        it('should handle equal values', () => {
            const dataWithDuplicates = [
                { id: 1, name: 'Same', value: 100 },
                { id: 2, name: 'Same', value: 100 },
            ];
            helper.setData(dataWithDuplicates);

            helper.toggleSort('name');

            expect(helper.filteredItems.length).toBe(2);
        });
    });

    describe('setPage', () => {
        beforeEach(() => {
            helper.pageSize = 2;
            helper.setData(mockData);
        });

        it('should change page when valid', () => {
            helper.setPage(2);

            expect(helper.currentPage).toBe(2);
            expect(helper.paginatedItems.length).toBe(2);
            expect(helper.paginatedItems[0].id).toBe(3);
        });

        it('should not change page below 1', () => {
            helper.setPage(0);

            expect(helper.currentPage).toBe(1);
        });

        it('should not change page above total pages', () => {
            helper.setPage(10);

            expect(helper.currentPage).toBe(1);
        });

        it('should update paginated items correctly', () => {
            expect(helper.paginatedItems.length).toBe(2);
            expect(helper.paginatedItems[0].id).toBe(1);

            helper.setPage(2);

            expect(helper.paginatedItems.length).toBe(2);
            expect(helper.paginatedItems[0].id).toBe(3);
        });

        it('should handle last page with fewer items', () => {
            helper.setPage(3);

            expect(helper.currentPage).toBe(3);
            expect(helper.paginatedItems.length).toBe(1); // Only 1 item on page 3
            expect(helper.paginatedItems[0].id).toBe(5);
        });
    });

    describe('combined operations', () => {
        beforeEach(() => {
            helper.pageSize = 2;
            helper.setData(mockData);
        });

        it('should handle search + sort + pagination', () => {
            helper.setSearch('a', ['name']); // Alpha, Beta, Gamma, Delta
            helper.toggleSort('value'); // Sort by value asc
            helper.setPage(2);

            expect(helper.filteredItems.length).toBe(4);
            expect(helper.currentPage).toBe(2);
            expect(helper.paginatedItems.length).toBe(2);
            expect(helper.paginatedItems[0].name).toBe('Gamma'); // value: 150
        });

        it('should adjust current page when filtered items decrease', () => {
            helper.setPage(3); // Page 3 of 3

            helper.setSearch('a', ['name']); // Reduces to 4 items, 2 pages

            expect(helper.currentPage).toBe(1); // Reset to 1 after search
            expect(helper.totalPages).toBe(2);
        });

        it('should recalculate total pages after filtering', () => {
            expect(helper.totalPages).toBe(3); // 5 items, page size 2

            helper.setSearch('Alpha', ['name']); // 1 item

            expect(helper.totalPages).toBe(1);
        });
    });

    describe('pagination calculations', () => {
        it('should calculate total pages correctly', () => {
            helper.pageSize = 3;
            helper.setData(mockData); // 5 items

            expect(helper.totalPages).toBe(2); // ceil(5/3) = 2
        });

        it('should handle page size larger than data', () => {
            helper.pageSize = 100;
            helper.setData(mockData);

            expect(helper.totalPages).toBe(1);
            expect(helper.paginatedItems.length).toBe(5);
        });

        it('should ensure minimum of 1 page', () => {
            helper.setData([]);

            expect(helper.totalPages).toBe(1);
        });
    });
});
