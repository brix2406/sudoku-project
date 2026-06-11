import { memo } from 'react';
import DropzoneLibrary from '../upload/DropzoneLibrary';

function renderBoard(board) {
  if (!Array.isArray(board) || board.length === 0) {
    return null;
  }

  return (
    <div className="board-wrapper" aria-label="Solved sudoku board">
      {board.map((row, rowIndex) => (
        <div className="board-row" key={`row-${rowIndex}`}>
          {row.map((value, colIndex) => (
            <span className="board-cell" key={`cell-${rowIndex}-${colIndex}`}>
              {value}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function UploadSection({ uploadedFile, result, isSolving, error, onImageSelected, onImageCleared }) {
  return (
    <section id="upload" className="page-section upload-section">
      <div className="section-inner">
        <h2>Upload And Solve</h2>
        <p className="section-copy">
          Supports drag-and-drop, click-to-upload, and mobile camera capture for PNG/JPEG.
        </p>

        <DropzoneLibrary onImageSelected={onImageSelected} onImageCleared={onImageCleared} />

        {uploadedFile && (
          <div className="upload-info">
            <p>File: {uploadedFile.name}</p>
            <p>Size: {(uploadedFile.size / 1024).toFixed(2)} KB</p>
          </div>
        )}

        <div className="solve-status-panel">
          <p>
            Solve state:{' '}
            <strong>{isSolving ? 'Uploading and solving...' : result ? 'Solved' : 'Idle'}</strong>
          </p>
          {error && <p className="error-text">{error}</p>}
        </div>

        {result?.meta && (
          <div className="meta-grid">
            <p>Mode: {result.meta.mode || 'unknown'}</p>
            <p>Latency: {result.meta.processTimeMs ?? 'n/a'} ms</p>
            <p>OCR confidence: {result.meta.confidence ?? 'n/a'}</p>
            <p>Extracted clues: {result.meta.extractedClues ?? 'n/a'}</p>
          </div>
        )}

        {renderBoard(result?.solvedBoard)}
      </div>
    </section>
  );
}

export default memo(UploadSection);
