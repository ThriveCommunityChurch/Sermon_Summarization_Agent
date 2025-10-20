import React, { useRef, useState } from 'react';
import './FileUpload.css';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isLoading?: boolean;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, isLoading = false }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const allowedExtensions = ['.mp3', '.mp4', '.wav', '.m4a', '.mov'];

  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true);
    } else if (e.type === 'dragleave') {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFile = (file: File) => {
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
      alert(`Invalid file type. Allowed types: ${allowedExtensions.join(', ')}`);
      return;
    }

    setSelectedFile(file);
    onFileSelect(file);
  };

  const handleClick = () => {
    if (!isLoading && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="file-upload-container">
      <div
        className={`file-upload-area ${isDragActive ? 'active' : ''} ${isLoading ? 'loading' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileInput}
          accept={allowedExtensions.join(',')}
          disabled={isLoading}
          style={{ display: 'none' }}
        />

        <div className="upload-content">
          {isLoading ? (
            <>
              <div className="upload-icon loading-icon">⏳</div>
              <p className="upload-text">Processing your sermon...</p>
              <p className="upload-subtext">This may take a few minutes</p>
            </>
          ) : (
            <>
              <p className="upload-text">
                {selectedFile ? selectedFile.name : 'Drag and drop your audio or video file here'}
              </p>
              <p className="upload-subtext">
                or click to browse • Supported: MP3, MP4, WAV, M4A, MOV
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

