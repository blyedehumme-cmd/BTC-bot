const rawBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000/api';
const normalizedBackendUrl = rawBackendUrl.replace(/\/+$/, '');
export const API_BASE_URL = normalizedBackendUrl.endsWith('/api') ? normalizedBackendUrl : `${normalizedBackendUrl}/api`;
