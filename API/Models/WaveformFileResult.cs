namespace SermonSummarizationAPI.Models;

/// <summary>
/// Result for a single file in a bulk waveform generation job
/// </summary>
public class WaveformFileResult
{
    /// <summary>
    /// Name of the audio file
    /// </summary>
    public string Filename { get; set; } = string.Empty;

    /// <summary>
    /// Processing status (pending, processing, success, error)
    /// </summary>
    public string Status { get; set; } = "pending";

    /// <summary>
    /// Number of waveform samples generated
    /// </summary>
    public int? SampleCount { get; set; }

    /// <summary>
    /// File size in megabytes
    /// </summary>
    public double? FileSizeMb { get; set; }

    /// <summary>
    /// Error message if processing failed
    /// </summary>
    public string? Error { get; set; }

    /// <summary>
    /// Path to the output waveform JSON file
    /// </summary>
    public string? OutputPath { get; set; }
}

