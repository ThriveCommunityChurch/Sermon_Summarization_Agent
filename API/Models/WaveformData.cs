namespace SermonSummarizationAPI.Models;

/// <summary>
/// Waveform data for a specific audio file
/// </summary>
public class WaveformData
{
    /// <summary>
    /// Name of the audio file
    /// </summary>
    public string Filename { get; set; } = string.Empty;

    /// <summary>
    /// Array of normalized waveform amplitude values (0.15 to 1.0)
    /// </summary>
    public List<double> WaveformValues { get; set; } = new();

    /// <summary>
    /// Number of waveform samples
    /// </summary>
    public int SampleCount { get; set; }
}

