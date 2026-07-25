export const API_PREFIX = process.env['API_PREFIX'] || '/api/app';

export const config = {
    baseUrl: process.env['BASE_URL'] || 'http://localhost:4200', // Angular dev server default (public site)
    adminUrl: process.env['ADMIN_BASE_URL'] || 'http://admin.localhost', // Admin SPA origin
    adminUsername: process.env['ADMIN_USERNAME'] || 'admin',
    adminPassword: process.env['ADMIN_PASSWORD'] || 'admin',
};
