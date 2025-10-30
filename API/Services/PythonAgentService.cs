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
    private readonly string _pythonExecutablePath;

    public PythonAgentService(ILogger<PythonAgentService> logger, ITokenTrackingService tokenTrackingService, IConfiguration configuration)
    {
        _logger = logger;
        _tokenTrackingService = tokenTrackingService;

        // Get the path to the Python agent
        // AppContext.BaseDirectory = API/bin/Debug/net9.0
        // We need to go up 4 levels to get to the repository root where agent.py is located
        // API/bin/Debug/net9.0 -> API/bin/Debug -> API/bin -> API -> Sermon_Summarization_Agent
        var binPath = AppContext.BaseDirectory;
        var repositoryRoot = Path.GetFullPath(Path.Combine(binPath, "..", "..", "..", ".."));

        // Get Python agent script path from configuration or use default
        var scriptPath = configuration["PythonAgent:ScriptPath"] ?? "agent.py";
        _pythonAgentPath = Path.GetFullPath(Path.Combine(repositoryRoot, scriptPath));

        // Get Python executable path from configuration
        // Sermon processing REQUIRES the virtual environment to ensure GPU-enabled dependencies
        // are available. We do NOT fall back to system Python.
        var configuredPythonPath = configuration["PythonAgent:PythonExecutablePath"];
        if (string.IsNullOrEmpty(configuredPythonPath))
        {
            throw new InvalidOperationException(
                "PythonAgent:PythonExecutablePath must be configured in appsettings.json. " +
                "Sermon processing requires the virtual environment with GPU-enabled dependencies. " +
                "Please run setup_venv_gpu.bat to create the virtual environment."
            );
        }

        _pythonExecutablePath = Path.GetFullPath(Path.Combine(repositoryRoot, configuredPythonPath));

        _logger.LogInformation("Repository root: {RepositoryRoot}", repositoryRoot);
        _logger.LogInformation("Python agent path: {PythonAgentPath}", _pythonAgentPath);
        _logger.LogInformation("Python executable path: {PythonExecutablePath}", _pythonExecutablePath);

        // Verify paths exist - fail fast if they don't
        if (!File.Exists(_pythonAgentPath))
        {
            throw new FileNotFoundException(
                $"Python agent script not found at: {_pythonAgentPath}. " +
                "Please ensure agent.py exists in the repository root."
            );
        }

        if (!File.Exists(_pythonExecutablePath))
        {
            throw new FileNotFoundException(
                $"Python executable not found at: {_pythonExecutablePath}. " +
                "Please run setup_venv_gpu.bat to create the virtual environment with GPU-enabled dependencies."
            );
        }
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

                // Extract waveform data if available
                List<double>? waveformData = null;
                if (summaryData.TryGetProperty("waveform_data", out var waveformElement) && waveformElement.ValueKind == JsonValueKind.Array)
                {
                    var waveform = new List<double>();
                    foreach (var value in waveformElement.EnumerateArray())
                    {
                        if (value.ValueKind == JsonValueKind.Number)
                        {
                            waveform.Add(Math.Round(value.GetDouble(), 3));
                        }
                    }

                    // Validate waveform data (should be exactly 480 values)
                    if (waveform.Count == 480)
                    {
                        waveformData = waveform;
                        _logger.LogInformation("Extracted waveform data: {Count} values", waveform.Count);
                    }
                    else
                    {
                        _logger.LogWarning("Waveform data has unexpected count: {Count} (expected 480)", waveform.Count);
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
                    WaveformData = waveformData,
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
        _logger.LogInformation("Starting Python agent with executable: {PythonExecutable}", _pythonExecutablePath);

        var processInfo = new ProcessStartInfo
        {
            FileName = _pythonExecutablePath,
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

