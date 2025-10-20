namespace SermonSummarizationAPI.Models;

/// <summary>
/// Request model for processing a sermon file
/// </summary>
public class SermonProcessRequest
{
    /// <summary>
    /// The audio or video file to process
    /// </summary>
    public IFormFile? File { get; set; }

    /// <summary>
    /// Optional file path if processing from server
    /// </summary>
    public string? FilePath { get; set; }
}

