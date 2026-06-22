import { API_BASE_URL } from '../config/runtime';

const DEFAULT_TIMEOUT_MS = 12000;

export async function apiRequest(path, options = {}) {
  // Empty API_BASE_URL means same-origin (Vite proxy handles routing).

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
      let backendMessage = null;

      try {
        const payload = await response.json();
        if (payload?.error) {
          message = payload.error;
          backendMessage = payload.error;
        }
      } catch {
        // Keep fallback message when response body is not JSON.
      }

      const error = new Error(message);
      error.status = response.status;
      error.backendMessage = backendMessage;
      throw error;
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
