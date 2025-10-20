export interface TokenBreakdown {
  summarizationTokens: number;
  summarizationInputTokens?: number;
  summarizationOutputTokens?: number;
  taggingTokens: number;
  taggingInputTokens?: number;
  taggingOutputTokens?: number;
}

export interface SermonProcessResponse {
  id: string;
  summary: string;
  tags: string[];
  totalTokensUsed: number;
  tokenBreakdown: TokenBreakdown;
  status: string;
  error?: string;
  processedAt: string;
  processingDurationSeconds: number;
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
};

