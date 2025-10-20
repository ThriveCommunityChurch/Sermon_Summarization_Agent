namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for tracking token usage
/// </summary>
public interface ITokenTrackingService
{
    /// <summary>
    /// Record token usage for a processing request
    /// </summary>
    /// <param name="requestId">The processing request ID</param>
    /// <param name="summarizationTokens">Tokens used for summarization</param>
    /// <param name="taggingTokens">Tokens used for tagging</param>
    void RecordTokenUsage(string requestId, int summarizationTokens, int taggingTokens);

    /// <summary>
    /// Get total tokens used for a request
    /// </summary>
    /// <param name="requestId">The processing request ID</param>
    /// <returns>Total tokens used</returns>
    int GetTotalTokens(string requestId);

    /// <summary>
    /// Get token breakdown for a request
    /// </summary>
    /// <param name="requestId">The processing request ID</param>
    /// <returns>Token breakdown</returns>
    (int summarization, int tagging) GetTokenBreakdown(string requestId);
}

