import React from 'react';
import './SkeletonLoader.css';

interface SkeletonLoaderProps {
  lines?: number;
  height?: string;
}

export const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({ lines = 3, height = '16px' }) => {
  return (
    <div className="skeleton-loader">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="skeleton-line"
          style={{
            height,
            marginBottom: index < lines - 1 ? '12px' : '0',
          }}
        />
      ))}
    </div>
  );
};

export const SkeletonCodeBlock: React.FC = () => {
  return (
    <div className="skeleton-code-block">
      <div className="skeleton-header">
        <div className="skeleton-line" style={{ width: '150px', height: '20px' }} />
      </div>
      <div className="skeleton-content">
        <SkeletonLoader lines={8} height="14px" />
      </div>
    </div>
  );
};

