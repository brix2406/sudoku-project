import { API_MODE } from '../config/runtime';
import { apiRequest } from './client';
import { mockSolveManual } from '../services/mockApi';

export async function solveManual(sudokuString) {
  if (API_MODE === 'mock') {
    return mockSolveManual(sudokuString);
  }

  const response = await apiRequest('/manual_solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sudoku_string: sudokuString }),
  });

  const status = isBoardSolved(response?.solved_board) ? 'success' : 'failed';

  return {
    status,
    originalBoard: response?.original_board || [],
    solvedBoard: response?.solved_board || [],
    meta: {
      mode: 'live',
      processTimeMs: response?.processTimeMs,
    },
  };
}

function isBoardSolved(board) {
  if (!Array.isArray(board) || board.length === 0) return false;
  return board.every(row => row.every(cell => cell !== '.'));
}
