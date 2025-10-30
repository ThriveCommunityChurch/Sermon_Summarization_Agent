import './WaveformFileRow.css';
import type { WaveformFileResult } from '../services/api';

interface WaveformFileRowProps {
  file: WaveformFileResult;
  onExpand: () => void;
  onCopy: () => void;
}

export const WaveformFileRow = ({ file, onExpand, onCopy }: WaveformFileRowProps) => {
  const getStatusIcon = () => {
    switch (file.status) {
      case 'success':
        return '✓';
      case 'error':
        return '✗';
      case 'processing':
        return '⟳';
      case 'pending':
        return '○';
      default:
        return '?';
    }
  };

  const getStatusClass = () => {
    switch (file.status) {
      case 'success':
        return 'status-success';
      case 'error':
        return 'status-error';
      case 'processing':
        return 'status-processing';
      case 'pending':
        return 'status-pending';
      default:
        return '';
    }
  };

  return (
    <div className="waveform-file-row">
      <div className="file-row-header" onClick={onExpand}>
        <span className={`status-icon ${getStatusClass()}`}>
          {getStatusIcon()}
        </span>

        <div className="file-info-container">
          <div className="file-info-main">
            <span className="filename">{file.filename}</span>
          </div>

          <div className="file-info-details">
            {file.fileSizeMb && (
              <span className="file-size">{file.fileSizeMb.toFixed(2)} MB</span>
            )}
            {file.sampleCount && (
              <span className="sample-count">{file.sampleCount} samples</span>
            )}
            {file.error && (
              <span className="error-badge" title={file.error}>
                {file.error}
              </span>
            )}
          </div>
        </div>

        <span className={`expand-icon ${file.isExpanded ? 'expanded' : ''}`}>
          ▼
        </span>
      </div>

      {file.isExpanded && (
        <div className="file-row-details">
          {file.isLoadingWaveform ? (
            <div className="loading-waveform">Loading waveform data...</div>
          ) : file.waveformData ? (
            <div className="waveform-data-section">
              <div className="waveform-header">
                <span className="waveform-label">
                  Waveform Data ({file.waveformData.length} values)
                </span>
                <button className="copy-button" onClick={onCopy}>
                  📋 Copy JSON
                </button>
              </div>
              <div className="waveform-preview">
                <code>{JSON.stringify(file.waveformData.slice(0, 10), null, 2)}...</code>
              </div>
            </div>
          ) : file.error ? (
            <div className="error-details">
              <span className="error-label">Error:</span>
              <span className="error-text">{file.error}</span>
            </div>
          ) : (
            <div className="no-data">No waveform data available</div>
          )}
        </div>
      )}
    </div>
  );
};

