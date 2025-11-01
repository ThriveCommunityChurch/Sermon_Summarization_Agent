export interface TokenBreakdown {
  summarizationTokens: number;
  summarizationInputTokens?: number;
  summarizationOutputTokens?: number;
  taggingTokens: number;
  taggingInputTokens?: number;
  taggingOutputTokens?: number;
  clipGenerationTokens?: number;
  clipGenerationInputTokens?: number;
  clipGenerationOutputTokens?: number;
}

export interface VideoClipMetadata {
  version: string;
  generated_at: string;
  original_video: {
    path: string;
    duration_seconds: number;
    file_size_mb: number;
  };
  output_video: {
    path: string;
    duration_seconds: number;
    file_size_mb: number;
    size_reduction_percent: number;
  };
  processing_stats: {
    total_workflow_time_seconds: number;
    ai_selection_time_seconds: number;
    optimization_time_seconds: number;
    ffmpeg_execution_time_seconds: number;
    original_segment_count: number;
    ai_selected_count: number;
    final_segment_count: number;
  };
  configuration: {
    max_clip_duration: number;
    min_segment_length: number;
    context_padding: number;
    merge_gap_threshold: number;
    enable_fade_transitions: boolean;
    fade_duration: number;
    gpu_encoding_enabled: boolean;
    gpu_encoding_attempted: boolean;
    gpu_fallback_occurred: boolean;
    gpu_encoder_preset: string | null;
  };
  gpu_info: {
    gpu_available: boolean;
    ffmpeg_cuda_support: boolean;
    encoding_method: string;
    status: string;
  };
  segments: Array<{
    index: number;
    start_time: number;
    end_time: number;
    duration_seconds: number;
    start_time_formatted: string;
    end_time_formatted: string;
    importance_score: number;
    selection_reason: string;
    text_preview: string;
    full_text_length: number;
  }>;
  summary: {
    total_segments: number;
    total_duration_seconds: number;
    total_duration_formatted: string;
    average_segment_duration: number;
    compression_ratio: number;
    average_importance_score: number;
  };
  tokens: {
    total: number;
    input: number;
    output: number;
  };
}

export interface SermonProcessResponse {
  id: string;
  summary: string;
  tags: string[];
  waveformData?: number[];
  totalTokensUsed: number;
  tokenBreakdown: TokenBreakdown;
  videoClipGenerated?: boolean;
  videoClipFilename?: string;
  videoClipPath?: string;
  videoClipMetadata?: VideoClipMetadata;
  status: string;
  error?: string;
  processedAt: string;
  processingDurationSeconds: number;
}

export interface WaveformFileResult {
  filename: string;
  status: 'pending' | 'processing' | 'success' | 'error';
  sampleCount?: number;
  fileSizeMb?: number;
  error?: string;
  outputPath?: string;
  // UI-only state
  isExpanded?: boolean;
  waveformData?: number[];
  isLoadingWaveform?: boolean;
}

export interface WaveformJobStatus {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  totalFiles: number;
  processedFiles: number;
  successfulFiles: number;
  failedFiles: number;
  currentFile?: string;
  startTime: string;
  endTime?: string;
  elapsedSeconds?: number;
  estimatedRemainingSeconds?: number;
  results: WaveformFileResult[];
  error?: string;
}

export interface BulkWaveformJobResponse {
  jobId: string;
  status: string;
  message: string;
}

export interface WaveformData {
  filename: string;
  waveformValues: number[];
  sampleCount: number;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export const apiClient = {
  async processSermon(file: File): Promise<SermonProcessResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/sermons/process`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to process sermon');
    }

    return response.json();
  },

  async getProcessingStatus(id: string): Promise<SermonProcessResponse> {
    const response = await fetch(`${API_BASE_URL}/sermons/${id}/status`);

    if (!response.ok) {
      throw new Error('Failed to get processing status');
    }

    return response.json();
  },

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/sermons/health`);
      return response.ok;
    } catch {
      return false;
    }
  },

  async startBulkWaveform(directoryPath: string): Promise<BulkWaveformJobResponse> {
    const response = await fetch(`${API_BASE_URL}/sermons/bulk-waveform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directoryPath }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Failed to start bulk waveform generation');
    }

    return response.json();
  },

  async getWaveformJobStatus(jobId: string): Promise<WaveformJobStatus> {
    const response = await fetch(`${API_BASE_URL}/sermons/bulk-waveform/${jobId}/status`);

    if (!response.ok) {
      throw new Error('Failed to get job status');
    }

    return response.json();
  },

  async getWaveformData(jobId: string, filename: string): Promise<WaveformData> {
    const response = await fetch(
      `${API_BASE_URL}/sermons/bulk-waveform/${jobId}/waveform/${encodeURIComponent(filename)}`
    );

    if (!response.ok) {
      throw new Error('Failed to get waveform data');
    }

    return response.json();
  },

  async exportWaveformData(jobId: string, format: 'json' | 'csv' | 'zip'): Promise<ArrayBuffer> {
    const response = await fetch(
      `${API_BASE_URL}/sermons/bulk-waveform/${jobId}/export?format=${format}`
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Export failed' }));
      throw new Error(error.error || 'Failed to export waveform data');
    }

    return response.arrayBuffer();
  },
};

