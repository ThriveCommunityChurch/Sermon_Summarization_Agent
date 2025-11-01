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

            // Copy the input file to the temp directory to ensure all outputs are in the same location
            var originalFileName = Path.GetFileName(filePath);
            var tempInputPath = Path.Combine(tempDir, originalFileName);
            File.Copy(filePath, tempInputPath, overwrite: true);
            _logger.LogInformation("Copied input file to temp directory: {TempInputPath}", tempInputPath);

            // Determine if this is a video file (for clip generation)
            var isVideoFile = IsVideoFile(filePath);
            _logger.LogInformation("File type: {FileType}", isVideoFile ? "Video" : "Audio");

            // Run the Python agent
            var result = await RunPythonAgentAsync(tempInputPath, tempDir, isVideoFile, cancellationToken);

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

            // Check for video clip outputs (only for video files)
            var (videoClipGenerated, videoClipFilename, videoClipMetadata) = await CheckForVideoClipOutputsAsync(tempDir, originalFileName, cancellationToken);

            // Extract clip generation tokens from video clip metadata if available
            if (videoClipGenerated && videoClipMetadata != null)
            {
                ExtractClipGenerationTokens(videoClipMetadata, tokenBreakdown);
                totalTokens += tokenBreakdown.ClipGenerationTokens ?? 0;
            }

            // Construct full video clip path if video was generated
            string? videoClipPath = null;
            if (videoClipGenerated && !string.IsNullOrEmpty(videoClipFilename))
            {
                videoClipPath = Path.Combine(tempDir, videoClipFilename);
                _logger.LogInformation("Video clip path: {VideoClipPath}", videoClipPath);
            }

            var response = new SermonProcessResponse
            {
                Id = requestId,
                Summary = summary,
                Tags = tags,
                WaveformData = waveformData,
                TotalTokensUsed = totalTokens,
                TokenBreakdown = tokenBreakdown,
                VideoClipGenerated = videoClipGenerated,
                VideoClipFilename = videoClipFilename,
                VideoClipPath = videoClipPath,
                VideoClipMetadata = videoClipMetadata,
                Status = "completed",
                ProcessedAt = DateTime.UtcNow,
                ProcessingDurationSeconds = (DateTime.UtcNow - startTime).TotalSeconds
            };

            _logger.LogInformation("Sermon processing completed successfully. Tokens used: {TotalTokens}, Video clip generated: {VideoClipGenerated}", totalTokens, videoClipGenerated);

            // Only clean up temp directory if no video clip was generated
            // If video clip exists, the SermonProcessingService will handle cleanup later
            if (!videoClipGenerated)
            {
                try
                {
                    Directory.Delete(tempDir, true);
                    _logger.LogInformation("Cleaned up temporary directory (no video clip): {TempDir}", tempDir);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning("Failed to clean up temporary directory: {Error}", ex.Message);
                }
            }
            else
            {
                _logger.LogInformation("Preserving temporary directory for video clip: {TempDir}", tempDir);
            }

            return response;
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

    private async Task<bool> RunPythonAgentAsync(string filePath, string outputDir, bool enableClipGeneration, CancellationToken cancellationToken)
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

        // Set environment variable to enable/disable clip generation based on file type
        processInfo.EnvironmentVariables["ENABLE_CLIP_GENERATION"] = enableClipGeneration.ToString().ToLower();

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

    private void ExtractClipGenerationTokens(object videoClipMetadata, TokenBreakdown tokenBreakdown)
    {
        try
        {
            // Convert metadata object to JsonElement for parsing
            var metadataJson = JsonSerializer.Serialize(videoClipMetadata);
            var metadataElement = JsonDocument.Parse(metadataJson).RootElement;

            // Extract tokens from video clip metadata
            if (metadataElement.TryGetProperty("tokens", out var tokensElement))
            {
                if (tokensElement.TryGetProperty("total", out var totalElement))
                {
                    tokenBreakdown.ClipGenerationTokens = totalElement.GetInt32();
                }
                if (tokensElement.TryGetProperty("input", out var inputElement))
                {
                    tokenBreakdown.ClipGenerationInputTokens = inputElement.GetInt32();
                }
                if (tokensElement.TryGetProperty("output", out var outputElement))
                {
                    tokenBreakdown.ClipGenerationOutputTokens = outputElement.GetInt32();
                }

                _logger.LogInformation("Extracted clip generation tokens: Total={Total}, Input={Input}, Output={Output}",
                    tokenBreakdown.ClipGenerationTokens,
                    tokenBreakdown.ClipGenerationInputTokens,
                    tokenBreakdown.ClipGenerationOutputTokens);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to extract clip generation tokens from metadata");
        }
    }

    private bool IsVideoFile(string filePath)
    {
        var videoExtensions = new[] { ".mp4", ".mov", ".avi", ".mkv", ".webm" };
        var extension = Path.GetExtension(filePath).ToLower();
        return videoExtensions.Contains(extension);
    }

    private async Task<(bool generated, string? filename, object? metadata)> CheckForVideoClipOutputsAsync(
        string tempDir,
        string originalFileName,
        CancellationToken cancellationToken)
    {
        try
        {
            // Construct expected video clip filename: {original_stem}_Summary.mp4
            var originalStem = Path.GetFileNameWithoutExtension(originalFileName);
            var videoClipFilename = $"{originalStem}_Summary.mp4";
            var videoClipPath = Path.Combine(tempDir, videoClipFilename);

            // Check if video clip was generated
            if (!File.Exists(videoClipPath))
            {
                _logger.LogInformation("No video clip found at: {VideoClipPath}", videoClipPath);
                return (false, null, null);
            }

            _logger.LogInformation("Video clip found: {VideoClipFilename}", videoClipFilename);

            // Check for metadata JSON
            var metadataFilename = $"{originalStem}_Summary_metadata.json";
            var metadataPath = Path.Combine(tempDir, metadataFilename);

            object? metadata = null;
            if (File.Exists(metadataPath))
            {
                var metadataJson = await File.ReadAllTextAsync(metadataPath, cancellationToken);
                metadata = JsonSerializer.Deserialize<JsonElement>(metadataJson);
                _logger.LogInformation("Video clip metadata loaded from: {MetadataFilename}", metadataFilename);
            }
            else
            {
                _logger.LogWarning("Video clip metadata not found at: {MetadataPath}", metadataPath);
            }

            return (true, videoClipFilename, metadata);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error checking for video clip outputs");
            return (false, null, null);
        }
    }
}

