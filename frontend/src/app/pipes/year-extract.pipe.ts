import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
    name: 'yearExtract',
    standalone: true,
})
export class YearExtractPipe implements PipeTransform {
    transform(dateString: string | null | undefined): string {
        if (!dateString) return '';
        const match = dateString.match(/\b(19|20)\d{2}\b/);
        return match ? match[0] : '';
    }
}
