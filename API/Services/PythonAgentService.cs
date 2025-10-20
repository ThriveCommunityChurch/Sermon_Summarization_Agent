using System.Diagnostics;
using System.Text.Json;
using SermonSummarizationAPI.Models;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for communicating with the Python sermon summarization agent
/// </summary>
public class PythonAgentService : IPythonAgentService
{
    private readonly ILogger<PythonAgentService> _logger;
    private readonly ITokenTrackingService _tokenTrackingService;
    private readonly string _pythonAgentPath;

    public PythonAgentService(ILogger<PythonAgentService> logger, ITokenTrackingService tokenTrackingService)
    {
        _logger = logger;
        _tokenTrackingService = tokenTrackingService;

        // Get the path to the Python agent
        // AppContext.BaseDirectory = bin/Debug/net9.0
        // We need to go up 4 levels to get to the repository root where agent.py is located
        // bin/Debug/net9.0 -> bin -> Debug -> net9.0 -> API -> Sermon_Summarization_Agent
        var binPath = AppContext.BaseDirectory;
        var repositoryRoot = Path.GetFullPath(Path.Combine(binPath, "..", "..", "..", ".."));
        _pythonAgentPath = Path.Combine(repositoryRoot, "agent.py");

        _logger.LogInformation("Python agent path: {PythonAgentPath}", _pythonAgentPath);
    }

    public async Task<SermonProcessResponse> ProcessSermonAsync(string filePath, CancellationToken cancellationToken = default)
    {
        var requestId = Guid.NewGuid().ToString();
        var startTime = DateTime.UtcNow;

        try
        {
            _logger.LogInformation("Starting sermon processing for file: {FilePath}", filePath);

            // Create a temporary directory for this processing request
            var tempDir = Path.Combine(Path.GetTempPath(), requestId);
            Directory.CreateDirectory(tempDir);

            try
            {
                // Run the Python agent
                var result = await RunPythonAgentAsync(filePath, tempDir, cancellationToken);

                // Read the results from the output files
                var summaryJsonPath = Path.Combine(tempDir, "summary.json");
                if (!File.Exists(summaryJsonPath))
                {
                    throw new FileNotFoundException("Summary JSON file not found after processing");
                }

                var summaryJson = await File.ReadAllTextAsync(summaryJsonPath, cancellationToken);
                var summaryData = JsonSerializer.Deserialize<JsonElement>(summaryJson);

                // Extract summary and tags
                var summary = summaryData.GetProperty("summary").GetString() ?? "";
                var tags = new List<string>();
                
                if (summaryData.TryGetProperty("tags", out var tagsElement) && tagsElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (var tag in tagsElement.EnumerateArray())
                    {
                        if (tag.GetString() is string tagStr)
                        {
                            tags.Add(tagStr);
                        }
                    }
                }

                // Extract token usage if available
                var tokenBreakdown = ExtractTokenUsage(summaryData);
                _tokenTrackingService.RecordTokenUsage(requestId, tokenBreakdown.SummarizationTokens, tokenBreakdown.TaggingTokens);

                var totalTokens = tokenBreakdown.SummarizationTokens + tokenBreakdown.TaggingTokens;

                var response = new SermonProcessResponse
                {
                    Id = requestId,
                    Summary = summary,
                    Tags = tags,
                    TotalTokensUsed = totalTokens,
                    TokenBreakdown = tokenBreakdown,
                    Status = "completed",
                    ProcessedAt = DateTime.UtcNow,
                    ProcessingDurationSeconds = (DateTime.UtcNow - startTime).TotalSeconds
                };

                _logger.LogInformation("Sermon processing completed successfully. Tokens used: {TotalTokens}", totalTokens);
                return response;
            }
            finally
            {
                // Clean up temporary directory
                try
                {
                    Directory.Delete(tempDir, true);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning("Failed to clean up temporary directory: {Error}", ex.Message);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing sermon");
            return new SermonProcessResponse
            {
                Id = requestId,
                Status = "failed",
                Error = ex.Message,
                ProcessedAt = DateTime.UtcNow,
                ProcessingDurationSeconds = (DateTime.UtcNow - startTime).TotalSeconds
            };
        }
    }

    private async Task<bool> RunPythonAgentAsync(string filePath, string outputDir, CancellationToken cancellationToken)
    {
        var processInfo = new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"\"{_pythonAgentPath}\" --file \"{filePath}\"",
            WorkingDirectory = outputDir,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        using var process = Process.Start(processInfo);
        if (process == null)
        {
            throw new InvalidOperationException("Failed to start Python process");
        }

        var output = await process.StandardOutput.ReadToEndAsync();
        var error = await process.StandardError.ReadToEndAsync();

        await process.WaitForExitAsync(cancellationToken);

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"Python agent failed with exit code {process.ExitCode}: {error}");
        }

        _logger.LogInformation("Python agent output: {Output}", output);
        return true;
    }

    private TokenBreakdown ExtractTokenUsage(JsonElement summaryData)
    {
        var breakdown = new TokenBreakdown();

        // Try to extract token usage from the summary data
        if (summaryData.TryGetProperty("tokens", out var tokensElement))
        {
            // Extract summarization tokens
            if (tokensElement.TryGetProperty("summarization", out var summarizationElement))
            {
                breakdown.SummarizationTokens = summarizationElement.GetInt32();
            }
            if (tokensElement.TryGetProperty("summarization_input", out var summarizationInputElement))
            {
                breakdown.SummarizationInputTokens = summarizationInputElement.GetInt32();
            }
            if (tokensElement.TryGetProperty("summarization_output", out var summarizationOutputElement))
            {
                breakdown.SummarizationOutputTokens = summarizationOutputElement.GetInt32();
            }

            // Extract tagging tokens
            if (tokensElement.TryGetProperty("tagging", out var taggingElement))
            {
                breakdown.TaggingTokens = taggingElement.GetInt32();
            }
            if (tokensElement.TryGetProperty("tagging_input", out var taggingInputElement))
            {
                breakdown.TaggingInputTokens = taggingInputElement.GetInt32();
            }
            if (tokensElement.TryGetProperty("tagging_output", out var taggingOutputElement))
            {
                breakdown.TaggingOutputTokens = taggingOutputElement.GetInt32();
            }
        }

        return breakdown;
    }
}

