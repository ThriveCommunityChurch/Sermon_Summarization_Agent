import React, { useState, useRef } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCopy } from '@fortawesome/free-regular-svg-icons';
import { faCheck } from '@fortawesome/free-solid-svg-icons';

import type { SermonProcessResponse } from '../services/api';
import { getCostBreakdown, formatCost } from '../utils/costCalculator';
import './SummaryDisplay.css';

interface SummaryDisplayProps {
  result: SermonProcessResponse;
}

export const SummaryDisplay: React.FC<SummaryDisplayProps> = ({ result }) => {
  const [copied, setCopied] = useState(false);
  const [waveformCopied, setWaveformCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);
  const waveformTimeoutRef = useRef<number | null>(null);

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result.summary);

    // Clear any existing timeout
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
    }

    // Set copied state to true
    setCopied(true);

    // Reset after 2 seconds
    timeoutRef.current = window.setTimeout(() => {
      setCopied(false);
      timeoutRef.current = null;
    }, 2000);
  };

  const handleWaveformCopy = () => {
    if (result.waveformData) {
      navigator.clipboard.writeText(JSON.stringify(result.waveformData, null, 2));

      // Clear any existing timeout
      if (waveformTimeoutRef.current !== null) {
        clearTimeout(waveformTimeoutRef.current);
      }

      // Set copied state to true
      setWaveformCopied(true);

      // Reset after 2 seconds
      waveformTimeoutRef.current = window.setTimeout(() => {
        setWaveformCopied(false);
        waveformTimeoutRef.current = null;
      }, 2000);
    }
  };

  return (
    <div className="summary-display">
      <div className="summary-card">
        <div className="card-header">
          <h2>Sermon Summary</h2>
          <span className="processing-time">
            Processed in {formatDuration(result.processingDurationSeconds)}
          </span>
        </div>

        <div className="code-block">
          <div className="code-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="code-label">Summary</span>
            <FontAwesomeIcon
              icon={copied ? faCheck : faCopy}
              style={{
                color: copied ? '#10b981' : '#64748b',
                height: '12px',
                transition: 'color 0.2s ease'
              }}
              onClick={handleCopy}
            />
          </div>
          <div className="code-content">
            <p className="summary-text">{result.summary}</p>
          </div>
        </div>

        {result.tags && result.tags.length > 0 && (
          <div className="tags-section">
            <h3>Tags</h3>
            <div className="tags-container">
              {result.tags.map((tag, index) => (
                <span key={index} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Waveform Data Section */}
        {result.waveformData && result.waveformData.length > 0 && (
          <div className="waveform-section">
            <h3>Waveform Data</h3>
            <div className="code-block">
              <div className="code-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="code-label">Audio Waveform (480 normalized values)</span>
                <FontAwesomeIcon
                  icon={waveformCopied ? faCheck : faCopy}
                  style={{
                    color: waveformCopied ? '#10b981' : '#64748b',
                    height: '12px',
                    transition: 'color 0.2s ease',
                    cursor: 'pointer'
                  }}
                  onClick={handleWaveformCopy}
                />
              </div>
              <div className="code-content waveform-json">
                <pre>{JSON.stringify(result.waveformData, null, 2)}</pre>
              </div>
            </div>
            <div className="waveform-info">
              <p>
                <strong>Format:</strong> Array of {result.waveformData.length} normalized amplitude values (0.15-1.0 range)
              </p>
              <p>
                <strong>Usage:</strong> Copy this data for use in mobile apps or audio visualization components
              </p>
            </div>
          </div>
        )}

          {/* Cost Breakdown Section */}
        {result.tokenBreakdown && (() => {
          // Check if we have the detailed breakdown (new format)
          const hasDetailedBreakdown =
            result.tokenBreakdown.summarizationInputTokens !== undefined &&
            result.tokenBreakdown.summarizationOutputTokens !== undefined &&
            result.tokenBreakdown.taggingInputTokens !== undefined &&
            result.tokenBreakdown.taggingOutputTokens !== undefined;

          if (!hasDetailedBreakdown) return null;

          const costs = getCostBreakdown(
            result.tokenBreakdown.summarizationInputTokens!,
            result.tokenBreakdown.summarizationOutputTokens!,
            result.tokenBreakdown.taggingInputTokens!,
            result.tokenBreakdown.taggingOutputTokens!
          );

          return (
            <div className="tokens-section">
              <h3>Cost</h3>
              <div className="tokens-grid">
                <div className="token-item">
                  <span className="token-label">Total</span>
                  <span className="token-value" style={{ color: '#10b981', fontWeight: 600 }}>
                    {formatCost(costs.totalCost)}
                  </span>
                </div>
              </div>

              <div className="operation-breakdown">
                <div className="operation-section">
                  <h4>Cost of Operation</h4>
                  <div className="tokens-grid">
                    <div className="token-item">
                      <span className="token-label">Summarization</span>
                      <span className="token-value">
                        {formatCost(costs.summarizationCost)}
                      </span>
                    </div>
                    <div className="token-item">
                      <span className="token-label">Tagging</span>
                      <span className="token-value">
                        {formatCost(costs.taggingCost)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Token Usage Section */}
        <div className="tokens-section">
          <h3>Token Usage</h3>
          {result.tokenBreakdown && (() => {
            // Check if we have the detailed breakdown (new format)
            const hasDetailedBreakdown =
              result.tokenBreakdown.summarizationInputTokens !== undefined &&
              result.tokenBreakdown.summarizationOutputTokens !== undefined &&
              result.tokenBreakdown.taggingInputTokens !== undefined &&
              result.tokenBreakdown.taggingOutputTokens !== undefined;

            return (
              <>
                <div className="tokens-grid">
                  <div className="token-item">
                    <span className="token-label">Total Tokens</span>
                    <span className="token-value">{result.totalTokensUsed.toLocaleString()}</span>
                  </div>
                </div>

                {hasDetailedBreakdown && result.tokenBreakdown ? (
                  <div className="operation-breakdown">
                    <div className="operation-section">
                      <h4>Summarization</h4>
                      <div className="tokens-grid">
                        <div className="token-item">
                          <span className="token-label">Total</span>
                          <span className="token-value">
                            {result.tokenBreakdown.summarizationTokens.toLocaleString()}
                          </span>
                        </div>
                        <div className="token-item">
                          <span className="token-label">Input</span>
                          <span className="token-value">
                            {result.tokenBreakdown?.summarizationInputTokens?.toLocaleString()}
                          </span>
                        </div>
                        <div className="token-item">
                          <span className="token-label">Output</span>
                          <span className="token-value">
                            {result.tokenBreakdown?.summarizationOutputTokens?.toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="operation-section">
                      <h4>Tagging</h4>
                      <div className="tokens-grid">
                        <div className="token-item">
                          <span className="token-label">Total</span>
                          <span className="token-value">
                            {result.tokenBreakdown.taggingTokens.toLocaleString()}
                          </span>
                        </div>
                        <div className="token-item">
                          <span className="token-label">Input</span>
                          <span className="token-value">
                            {result.tokenBreakdown?.taggingInputTokens?.toLocaleString()}
                          </span>
                        </div>
                        <div className="token-item">
                          <span className="token-label">Output</span>
                          <span className="token-value">
                            {result.tokenBreakdown?.taggingOutputTokens?.toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="tokens-grid">
                    <div className="token-item">
                      <span className="token-label">Summarization</span>
                      <span className="token-value">
                        {result.tokenBreakdown.summarizationTokens.toLocaleString()}
                      </span>
                    </div>
                    <div className="token-item">
                      <span className="token-label">Tagging</span>
                      <span className="token-value">
                        {result.tokenBreakdown.taggingTokens.toLocaleString()}
                      </span>
                    </div>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
};

