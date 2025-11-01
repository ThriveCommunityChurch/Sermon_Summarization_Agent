namespace SermonSummarizationAPI.Models;

/// <summary>
/// Token usage breakdown by operation
/// </summary>
public class TokenBreakdown
{
    /// <summary>
    /// Total tokens used for summarization (input + output)
    /// </summary>
    public int SummarizationTokens { get; set; }

    /// <summary>
    /// Input tokens used for summarization
    /// </summary>
    public int SummarizationInputTokens { get; set; }

    /// <summary>
    /// Output tokens used for summarization
    /// </summary>
    public int SummarizationOutputTokens { get; set; }

    /// <summary>
    /// Total tokens used for tagging (input + output)
    /// </summary>
    public int TaggingTokens { get; set; }

    /// <summary>
    /// Input tokens used for tagging
    /// </summary>
    public int TaggingInputTokens { get; set; }

    /// <summary>
    /// Output tokens used for tagging
    /// </summary>
    public int TaggingOutputTokens { get; set; }

    /// <summary>
    /// Total tokens used for clip generation (input + output)
    /// </summary>
    public int? ClipGenerationTokens { get; set; }

    /// <summary>
    /// Input tokens used for clip generation
    /// </summary>
    public int? ClipGenerationInputTokens { get; set; }

    /// <summary>
    /// Output tokens used for clip generation
    /// </summary>
    public int? ClipGenerationOutputTokens { get; set; }
}