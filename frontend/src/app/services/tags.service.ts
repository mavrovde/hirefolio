import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface TagStat {
  name: string;
  count: number;
}

@Injectable({
  providedIn: 'root',
})
export class TagsService {
  private apiUrl = `${environment.apiUrl}/api/tags`;

  constructor(private http: HttpClient) {}

  getAllTags(): Observable<TagStat[]> {
    return this.http.get<TagStat[]>(this.apiUrl);
  }

  renameTag(oldName: string, newName: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/${oldName}`, { new_name: newName });
  }

  deleteTag(name: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${name}`);
  }
}
