namespace SermonSummarizationAPI.Services;

/// <summary>
/// Implementation of token tracking service
/// </summary>
public class TokenTrackingService : ITokenTrackingService
{
    private readonly Dictionary<string, (int summarization, int tagging)> _tokenUsage = new();
    private readonly object _lockObject = new();

    public void RecordTokenUsage(string requestId, int summarizationTokens, int taggingTokens)
    {
        lock (_lockObject)
        {
            _tokenUsage[requestId] = (summarizationTokens, taggingTokens);
        }
    }

    public int GetTotalTokens(string requestId)
    {
        lock (_lockObject)
        {
            if (_tokenUsage.TryGetValue(requestId, out var tokens))
            {
                return tokens.summarization + tokens.tagging;
            }
            return 0;
        }
    }

    public (int summarization, int tagging) GetTokenBreakdown(string requestId)
    {
        lock (_lockObject)
        {
            if (_tokenUsage.TryGetValue(requestId, out var tokens))
            {
                return tokens;
            }
            return (0, 0);
        }
    }
}

