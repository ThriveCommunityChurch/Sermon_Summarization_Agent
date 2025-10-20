using SermonSummarizationAPI.Models;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for orchestrating sermon processing
/// </summary>
public interface ISermonProcessingService
{
    /// <summary>
    /// Process an uploaded sermon file
    /// </summary>
    /// <param name="request">The HTTP request containing the file</param>
    /// <returns>Processing result</returns>
    Task<SermonProcessResponse> ProcessUploadedFileAsync(HttpRequest request);

    /// <summary>
    /// Get processing status by ID
    /// </summary>
    /// <param name="id">Processing request ID</param>
    /// <returns>Processing status</returns>
    SermonProcessResponse? GetProcessingStatusAsync(string id);
}

