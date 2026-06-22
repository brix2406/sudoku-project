import { memo } from 'react';
import DropzoneLibrary from '../upload/DropzoneLibrary';

function renderBoard(board, label) {
  if (!Array.isArray(board) || board.length === 0) {
    return null;
  }

  return (
    <div className="board-section">
      <h3>{label}</h3>
      <div className="board-wrapper" aria-label={label}>
        {board.map((row, rowIndex) => (
          <div className="board-row" key={`row-${label}-${rowIndex}`}>
            {row.map((value, colIndex) => (
              <span className="board-cell" key={`cell-${label}-${rowIndex}-${colIndex}`}>
                {value !== '.' ? value : ''}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function UploadSection({ uploadedFile, result, isSolving, error, onImageSelected, onImageCleared }) {
  return (
    <section id="upload" className="page-section upload-section">
      <div className="section-inner">
        <h2>Upload And Solve</h2>
        <p className="section-copy">
          Supports drag-and-drop, file upload, and camera capture for PNG/JPEG.
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
            <strong>{isSolving ? 'Uploading and solving...' : result ? result.status === 'failed' ? 'Failed' : 'Solved' : 'Idle'}</strong>
          </p>
          {error && <div className="manual-sudoku-error" role="alert">{error}</div>}
        </div>

        {result?.status === 'failed' && (
          <div className="manual-sudoku-error" role="alert">Failed to solve puzzle. The solver may not have found a solution.</div>
        )}

        {(result?.originalBoard?.length > 0 || result?.solvedBoard?.length > 0) && (
          <div className="boards-container">
            {renderBoard(result?.originalBoard, 'Original')}
            {renderBoard(result?.solvedBoard, 'Solved')}
          </div>
        )}

        
      </div>
    </section>
  );
}

export default memo(UploadSection);
