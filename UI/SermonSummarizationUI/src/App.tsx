import { useState } from 'react';
import './App.css';
import { FileUpload } from './components/FileUpload';
import { SummaryDisplay } from './components/SummaryDisplay';
import { SkeletonCodeBlock } from './components/SkeletonLoader';
import { apiClient } from './services/api';
import type { SermonProcessResponse } from './services/api';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<SermonProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = async (file: File) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.processSermon(file);

      if (response.status === 'failed') {
        setError(response.error || 'Failed to process sermon');
      } else {
        setResult(response);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred while processing the sermon';
      setError(errorMessage);
      console.error('Error processing sermon:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>Sermon Summarization</h1>
          <p>Upload your sermon audio or video to get AI-powered summary and tags</p>
        </div>
      </header>

      <main className="app-main">
        <div className="container">
          <FileUpload onFileSelect={handleFileSelect} isLoading={isLoading} />

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              <div>
                <p className="error-title">Processing Failed</p>
                <p className="error-text">{error}</p>
              </div>
            </div>
          )}

          {isLoading && <SkeletonCodeBlock />}

          {result && !isLoading && <SummaryDisplay result={result} />}
        </div>
      </main>

      <footer className="app-footer">
        <p>© {new Date().getFullYear()} Thrive Community Church</p>
      </footer>
    </div>
  );
}

export default App;
