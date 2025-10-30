import { useEffect, useRef, useState } from 'react';
import * as signalR from '@microsoft/signalr';
import type { WaveformFileResult } from '../services/api';

interface UseWaveformProgressOptions {
  jobId: string | null;
  onJobStarted?: (data: { jobId: string; totalFiles: number; startTime: string }) => void;
  onFileProgress?: (data: { jobId: string; currentFile: string; current: number; total: number }) => void;
  onFileComplete?: (data: { jobId: string; fileResult: WaveformFileResult }) => void;
  onJobComplete?: (data: { jobId: string; totalFiles: number; successfulFiles: number; failedFiles: number; durationSeconds: number }) => void;
  onJobFailed?: (data: { jobId: string; error: string }) => void;
}

export type ConnectionState = 'disconnected' | 'connecting' | 'connected';

export const useWaveformProgress = (options: UseWaveformProgressOptions) => {
  const { jobId, onJobStarted, onFileProgress, onFileComplete, onJobComplete, onJobFailed } = options;
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const connectionRef = useRef<signalR.HubConnection | null>(null);

  // Store callbacks in refs to avoid recreating connection on every render
  const callbacksRef = useRef({
    onJobStarted,
    onFileProgress,
    onFileComplete,
    onJobComplete,
    onJobFailed
  });

  // Update callbacks ref when they change
  useEffect(() => {
    callbacksRef.current = {
      onJobStarted,
      onFileProgress,
      onFileComplete,
      onJobComplete,
      onJobFailed
    };
  }, [onJobStarted, onFileProgress, onFileComplete, onJobComplete, onJobFailed]);

  useEffect(() => {
    if (!jobId) {
      // Clean up any existing connection
      if (connectionRef.current) {
        connectionRef.current.stop().catch(console.error);
        connectionRef.current = null;
      }
      setConnectionState('disconnected');
      return;
    }

    // Get base URL without /api suffix for SignalR hub
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';
    const baseUrl = apiUrl.replace(/\/api$/, '');

    const connection = new signalR.HubConnectionBuilder()
      .withUrl(`${baseUrl}/hubs/waveform-progress`, {
        withCredentials: false
      })
      .withAutomaticReconnect({
        nextRetryDelayInMilliseconds: (retryContext) => {
          // Exponential backoff: 0s, 2s, 10s, 30s, 30s...
          if (retryContext.previousRetryCount === 0) return 0;
          if (retryContext.previousRetryCount === 1) return 2000;
          if (retryContext.previousRetryCount === 2) return 10000;
          return 30000;
        }
      })
      .configureLogging(signalR.LogLevel.Information)
      .build();

    connectionRef.current = connection;

    // Register event handlers using refs to avoid dependency issues
    connection.on('JobStarted', (data) => {
      console.log('SignalR: JobStarted', data);
      callbacksRef.current.onJobStarted?.(data);
    });

    connection.on('FileProgress', (data) => {
      console.log('SignalR: FileProgress', data);
      callbacksRef.current.onFileProgress?.(data);
    });

    connection.on('FileComplete', (data) => {
      console.log('SignalR: FileComplete', data);
      callbacksRef.current.onFileComplete?.(data);
    });

    connection.on('JobComplete', (data) => {
      console.log('SignalR: JobComplete', data);
      callbacksRef.current.onJobComplete?.(data);
    });

    connection.on('JobFailed', (data) => {
      console.log('SignalR: JobFailed', data);
      callbacksRef.current.onJobFailed?.(data);
    });

    // Connection state handlers
    connection.onreconnecting((error) => {
      console.log('SignalR: Reconnecting...', error);
      setConnectionState('connecting');
    });

    connection.onreconnected((connectionId) => {
      console.log('SignalR: Reconnected', connectionId);
      setConnectionState('connected');
      // Re-subscribe to job after reconnection
      connection.invoke('SubscribeToJob', jobId).catch((err) => {
        console.error('Failed to re-subscribe to job:', err);
      });
    });

    connection.onclose((error) => {
      console.log('SignalR: Connection closed', error);
      setConnectionState('disconnected');
    });

    // Start connection
    const startConnection = async () => {
      try {
        setConnectionState('connecting');
        console.log('SignalR: Starting connection...');
        await connection.start();
        console.log('SignalR: Connected successfully');
        setConnectionState('connected');
        
        // Subscribe to job updates
        console.log('SignalR: Subscribing to job', jobId);
        await connection.invoke('SubscribeToJob', jobId);
        console.log('SignalR: Subscribed to job', jobId);
      } catch (error) {
        console.error('SignalR connection error:', error);
        setConnectionState('disconnected');
      }
    };

    startConnection();

    // Cleanup
    return () => {
      if (connection.state === signalR.HubConnectionState.Connected) {
        console.log('SignalR: Unsubscribing from job', jobId);
        connection.invoke('UnsubscribeFromJob', jobId).catch(console.error);
        connection.stop().catch(console.error);
      }
    };
  }, [jobId]); // Only depend on jobId, not the callbacks

  return { connectionState };
};

