import { useState, useEffect } from 'react';
import './BulkWaveformGenerator.css';
import { WaveformFileRow } from './WaveformFileRow';
import { apiClient, type WaveformJobStatus } from '../services/api';
import { useWaveformProgress } from '../hooks/useWaveformProgress';

export const BulkWaveformGenerator = () => {
  const [directoryPath, setDirectoryPath] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<WaveformJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [exportFormat, setExportFormat] = useState<'json' | 'csv' | 'zip'>('json');
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isResultsExpanded, setIsResultsExpanded] = useState(false);

  const isProcessing = jobStatus?.status === 'queued' || jobStatus?.status === 'processing';
  const canExport = jobStatus?.status === 'completed' && jobId;

  // SignalR WebSocket connection for real-time updates
  const { connectionState } = useWaveformProgress({
    jobId,
    onJobStarted: (data) => {
      console.log('Job started:', data);
      setJobStatus(prev => prev ? {
        ...prev,
        totalFiles: data.totalFiles,
        status: 'processing',
        startTime: data.startTime
      } : null);
    },
    onFileProgress: (data) => {
      console.log('File progress:', data);
      setJobStatus(prev => prev ? {
        ...prev,
        currentFile: data.currentFile,
        processedFiles: data.current // Update processedFiles to current file index
      } : null);
    },
    onFileComplete: (data) => {
      console.log('File complete:', data);
      setJobStatus(prev => {
        if (!prev) return null;
        const existingResult = prev.results.find(r => r.filename === data.fileResult.filename);
        const updatedResults = existingResult
          ? prev.results.map(r => r.filename === data.fileResult.filename ? data.fileResult : r)
          : [...prev.results, data.fileResult];

        return {
          ...prev,
          results: updatedResults,
          // Don't update processedFiles here - it's updated by FileProgress event
          successfulFiles: updatedResults.filter(r => r.status === 'success').length,
          failedFiles: updatedResults.filter(r => r.status === 'error').length
        };
      });
    },
    onJobComplete: (data) => {
      console.log('Job complete:', data);
      setJobStatus(prev => prev ? { ...prev, status: 'completed' } : null);
    },
    onJobFailed: (data) => {
      console.log('Job failed:', data);
      setError(data.error);
      setJobStatus(prev => prev ? { ...prev, status: 'failed', error: data.error } : null);
    }
  });

  // Polling effect - only poll when WebSocket is not connected
  useEffect(() => {
    if (!jobId || !isProcessing || connectionState === 'connected') {
      return; // Don't poll if WebSocket is connected
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusData = await apiClient.getWaveformJobStatus(jobId);
        setJobStatus(statusData);

        // Stop polling when job completes or fails
        if (statusData.status === 'completed' || statusData.status === 'failed') {
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error('Error polling job status:', error);
      }
    }, 1500); // Poll every 1.5 seconds

    return () => clearInterval(pollInterval);
  }, [jobId, isProcessing, connectionState]);

  // Timer effect to update elapsed time and estimated remaining time every second
  useEffect(() => {
    if (!jobStatus || !isProcessing || !jobStatus.startTime) {
      return;
    }

    const timerInterval = setInterval(() => {
      const startTime = new Date(jobStatus.startTime);
      const now = new Date();
      const elapsedSeconds = Math.floor((now.getTime() - startTime.getTime()) / 1000);

      setJobStatus(prev => {
        if (!prev) return null;

        // Calculate estimated remaining time
        const completed = prev.successfulFiles + prev.failedFiles;
        let estimatedRemainingSeconds: number | undefined;

        if (completed > 0 && elapsedSeconds > 0) {
          const avgSecondsPerFile = elapsedSeconds / completed;
          const remainingFiles = prev.totalFiles - completed;
          estimatedRemainingSeconds = Math.round(avgSecondsPerFile * remainingFiles);
        }

        return { ...prev, elapsedSeconds, estimatedRemainingSeconds };
      });
    }, 1000); // Update every second

    return () => clearInterval(timerInterval);
  }, [jobStatus?.startTime, isProcessing]);

  const handleStartJob = async () => {
    if (!directoryPath.trim()) {
      setError('Please enter a directory path');
      return;
    }

    setIsStarting(true);
    setError(null);

    try {
      const response = await apiClient.startBulkWaveform(directoryPath);

      if (response.status === 'failed') {
        setError(response.message || 'Failed to start job');
        setIsStarting(false);
        return;
      }

      // Initialize job status to trigger polling
      setJobStatus({
        jobId: response.jobId,
        status: 'queued',
        totalFiles: 0,
        processedFiles: 0,
        successfulFiles: 0,
        failedFiles: 0,
        startTime: new Date().toISOString(),
        results: []
      });

      setJobId(response.jobId);
      setIsStarting(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
      setError(errorMessage);
      setIsStarting(false);
    }
  };

  const handleExport = async () => {
    if (!jobId || !canExport) return;

    setIsExporting(true);
    setExportError(null);

    try {
      const response = await apiClient.exportWaveformData(jobId, exportFormat);

      // Create a blob from the response data
      const blob = new Blob([response], {
        type: exportFormat === 'json' ? 'application/json' :
              exportFormat === 'csv' ? 'text/csv' :
              'application/zip'
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `waveforms-${jobId}.${exportFormat}`;
      document.body.appendChild(link);
      link.click();

      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setIsExporting(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Export failed';
      setExportError(errorMessage);
      setIsExporting(false);
    }
  };

  const handleExpandFile = async (filename: string) => {
    if (!jobStatus || !jobId) return;

    const fileResult = jobStatus.results.find(r => r.filename === filename);
    if (!fileResult) return;

    // Toggle collapse if already expanded
    if (fileResult.isExpanded) {
      setJobStatus(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          results: prev.results.map(r =>
            r.filename === filename ? { ...r, isExpanded: false } : r
          )
        };
      });
      return;
    }

    // Load waveform data if not already loaded
    if (!fileResult.waveformData) {
      setJobStatus(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          results: prev.results.map(r =>
            r.filename === filename ? { ...r, isLoadingWaveform: true } : r
          )
        };
      });

      try {
        const waveformData = await apiClient.getWaveformData(jobId, filename);
        setJobStatus(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            results: prev.results.map(r =>
              r.filename === filename
                ? { ...r, waveformData: waveformData.waveformValues, isExpanded: true, isLoadingWaveform: false }
                : r
            )
          };
        });
      } catch (error) {
        console.error('Error loading waveform data:', error);
        setJobStatus(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            results: prev.results.map(r =>
              r.filename === filename ? { ...r, isLoadingWaveform: false } : r
            )
          };
        });
      }
    } else {
      // Just expand
      setJobStatus(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          results: prev.results.map(r =>
            r.filename === filename ? { ...r, isExpanded: true } : r
          )
        };
      });
    }
  };

  const handleCopyWaveform = async (filename: string) => {
    if (!jobStatus || !jobId) return;

    const fileResult = jobStatus.results.find(r => r.filename === filename);
    if (!fileResult) return;

    try {
      // Load waveform data if not already loaded
      let waveformValues = fileResult.waveformData;
      if (!waveformValues) {
        const waveformData = await apiClient.getWaveformData(jobId, filename);
        waveformValues = waveformData.waveformValues;
      }

      // Copy to clipboard
      const jsonString = JSON.stringify(waveformValues, null, 2);
      await navigator.clipboard.writeText(jsonString);

      // Show success feedback (you could add a toast notification here)
      console.log('Waveform data copied to clipboard');
    } catch (error) {
      console.error('Error copying waveform data:', error);
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '0s';

    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
      return `${mins}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const progressPercentage = jobStatus
    ? (jobStatus.processedFiles / jobStatus.totalFiles) * 100
    : 0;

  return (
    <div className="bulk-waveform-generator">
      <div className="generator-header">
        <h2>Bulk Waveform Generation</h2>
        <p>Generate waveform data for multiple audio files in a directory</p>
      </div>

      {/* Connection Status Indicator */}
      {jobId && connectionState === 'connected' && (
        <div className="connection-status connected">
          <span className="status-dot"></span>
           Connected. Working...
        </div>
      )}
      {jobId && connectionState === 'connecting' && (
        <div className="connection-status connecting">
          <span className="status-dot"></span>
          Connecting...
        </div>
      )}

      {/* Directory Input */}
      <div className="input-section">
        <input
          type="text"
          className="directory-input"
          placeholder="Enter directory path (e.g., C:/Audio/Sermons)"
          value={directoryPath}
          onChange={(e) => setDirectoryPath(e.target.value)}
          disabled={isProcessing || isStarting}
        />
        <button
          className="start-button"
          onClick={handleStartJob}
          disabled={isProcessing || isStarting || !directoryPath.trim()}
        >
          {isStarting ? 'Starting...' : 'Generate Waveforms'}
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <div>
            <p className="error-title">Error</p>
            <p className="error-text">{error}</p>
          </div>
        </div>
      )}

      {/* Job Status Section */}
      {jobStatus && (
        <>
          {/* Summary Stats */}
          <div className="summary-stats">
            <div className="stat-card">
              <span className="stat-label">Total Files</span>
              <span className="stat-value">{jobStatus.totalFiles}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Completed</span>
              <span className="stat-value success">{jobStatus.successfulFiles}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Failed</span>
              <span className="stat-value error">{jobStatus.failedFiles}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Processing Rate</span>
              <span className="stat-value">
                {(() => {
                  const completed = jobStatus.successfulFiles + jobStatus.failedFiles;
                  const elapsed = jobStatus.elapsedSeconds || 0;
                  if (completed === 0 || elapsed === 0) return '—';
                  const rate = (completed / elapsed) * 60; // files per minute
                  return `${rate.toFixed(1)} /min`;
                })()}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Elapsed Time</span>
              <span className="stat-value">{formatDuration(jobStatus.elapsedSeconds)}</span>
            </div>
            {jobStatus.estimatedRemainingSeconds && jobStatus.status === 'processing' && (
              <div className="stat-card">
                <span className="stat-label">Est. Remaining</span>
                <span className="stat-value">{formatDuration(jobStatus.estimatedRemainingSeconds)}</span>
              </div>
            )}
          </div>

          {/* Export Section */}
          {canExport && (
            <div className="export-section">
              <div className="export-controls">
                <label htmlFor="export-format" className="export-label">
                  Export Format:
                </label>
                <select
                  id="export-format"
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value as 'json' | 'csv' | 'zip')}
                  className="export-format-select"
                  disabled={isExporting}
                >
                  <option value="json">JSON (Single File)</option>
                  <option value="csv">CSV (Spreadsheet)</option>
                  <option value="zip">ZIP (Individual Files)</option>
                </select>
                <button
                  onClick={handleExport}
                  disabled={isExporting}
                  className="export-button"
                >
                  {isExporting ? 'Exporting...' : '📥 Export Data'}
                </button>
              </div>
              {exportError && (
                <div className="export-error">
                  <span className="error-icon">⚠️</span>
                  <span>{exportError}</span>
                </div>
              )}
            </div>
          )}

          {/* Progress Bar */}
          <div className="progress-section">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <span className="progress-text">
              {jobStatus.processedFiles} of {jobStatus.totalFiles} files processed
              {jobStatus.currentFile && ` • Currently processing: ${jobStatus.currentFile}`}
            </span>
          </div>

          {/* File Results Table - Collapsible */}
          <div className="results-section">
            <div
              className={`results-header ${jobStatus.totalFiles > 100 ? 'disabled' : ''}`}
              onClick={() => {
                if (jobStatus.totalFiles <= 100) {
                  setIsResultsExpanded(!isResultsExpanded);
                }
              }}
              style={{ cursor: jobStatus.totalFiles > 100 ? 'not-allowed' : 'pointer' }}
            >
              <h3>
                Files ({jobStatus.results.length})
                {jobStatus.totalFiles <= 100 && (
                  <span className="collapse-icon">
                    {isResultsExpanded ? '▼' : '▶'}
                  </span>
                )}
              </h3>
              {jobStatus.totalFiles > 100 && (
                <span className="results-disabled-message">
                  Too many files to display. Use the Export feature to download results.
                </span>
              )}
            </div>

            {/* Only render rows when expanded AND total files <= 100 */}
            {isResultsExpanded && jobStatus.totalFiles <= 100 && (
              <div className="results-table">
                {jobStatus.results.map(file => (
                  <WaveformFileRow
                    key={file.filename}
                    file={file}
                    onExpand={() => handleExpandFile(file.filename)}
                    onCopy={() => handleCopyWaveform(file.filename)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

