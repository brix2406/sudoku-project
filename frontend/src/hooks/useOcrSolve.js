import { useCallback, useState } from 'react';
import { solveFromImage } from '../api/ocrApi';

export function useOcrSolve() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadedPreview, setUploadedPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [isSolving, setIsSolving] = useState(false);
  const [error, setError] = useState('');

  const submitForSolve = useCallback(async (imageData, file) => {
    setUploadedFile(file);
    setUploadedPreview(imageData);
    setResult(null);
    setError('');
    setIsSolving(true);

    try {
      const response = await solveFromImage(file);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to solve puzzle.');
    } finally {
      setIsSolving(false);
    }
  }, []);

  const clearUpload = useCallback(() => {
    setUploadedFile(null);
    setUploadedPreview(null);
    setResult(null);
    setError('');
    setIsSolving(false);
  }, []);

  return {
    uploadedFile,
    uploadedPreview,
    result,
    isSolving,
    error,
    submitForSolve,
    clearUpload,
  };
}
