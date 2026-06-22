// Maps a manual-solve failure to a user-facing message.
// Prefers the backend's error text; falls back to the impossible-puzzle
// message only when an HTTP error response had no readable error body.
const IMPOSSIBLE_FALLBACK = 'This puzzle is impossible: no solution exists.';

export function manualSolveErrorMessage(err) {
  if (err?.backendMessage) {
    return err.backendMessage;
  }
  if (typeof err?.status === 'number') {
    return IMPOSSIBLE_FALLBACK;
  }
  return err instanceof Error && err.message ? err.message : 'Failed to solve puzzle.';
}
