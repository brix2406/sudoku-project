import { useEffect, useState } from 'react';
import { HEARTBEAT_INTERVAL_MS } from '../config/runtime';
import { getStatus } from '../api/statusApi';

export function useHeartbeat() {
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const response = await getStatus();
        if (cancelled) {
          return;
        }

        setStatus(response);
        setError('');
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(err instanceof Error ? err.message : 'Heartbeat request failed.');
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    poll();
    const timerId = setInterval(poll, HEARTBEAT_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timerId);
    };
  }, []);

  return {
    status,
    isLoading,
    error,
  };
}
