using SermonSummarizationAPI.Models;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for bulk waveform generation operations
/// </summary>
public interface IWaveformService
{
    /// <summary>
    /// Start a bulk waveform generation job for all audio files in a directory
    /// </summary>
    /// <param name="directoryPath">Path to directory containing audio files</param>
    /// <returns>Job response with job ID and initial status</returns>
    Task<BulkWaveformJobResponse> StartBulkWaveformJobAsync(string directoryPath);

    /// <summary>
    /// Get the current status of a waveform generation job
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <returns>Current job status, or null if job not found</returns>
    WaveformJobStatus? GetJobStatus(string jobId);

    /// <summary>
    /// Get waveform data for a specific file in a job
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <param name="filename">Name of the audio file</param>
    /// <returns>Waveform data, or null if not found</returns>
    Task<WaveformData?> GetWaveformDataAsync(string jobId, string filename);

    /// <summary>
    /// Export waveform data for a completed job in the specified format
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <param name="format">Export format (json, csv, zip)</param>
    /// <returns>Tuple of (fileBytes, contentType, filename), or null if job not found</returns>
    Task<(byte[] FileBytes, string ContentType, string Filename)?> ExportWaveformDataAsync(string jobId, string format);
}

