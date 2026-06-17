import { API_MODE } from '../config/runtime';
import { apiRequest } from './client';
import { mockSolveFromImage } from '../services/mockApi';

export async function solveFromImage(file) {
  if (API_MODE === 'mock') {
    return mockSolveFromImage(file);
  }

  const formData = new FormData();
  formData.append('image', file);
  formData.append('n', '3');
  formData.append('k', '3');

  const response = await apiRequest('/ocr_solve', {
    method: 'POST',
    body: formData,
  });
function isBoardSolved(board) {
  if (!Array.isArray(board) || board.length === 0) return false;
  return board.every(row => row.every(cell => cell !== '.'));
}

  const status = isBoardSolved(response?.solved_board) ? 'success' : 'failed';

  return {
    status,
    originalBoard: response?.original_board || [],
    solvedBoard: response?.solved_board || [],
    meta: {
      mode: 'live',
      processTimeMs: response?.processTimeMs,
      confidence: response?.confidence,
    },
  };
}
