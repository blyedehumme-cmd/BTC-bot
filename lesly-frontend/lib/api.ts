const defaultBackendUrl =
  process.env.NODE_ENV === 'production'
    ? 'https://lesly-backend.onrender.com/api'
    : 'http://localhost:8000/api';

const rawBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || defaultBackendUrl;
const normalizedBackendUrl = rawBackendUrl.replace(/\/+$/, '');
export const API_BASE_URL = normalizedBackendUrl.endsWith('/api') ? normalizedBackendUrl : `${normalizedBackendUrl}/api`;
