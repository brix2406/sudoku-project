import { API_BASE_URL } from '../config/runtime';

const DEFAULT_TIMEOUT_MS = 12000;

export async function apiRequest(path, options = {}) {
  if (!API_BASE_URL) {
    throw new Error('API base URL is not configured yet. Set VITE_API_BASE_URL when backend is ready.');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
    });

    if (!response.ok) {
      const fallback = `Request failed: ${response.status}`;
      let message = fallback;

      try {
        const payload = await response.json();
        if (payload?.error) {
          message = payload.error;
        }
      } catch {
        // Keep fallback message when response body is not JSON.
      }

      throw new Error(message);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return response.json();
    }

    return response.text();
  } finally {
    clearTimeout(timeoutId);
  }
}
