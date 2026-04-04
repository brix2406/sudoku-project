import './App.css';
import HeroSection from './components/sections/HeroSection';
import UploadSection from './components/sections/UploadSection';
import AlgorithmSection from './components/sections/AlgorithmSection';
import StatusSection from './components/sections/StatusSection';
import { useOcrSolve } from './hooks/useOcrSolve';
import { useHeartbeat } from './hooks/useHeartbeat';

function App() {
  const { uploadedFile, result, isSolving, error, submitForSolve, clearUpload } = useOcrSolve();
  const { status, isLoading, error: heartbeatError } = useHeartbeat();

  return (
    <div className="site-shell">
      <header className="top-nav">
        <a href="#hero">Overview</a>
        <a href="#upload">Solve</a>
        <a href="#algorithm">Algorithm</a>
        <a href="#status">Status</a>
      </header>

      <HeroSection />
      <UploadSection
        uploadedFile={uploadedFile}
        result={result}
        isSolving={isSolving}
        error={error}
        onImageSelected={submitForSolve}
        onImageCleared={clearUpload}
      />
      <AlgorithmSection />
      <StatusSection heartbeat={status} isLoading={isLoading} error={heartbeatError} />
    </div>
  );
}

export default App;