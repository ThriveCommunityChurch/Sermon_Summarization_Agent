namespace SermonSummarizationAPI.Models;

/// <summary>
/// Response model when starting a bulk waveform generation job
/// </summary>
public class BulkWaveformJobResponse
{
    /// <summary>
    /// Unique identifier for the job
    /// </summary>
    public string JobId { get; set; } = string.Empty;

    /// <summary>
    /// Current status of the job (queued, processing, completed, failed)
    /// </summary>
    public string Status { get; set; } = "queued";

    /// <summary>
    /// Message describing the job status or any errors
    /// </summary>
    public string Message { get; set; } = string.Empty;
}

