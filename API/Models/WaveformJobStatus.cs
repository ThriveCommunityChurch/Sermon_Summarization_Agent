namespace SermonSummarizationAPI.Models;

/// <summary>
/// Status information for a bulk waveform generation job
/// </summary>
public class WaveformJobStatus
{
    /// <summary>
    /// Unique identifier for the job
    /// </summary>
    public string JobId { get; set; } = string.Empty;

    /// <summary>
    /// Current status (queued, processing, completed, failed)
    /// </summary>
    public string Status { get; set; } = "queued";

    /// <summary>
    /// Total number of files to process
    /// </summary>
    public int TotalFiles { get; set; }

    /// <summary>
    /// Number of files that have been processed (completed or failed)
    /// </summary>
    public int ProcessedFiles { get; set; }

    /// <summary>
    /// Number of files successfully processed
    /// </summary>
    public int SuccessfulFiles { get; set; }

    /// <summary>
    /// Number of files that failed processing
    /// </summary>
    public int FailedFiles { get; set; }

    /// <summary>
    /// Name of the file currently being processed
    /// </summary>
    public string? CurrentFile { get; set; }

    /// <summary>
    /// Time when the job started
    /// </summary>
    public DateTime StartTime { get; set; }

    /// <summary>
    /// Time when the job completed (null if still running)
    /// </summary>
    public DateTime? EndTime { get; set; }

    /// <summary>
    /// Elapsed time in seconds
    /// </summary>
    public double? ElapsedSeconds { get; set; }

    /// <summary>
    /// Estimated remaining time in seconds
    /// </summary>
    public double? EstimatedRemainingSeconds { get; set; }

    /// <summary>
    /// List of file processing results
    /// </summary>
    public List<WaveformFileResult> Results { get; set; } = new();

    /// <summary>
    /// Error message if the job failed
    /// </summary>
    public string? Error { get; set; }
}

