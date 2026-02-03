import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ServerTableHelper } from './table-helper-server';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

describe('ServerTableHelper', () => {
    interface TestItem {
        id: number;
        name: string;
        value: number;
    }

    let helper: ServerTableHelper<TestItem>;

    beforeEach(() => {
        helper = new ServerTableHelper<TestItem>('name', 'asc', 5);
    });

    describe('Initialization', () => {
        it('should initialize with correct defaults', () => {
            expect(helper.currentPage).toBe(1);
            expect(helper.pageSize).toBe(5);
            expect(helper.sortBy).toBe('name');
            expect(helper.sortOrder).toBe('asc');
            expect(helper.searchText).toBeNull();
            expect(helper.items).toEqual([]);
            expect(helper.totalItems).toBe(0);
            expect(helper.totalPages).toBe(1);
        });

        it('should emit initial params on creation', async () => {
            const newHelper = new ServerTableHelper<TestItem>();
            const params = await firstValueFrom(newHelper.params$);
            expect(params.page).toBe(1);
            expect(params.pageSize).toBe(10);
            expect(params.sortBy).toBeNull();
            expect(params.sortOrder).toBe('desc');
            expect(params.search).toBeNull();
        });
    });

    describe('setData', () => {
        it('should update table with paginated response', () => {
            const response = {
                items: [{ id: 1, name: 'Test', value: 100 }],
                total: 15,
                page: 2,
                page_size: 5,
                total_pages: 3,
            };

            helper.setData(response);

            expect(helper.items).toEqual(response.items);
            expect(helper.totalItems).toBe(15);
            expect(helper.currentPage).toBe(2);
            expect(helper.pageSize).toBe(5);
            expect(helper.totalPages).toBe(3);
        });

        it('should handle empty response', () => {
            const response = {
                items: [],
                total: 0,
                page: 1,
                page_size: 10,
                total_pages: 1,
            };

            helper.setData(response);

            expect(helper.items).toEqual([]);
            expect(helper.totalItems).toBe(0);
            expect(helper.totalPages).toBe(1);
        });
    });

    describe('setSearch', () => {
        it('should update search text and reset to page 1', () => {
            helper.currentPage = 3;
            helper.setSearch('test');
            expect(helper.searchText).toBe('test');
            expect(helper.currentPage).toBe(1);
        });

        it('should handle null search', () => {
            helper.setSearch('test');
            helper.setSearch(null);
            expect(helper.searchText).toBeNull();
        });

        it('should emit params on search', () => {
            const spy = vi.fn();
            helper.params$.subscribe(spy);
            const initialCalls = spy.mock.calls.length;
            helper.setSearch('query');
            expect(spy).toHaveBeenCalledTimes(initialCalls + 1);
        });
    });

    describe('toggleSort', () => {
        it('should toggle direction when same field', () => {
            helper.sortBy = 'name';
            helper.sortOrder = 'asc';
            helper.toggleSort('name');
            expect(helper.sortBy).toBe('name');
            expect(helper.sortOrder).toBe('desc');
        });

        it('should set new field with asc direction', () => {
            helper.sortBy = 'name';
            helper.sortOrder = 'desc';
            helper.toggleSort('value');
            expect(helper.sortBy).toBe('value');
            expect(helper.sortOrder).toBe('asc');
            expect(helper.currentPage).toBe(1);
        });

        it('should reset to page 1 on sort change', () => {
            helper.currentPage = 3;
            helper.toggleSort('value');
            expect(helper.currentPage).toBe(1);
        });
    });

    describe('setPage', () => {
        beforeEach(() => {
            helper.totalPages = 5;
        });

        it('should change page when valid', () => {
            helper.setPage(3);
            expect(helper.currentPage).toBe(3);
        });

        it('should not change page when invalid', () => {
            helper.setPage(10);
            expect(helper.currentPage).toBe(1);
        });

        it('should not change page when less than 1', () => {
            helper.setPage(0);
            expect(helper.currentPage).toBe(1);
        });

        it('should emit params only on valid page change', () => {
            const spy = vi.fn();
            helper.params$.subscribe(spy);

            const initialCalls = spy.mock.calls.length;
            helper.setPage(100); // Invalid
            expect(spy).toHaveBeenCalledTimes(initialCalls);
        });
    });

    describe('nextPage', () => {
        beforeEach(() => {
            helper.totalPages = 5;
            helper.currentPage = 2;
        });

        it('should go to next page', () => {
            helper.nextPage();
            expect(helper.currentPage).toBe(3);
        });

        it('should not go beyond last page', () => {
            helper.currentPage = 5;
            helper.nextPage();
            expect(helper.currentPage).toBe(5);
        });
    });

    describe('prevPage', () => {
        beforeEach(() => {
            helper.currentPage = 3;
            helper.totalPages = 5;
        });

        it('should go to previous page', () => {
            helper.prevPage();
            expect(helper.currentPage).toBe(2);
        });

        it('should not go below page 1', () => {
            helper.currentPage = 1;
            helper.prevPage();
            expect(helper.currentPage).toBe(1);
        });
    });

    describe('getParams', () => {
        it('should return current pagination parameters', () => {
            helper.currentPage = 2;
            helper.pageSize = 20;
            helper.sortBy = 'value';
            helper.sortOrder = 'desc';
            helper.searchText = 'test';

            const params = helper.getParams();

            expect(params.page).toBe(2);
            expect(params.pageSize).toBe(20);
            expect(params.sortBy).toBe('value');
            expect(params.sortOrder).toBe('desc');
            expect(params.search).toBe('test');
        });
    });

    describe('isSorted', () => {
        it('should return true for sorted field', () => {
            helper.sortBy = 'name';
            expect(helper.isSorted('name')).toBe(true);
        });

        it('should return false for non-sorted field', () => {
            helper.sortBy = 'name';
            expect(helper.isSorted('value')).toBe(false);
        });
    });

    describe('getSortDirection', () => {
        it('should return direction for sorted field', () => {
            helper.sortBy = 'name';
            helper.sortOrder = 'asc';
            expect(helper.getSortDirection('name')).toBe('asc');
        });

        it('should return null for non-sorted field', () => {
            helper.sortBy = 'name';
            expect(helper.getSortDirection('value')).toBeNull();
        });
    });
});
