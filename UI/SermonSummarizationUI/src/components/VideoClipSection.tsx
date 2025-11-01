import React, { useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFile, faVideo, faInfoCircle } from '@fortawesome/free-solid-svg-icons';
import type { VideoClipMetadata } from '../services/api';
import './VideoClipSection.css';

interface VideoClipSectionProps {
  videoClipFilename: string;
  videoClipPath?: string;
  videoClipMetadata?: VideoClipMetadata;
}

export const VideoClipSection: React.FC<VideoClipSectionProps> = ({
  videoClipFilename,
  videoClipPath,
  videoClipMetadata,
}) => {
  const [showMetadata, setShowMetadata] = useState(false);

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const formatRelativeDuration = (seconds: number): string => {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatFileSize = (mb: number): string => {
    if (mb < 1) {
      return `${(mb * 1024).toFixed(1)} KB`;
    }
    if (mb > 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb.toFixed(1)} MB`;
  };

  const handleCopyPath = async () => {
    // Copy the full file system path to clipboard
    // User can then paste it into their file explorer or video player
    if (videoClipPath) {
      try {
        await navigator.clipboard.writeText(videoClipPath);
      } catch (err) {
        console.error('Failed to copy path to clipboard:', err);
        alert(`Failed to copy to clipboard. File path: ${videoClipPath}`);
      }
    } else {
      console.error('Video clip path not available');
    }
  };

  const handleDownloadMetadata = async () => {
    if (!videoClipMetadata) return;

    if (videoClipPath) {
      var metadataPath = videoClipPath.replace('.mp4', '_metadata.json');

      try {
        await navigator.clipboard.writeText(metadataPath);
      } catch (err) {
        console.error('Failed to copy path to clipboard:', err);
        alert(`Failed to copy to clipboard. File path: ${metadataPath}`);
      }
    } else {
      console.error('Video metadata path not available');
    }
  };

  return (
    <div className="video-clip-section">
      <h3>
        <FontAwesomeIcon icon={faVideo} style={{ marginRight: '8px' }} />
        Video Clip Generated
      </h3>

      <div className="video-clip-info">
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Summary Score</span>
            <div className="row">
              <span className="big-info-value">{((videoClipMetadata?.summary?.average_importance_score ?? 0)* 10).toFixed(2)}</span>
              <span className="info-label" id='max-score'>/ 100</span>
            </div>
          </div>

          <div className="info-item">
            <span className="info-label">File Name</span>
            <span className="info-value">{videoClipFilename}</span>
          </div>
          
        </div>
        <div className="info-grid">         
          {videoClipMetadata && (
            <>
              {videoClipMetadata.output_video?.duration_seconds !== undefined && (
                <div className="info-item">
                  <span className="info-label">Duration</span>
                  <span className="info-value">
                    {formatDuration(videoClipMetadata.output_video.duration_seconds)}
                  </span>
                </div>
              )}
              {videoClipMetadata.output_video?.file_size_mb !== undefined && (
                <div className="info-item">
                  <span className="info-label">File Size</span>
                  <span className="info-value">
                    {formatFileSize(videoClipMetadata.output_video.file_size_mb)}
                  </span>
                </div>
              )}
              {videoClipMetadata.summary?.total_segments !== undefined && (
                <div className="info-item">
                  <span className="info-label">Segments</span>
                  <span className="info-value">
                    {videoClipMetadata.summary.total_segments}
                  </span>
                </div>
              )}
              {videoClipMetadata.output_video?.size_reduction_percent !== undefined && (
                <div className="info-item">
                  <span className="info-label">Size Reduction</span>
                  <span className="info-value">
                    {videoClipMetadata.output_video.size_reduction_percent.toFixed(1)}%
                  </span>
                </div>
              )}
            </>
          )}
        </div>

        <div className="video-clip-actions">
          <button
            className="download-button primary"
            onClick={handleCopyPath}
          >
            <FontAwesomeIcon icon={faVideo} />
            Copy File Path
          </button>

          {videoClipMetadata && (
            <>
              <button
                className="download-button secondary"
                onClick={handleDownloadMetadata}
              >
                <FontAwesomeIcon icon={faFile} />
                Copy Metadata Path
              </button>

              <button
                className="download-button secondary"
                onClick={() => setShowMetadata(!showMetadata)}
              >
                <FontAwesomeIcon icon={faInfoCircle} />
                {showMetadata ? 'Hide Details' : 'View Details'}
              </button>
            </>
          )}
        </div>
      </div>

      {showMetadata && videoClipMetadata && (
        <div className="metadata-details">
          {videoClipMetadata.original_video && (
            <div className="metadata-section">
              <h4>Original Video</h4>
              <div className="metadata-grid">
                {videoClipMetadata.original_video.duration_seconds !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">Duration</span>
                    <span className="metadata-value">
                      {formatDuration(videoClipMetadata.original_video.duration_seconds)}
                    </span>
                  </div>
                )}
                {videoClipMetadata.original_video.file_size_mb !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">File Size</span>
                    <span className="metadata-value">
                      {formatFileSize(videoClipMetadata.original_video.file_size_mb)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {videoClipMetadata.processing_stats && (
            <div className="metadata-section">
              <h4>Processing Stats</h4>
              <div className="metadata-grid">
                {videoClipMetadata.processing_stats.ai_selection_time_seconds !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">AI Selection</span>
                    <span className="metadata-value">
                      {formatRelativeDuration(videoClipMetadata.processing_stats.ai_selection_time_seconds)}
                    </span>
                  </div>
                )}
                {videoClipMetadata.processing_stats.ffmpeg_execution_time_seconds !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">FFMPEG Processing</span>
                    <span className="metadata-value">
                      {formatRelativeDuration(videoClipMetadata.processing_stats.ffmpeg_execution_time_seconds)}
                    </span>
                  </div>
                )}
                {(
                  <div className="metadata-item">
                    <span className="metadata-label">Total Time</span>
                    <span className="metadata-value">
                      {formatRelativeDuration(videoClipMetadata.processing_stats.ffmpeg_execution_time_seconds + videoClipMetadata.processing_stats.ai_selection_time_seconds)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {videoClipMetadata.configuration && (
            <div className="metadata-section">
              <h4>Configuration</h4>
              <div className="metadata-grid">
                {videoClipMetadata.configuration.max_clip_duration !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">Max Duration</span>
                    <span className="metadata-value">
                      {formatRelativeDuration(videoClipMetadata.configuration.max_clip_duration)}
                    </span>
                  </div>
                )}
                {videoClipMetadata.configuration.min_segment_length !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">Min Segment</span>
                    <span className="metadata-value">
                      {formatRelativeDuration(videoClipMetadata.configuration.min_segment_length)}
                    </span>
                  </div>
                )}
                {videoClipMetadata.configuration.enable_fade_transitions !== undefined && (
                  <div className="metadata-item">
                    <span className="metadata-label">Fade Transitions</span>
                    <span className="metadata-value">
                      {videoClipMetadata.configuration.enable_fade_transitions ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {videoClipMetadata.segments && videoClipMetadata.segments.length > 0 && (
            <div className="metadata-section">
              <h4>Selected Segments ({videoClipMetadata.segments.length})</h4>
              <div className="segments-list">
                {videoClipMetadata.segments.map((segment, index) => (
                  <div key={index} className="segment-item">
                    <div className="segment-header">
                      <span className="segment-time">
                        {formatDuration(segment.start_time)} - {formatDuration(segment.end_time)}
                      </span>
                      <span className="segment-duration">
                        {formatDuration(segment.duration_seconds)}
                      </span>
                    </div>
                    {segment.selection_reason && (
                      <div className="segment-reason">{segment.selection_reason}</div>
                    )}
                    {segment.text_preview && (
                      <div className="segment-text">{segment.text_preview}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

