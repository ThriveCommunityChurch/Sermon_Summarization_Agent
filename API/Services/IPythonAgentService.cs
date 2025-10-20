using SermonSummarizationAPI.Models;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for communicating with the Python sermon summarization agent
/// </summary>
public interface IPythonAgentService
{
    /// <summary>
    /// Process a sermon file through the Python agent
    /// </summary>
    /// <param name="filePath">Path to the audio/video file</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Processing result with summary, tags, and token usage</returns>
    Task<SermonProcessResponse> ProcessSermonAsync(string filePath, CancellationToken cancellationToken = default);
}

