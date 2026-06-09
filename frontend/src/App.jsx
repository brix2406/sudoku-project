import { useState } from 'react';
import './App.css';
import HeroSection from './components/sections/HeroSection';
import ManualSudokuSection from './components/sections/ManualSudokuSection';
import UploadSection from './components/sections/UploadSection';
import AlgorithmSection from './components/sections/AlgorithmSection';
import StatusSection from './components/sections/StatusSection';
import { useOcrSolve } from './hooks/useOcrSolve';
import { useHeartbeat } from './hooks/useHeartbeat';

function App() {
  const { uploadedFile, result, isSolving, error, submitForSolve, clearUpload } = useOcrSolve();
  const { status, isLoading, error: heartbeatError } = useHeartbeat();
  
  const [showManualSection, setShowManualSection] = useState(false);

  const handleToggle = () => {
    setShowManualSection(!showManualSection);
  };

  return (
    <div className="site-shell">
      <header className="top-nav">
        <a href="#hero">Overview</a>
        <a href="#sudoku-input">Sudoku Input</a>
        <a href="#algorithm">Algorithm</a>
        <a href="#status">Status</a>
      </header>

      <HeroSection />
      
      <div className="container" id="sudoku-input" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '2rem 0' }}>
        <button onClick={handleToggle} style={{ padding: '10px 20px', fontSize: '16px', cursor: 'pointer', marginBottom: '1rem' }}>
          Switch to {showManualSection ? 'Image Upload' : 'Manual Input'}
        </button>
        
        <div className="content-area" style={{ width: '100%' }}>
          {showManualSection ? (
            <ManualSudokuSection />
          ) : (
            <UploadSection
              uploadedFile={uploadedFile}
              result={result}
              isSolving={isSolving}
              error={error}
              onImageSelected={submitForSolve}
              onImageCleared={clearUpload}
            />
          )}
        </div>
      </div>

      <AlgorithmSection />
      <StatusSection heartbeat={status} isLoading={isLoading} error={heartbeatError} />
    </div>
  );
}

export default App;