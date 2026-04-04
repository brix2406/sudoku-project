import { API_MODE } from '../config/runtime';
import { apiRequest } from './client';
import { mockGetStatus } from '../services/mockApi';

export async function getStatus() {
  if (API_MODE === 'mock') {
    return mockGetStatus();
  }

  return apiRequest('/status', {
    method: 'GET',
  });
}
