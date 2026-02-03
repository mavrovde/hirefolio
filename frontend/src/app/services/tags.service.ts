import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface TagStat {
  name: string;
  count: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
@Injectable({
  providedIn: 'root',
})
export class TagsService {
  private apiUrl = `${environment.apiUrl}/api/tags`;

  constructor(private http: HttpClient) { }

  getAllTags(
    page: number = 1,
    pageSize: number = 10,
    sortBy: string = 'count',
    sortOrder: 'asc' | 'desc' = 'desc',
    search: string | null = null
  ): Observable<PaginatedResponse<TagStat>> {
    const params: any = {
      page: page.toString(),
      page_size: pageSize.toString(),
      sort_by: sortBy,
      sort_order: sortOrder
    };
    if (search) {
      params.search = search;
    }
    return this.http.get<PaginatedResponse<TagStat>>(this.apiUrl, { params });
  }

  renameTag(oldName: string, newName: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/${oldName}`, { new_name: newName });
  }

  deleteTag(name: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${name}`);
  }
}
