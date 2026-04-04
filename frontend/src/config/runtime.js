const rawMode = import.meta.env.VITE_API_MODE;
const normalizedMode = (rawMode || 'mock').toLowerCase();

export const API_MODE = normalizedMode === 'live' ? 'live' : 'mock';
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
export const HEARTBEAT_INTERVAL_MS = Number(import.meta.env.VITE_HEARTBEAT_INTERVAL_MS || 5000);
