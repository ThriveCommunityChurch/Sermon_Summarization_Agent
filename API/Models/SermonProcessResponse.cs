namespace SermonSummarizationAPI.Models;

/// <summary>
/// Response model for sermon processing results
/// </summary>
public class SermonProcessResponse
{
    /// <summary>
    /// Unique identifier for this processing request
    /// </summary>
    public string? Id { get; set; }

    /// <summary>
    /// The sermon summary
    /// </summary>
    public string? Summary { get; set; }

    /// <summary>
    /// Tags applied to the sermon
    /// </summary>
    public List<string>? Tags { get; set; }

    /// <summary>
    /// Pre-computed waveform data (480 normalized amplitude values between 0.15 and 1.0)
    /// </summary>
    public List<double>? WaveformData { get; set; }

    /// <summary>
    /// Total tokens consumed for this request
    /// </summary>
    public int TotalTokensUsed { get; set; }

    /// <summary>
    /// Breakdown of tokens by operation
    /// </summary>
    public TokenBreakdown? TokenBreakdown { get; set; }

    /// <summary>
    /// Processing status
    /// </summary>
    public string? Status { get; set; }

    /// <summary>
    /// Error message if processing failed
    /// </summary>
    public string? Error { get; set; }

    /// <summary>
    /// Timestamp when processing started
    /// </summary>
    public DateTime ProcessedAt { get; set; }

    /// <summary>
    /// Processing duration in seconds
    /// </summary>
    public double ProcessingDurationSeconds { get; set; }
}
