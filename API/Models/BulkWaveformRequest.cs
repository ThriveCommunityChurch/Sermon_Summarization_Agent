namespace SermonSummarizationAPI.Models;

/// <summary>
/// Request model for starting a bulk waveform generation job
/// </summary>
public class BulkWaveformRequest
{
    /// <summary>
    /// Path to directory containing audio files to process
    /// </summary>
    public string DirectoryPath { get; set; } = string.Empty;
}

