using System.Diagnostics;
using System.Text.Json;
using System.Text;
using System.IO.Compression;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.AspNetCore.SignalR;
using SermonSummarizationAPI.Models;
using SermonSummarizationAPI.Hubs;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service implementation for bulk waveform generation
/// </summary>
public class WaveformService : IWaveformService
{
    private readonly IMemoryCache _cache;
    private readonly ILogger<WaveformService> _logger;
    private readonly IConfiguration _configuration;
    private readonly IHubContext<WaveformProgressHub> _hubContext;
    private readonly string _pythonExecutablePath;
    private readonly string _bulkWaveformScriptPath;

    public WaveformService(
        IMemoryCache cache,
        ILogger<WaveformService> logger,
        IConfiguration configuration,
        IHubContext<WaveformProgressHub> hubContext)
    {
        _cache = cache;
        _logger = logger;
        _configuration = configuration;
        _hubContext = hubContext;

        // Get repository root (parent of API directory)
        var apiDirectory = Directory.GetCurrentDirectory();
        var repositoryRoot = Directory.GetParent(apiDirectory)?.FullName ?? apiDirectory;

        // Get Python executable path for bulk waveform generation
        // Uses separate configuration from PythonAgentService since bulk waveform
        // only needs basic audio processing (librosa) without GPU requirements
        var configuredPythonPath = configuration["PythonAgent:BulkWaveformPythonExecutablePath"];
        if (!string.IsNullOrEmpty(configuredPythonPath))
        {
            _pythonExecutablePath = Path.GetFullPath(Path.Combine(repositoryRoot, configuredPythonPath));
        }
        else
        {
            // Fallback to system Python if not configured
            _pythonExecutablePath = "python";
        }

        // Get bulk waveform script path
        _bulkWaveformScriptPath = Path.GetFullPath(
            Path.Combine(repositoryRoot, "bulk_waveform_generator.py")
        );

        _logger.LogInformation("WaveformService initialized with Python: {PythonPath}", _pythonExecutablePath);
        _logger.LogInformation("Bulk waveform script: {ScriptPath}", _bulkWaveformScriptPath);

        // Verify paths exist
        if (!File.Exists(_bulkWaveformScriptPath))
        {
            _logger.LogWarning("Bulk waveform script not found at: {ScriptPath}", _bulkWaveformScriptPath);
        }
        if (_pythonExecutablePath != "python" && !File.Exists(_pythonExecutablePath))
        {
            _logger.LogWarning("Python executable not found at: {PythonExecutablePath}. Falling back to system Python.", _pythonExecutablePath);
            _pythonExecutablePath = "python";
        }

        // Clean up old temp directories on startup
        CleanupOldTempDirectories();
    }

    public Task<BulkWaveformJobResponse> StartBulkWaveformJobAsync(string directoryPath)
    {
        try
        {
            // Validate directory exists
            if (!Directory.Exists(directoryPath))
            {
                return Task.FromResult(new BulkWaveformJobResponse
                {
                    Status = "failed",
                    Message = $"Directory not found: {directoryPath}"
                });
            }

            // Generate unique job ID
            var jobId = Guid.NewGuid().ToString();

            // Create initial job state
            var jobState = new WaveformJobStatus
            {
                JobId = jobId,
                Status = "queued",
                StartTime = DateTime.UtcNow,
                TotalFiles = 0,
                ProcessedFiles = 0,
                SuccessfulFiles = 0,
                FailedFiles = 0,
                Results = new List<WaveformFileResult>()
            };

            // Store in cache with 1 hour expiration
            var cacheOptions = new MemoryCacheEntryOptions
            {
                SlidingExpiration = TimeSpan.FromHours(1)
            };

            _cache.Set(jobId, jobState, cacheOptions);

            _logger.LogInformation("Starting bulk waveform job {JobId} for directory: {Directory}", jobId, directoryPath);

            // Start background task to process files
            _ = Task.Run(async () => await ProcessBulkWaveformJobAsync(jobId, directoryPath));

            return Task.FromResult(new BulkWaveformJobResponse
            {
                JobId = jobId,
                Status = "queued",
                Message = "Job started successfully"
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error starting bulk waveform job");
            return Task.FromResult(new BulkWaveformJobResponse
            {
                Status = "failed",
                Message = $"Error starting job: {ex.Message}"
            });
        }
    }

    public WaveformJobStatus? GetJobStatus(string jobId)
    {
        if (_cache.TryGetValue(jobId, out WaveformJobStatus? jobState) && jobState != null)
        {
            // Calculate elapsed time
            var elapsed = DateTime.UtcNow - jobState.StartTime;
            jobState.ElapsedSeconds = elapsed.TotalSeconds;

            // Calculate estimated remaining time
            if (jobState.ProcessedFiles > 0 && jobState.Status == "processing")
            {
                var avgTimePerFile = elapsed.TotalSeconds / jobState.ProcessedFiles;
                var remainingFiles = jobState.TotalFiles - jobState.ProcessedFiles;
                jobState.EstimatedRemainingSeconds = avgTimePerFile * remainingFiles;
            }

            return jobState;
        }

        return null;
    }

    public async Task<WaveformData?> GetWaveformDataAsync(string jobId, string filename)
    {
        try
        {
            // Construct path to waveform JSON file in temp directory
            var tempWaveformDir = Path.Combine(Path.GetTempPath(), "SermonWaveforms", jobId);
            var filenameWithoutExt = Path.GetFileNameWithoutExtension(filename);
            var waveformFilePath = Path.Combine(tempWaveformDir, $"{filenameWithoutExt}.json");

            if (!File.Exists(waveformFilePath))
            {
                _logger.LogWarning("Waveform file not found: {FilePath}", waveformFilePath);
                return null;
            }

            // Read and parse JSON file
            var jsonContent = await File.ReadAllTextAsync(waveformFilePath);
            var jsonDoc = JsonDocument.Parse(jsonContent);
            var root = jsonDoc.RootElement;

            var waveformData = new WaveformData
            {
                Filename = root.GetProperty("filename").GetString() ?? filename,
                SampleCount = root.GetProperty("sample_count").GetInt32(),
                WaveformValues = []
            };

            // Parse waveform_data array
            if (root.TryGetProperty("waveform_data", out var waveformArray))
            {
                foreach (var value in waveformArray.EnumerateArray())
                {
                    waveformData.WaveformValues.Add(Math.Round(value.GetDouble(), 3));
                }
            }

            return waveformData;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error reading waveform data for job {JobId}, file {Filename}", jobId, filename);
            return null;
        }
    }

    private async Task ProcessBulkWaveformJobAsync(string jobId, string directoryPath)
    {
        try
        {
            // Update job status to processing
            UpdateJobState(jobId, state =>
            {
                state.Status = "processing";
            });

            _logger.LogInformation("Processing bulk waveform job {JobId}", jobId);

            // Create temp output directory for this job
            var tempOutputDir = Path.Combine(Path.GetTempPath(), "SermonWaveforms", jobId);
            Directory.CreateDirectory(tempOutputDir);

            // Execute Python script
            var processInfo = new ProcessStartInfo
            {
                FileName = _pythonExecutablePath,
                Arguments = $"\"{_bulkWaveformScriptPath}\" --directory \"{directoryPath}\" --job-id \"{jobId}\" --output-dir \"{tempOutputDir}\"",
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

            // Read stdout line by line and parse JSON progress updates
            while (!process.StandardOutput.EndOfStream)
            {
                var line = await process.StandardOutput.ReadLineAsync();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    await ProcessProgressLineAsync(jobId, line);
                }
            }

            // Wait for process to complete
            await process.WaitForExitAsync();

            // Check for errors
            if (process.ExitCode != 0)
            {
                var errorOutput = await process.StandardError.ReadToEndAsync();
                _logger.LogError("Python script failed with exit code {ExitCode}: {Error}", process.ExitCode, errorOutput);

                UpdateJobState(jobId, state =>
                {
                    state.Status = "failed";
                    state.Error = $"Processing failed: {errorOutput}";
                    state.EndTime = DateTime.UtcNow;
                });

                // Broadcast job failed via SignalR
                await _hubContext.Clients.Group($"job-{jobId}")
                    .SendAsync("JobFailed", new
                    {
                        jobId,
                        error = $"Processing failed: {errorOutput}"
                    });
            }
            else
            {
                // Mark job as completed if not already marked
                var jobState = GetJobStatus(jobId);
                UpdateJobState(jobId, state =>
                {
                    if (state.Status == "processing")
                    {
                        state.Status = "completed";
                        state.EndTime = DateTime.UtcNow;
                    }
                });

                // Broadcast job complete via SignalR
                if (jobState != null)
                {
                    await _hubContext.Clients.Group($"job-{jobId}")
                        .SendAsync("JobComplete", new
                        {
                            jobId,
                            totalFiles = jobState.TotalFiles,
                            successfulFiles = jobState.SuccessfulFiles,
                            failedFiles = jobState.FailedFiles,
                            durationSeconds = jobState.ElapsedSeconds
                        });
                }

                _logger.LogInformation("Bulk waveform job {JobId} completed successfully", jobId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing bulk waveform job {JobId}", jobId);

            UpdateJobState(jobId, state =>
            {
                state.Status = "failed";
                state.Error = ex.Message;
                state.EndTime = DateTime.UtcNow;
            });

            // Broadcast job failed via SignalR
            await _hubContext.Clients.Group($"job-{jobId}")
                .SendAsync("JobFailed", new
                {
                    jobId,
                    error = ex.Message
                });
        }
    }

    private async Task ProcessProgressLineAsync(string jobId, string line)
    {
        try
        {
            var jsonDoc = JsonDocument.Parse(line);
            var root = jsonDoc.RootElement;

            if (!root.TryGetProperty("type", out var typeElement))
            {
                return;
            }

            var progressType = typeElement.GetString();

            switch (progressType)
            {
                case "started":
                    if (root.TryGetProperty("total_files", out var totalFiles))
                    {
                        var totalFilesCount = totalFiles.GetInt32();
                        UpdateJobState(jobId, state =>
                        {
                            state.TotalFiles = totalFilesCount;
                            state.Status = "processing";
                        });

                        // Broadcast job started via SignalR
                        await _hubContext.Clients.Group($"job-{jobId}")
                            .SendAsync("JobStarted", new
                            {
                                jobId,
                                totalFiles = totalFilesCount,
                                startTime = DateTime.UtcNow
                            });
                    }
                    break;

                case "progress":
                    if (root.TryGetProperty("filename", out var filename) &&
                        root.TryGetProperty("current", out var current) &&
                        root.TryGetProperty("total", out var total))
                    {
                        var currentFile = filename.GetString();
                        var currentIndex = current.GetInt32();
                        var totalCount = total.GetInt32();

                        UpdateJobState(jobId, state =>
                        {
                            state.CurrentFile = currentFile;
                        });

                        // Broadcast file progress via SignalR
                        await _hubContext.Clients.Group($"job-{jobId}")
                            .SendAsync("FileProgress", new
                            {
                                jobId,
                                currentFile,
                                current = currentIndex,
                                total = totalCount
                            });
                    }
                    break;

                case "file_complete":
                    await ProcessFileCompleteAsync(jobId, root);
                    break;

                case "completed":
                    UpdateJobState(jobId, state =>
                    {
                        state.Status = "completed";
                        state.EndTime = DateTime.UtcNow;
                        state.CurrentFile = null;
                    });
                    break;

                case "error":
                    if (root.TryGetProperty("error", out var error))
                    {
                        var errorMessage = error.GetString();
                        UpdateJobState(jobId, state =>
                        {
                            state.Status = "failed";
                            state.Error = errorMessage;
                            state.EndTime = DateTime.UtcNow;
                        });

                        // Broadcast job failed via SignalR
                        await _hubContext.Clients.Group($"job-{jobId}")
                            .SendAsync("JobFailed", new
                            {
                                jobId,
                                error = errorMessage
                            });
                    }
                    break;
            }
        }
        catch (JsonException ex)
        {
            _logger.LogWarning(ex, "Failed to parse progress line: {Line}", line);
        }
    }

    private async Task ProcessFileCompleteAsync(string jobId, JsonElement root)
    {
        var fileResult = new WaveformFileResult();

        if (root.TryGetProperty("filename", out var filename))
            fileResult.Filename = filename.GetString() ?? "";

        if (root.TryGetProperty("status", out var status))
            fileResult.Status = status.GetString() ?? "unknown";

        if (root.TryGetProperty("sample_count", out var sampleCount))
            fileResult.SampleCount = sampleCount.GetInt32();

        if (root.TryGetProperty("file_size_mb", out var fileSizeMb))
            fileResult.FileSizeMb = fileSizeMb.GetDouble();

        if (root.TryGetProperty("error", out var error))
            fileResult.Error = error.GetString();

        if (root.TryGetProperty("output_path", out var outputPath))
            fileResult.OutputPath = outputPath.GetString();

        UpdateJobState(jobId, state =>
        {
            // Add or update file result
            var existingResult = state.Results.FirstOrDefault(r => r.Filename == fileResult.Filename);
            if (existingResult != null)
            {
                state.Results.Remove(existingResult);
            }
            state.Results.Add(fileResult);

            // Update counters
            state.ProcessedFiles = state.Results.Count(r => r.Status == "success" || r.Status == "error");
            state.SuccessfulFiles = state.Results.Count(r => r.Status == "success");
            state.FailedFiles = state.Results.Count(r => r.Status == "error");
        });

        // Broadcast file complete via SignalR
        await _hubContext.Clients.Group($"job-{jobId}")
            .SendAsync("FileComplete", new
            {
                jobId,
                fileResult
            });
    }

    private void UpdateJobState(string jobId, Action<WaveformJobStatus> updateAction)
    {
        if (_cache.TryGetValue(jobId, out WaveformJobStatus? jobState) && jobState != null)
        {
            updateAction(jobState);
            _cache.Set(jobId, jobState, new MemoryCacheEntryOptions
            {
                SlidingExpiration = TimeSpan.FromHours(1)
            });
        }
    }

    private void CleanupJobFiles(string jobId)
    {
        try
        {
            var tempOutputDir = Path.Combine(Path.GetTempPath(), "SermonWaveforms", jobId);
            if (Directory.Exists(tempOutputDir))
            {
                Directory.Delete(tempOutputDir, recursive: true);
                _logger.LogInformation("Cleaned up waveform files for job {JobId}", jobId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to clean up files for job {JobId}", jobId);
        }
    }

    private void CleanupOldTempDirectories()
    {
        try
        {
            var tempWaveformsDir = Path.Combine(Path.GetTempPath(), "SermonWaveforms");
            if (!Directory.Exists(tempWaveformsDir))
            {
                return;
            }

            // Delete directories older than 7 days
            var cutoffTime = DateTime.Now.AddDays(-7);
            var directories = Directory.GetDirectories(tempWaveformsDir);

            foreach (var dir in directories)
            {
                try
                {
                    var dirInfo = new DirectoryInfo(dir);
                    if (dirInfo.LastWriteTime < cutoffTime)
                    {
                        Directory.Delete(dir, recursive: true);
                        _logger.LogInformation("Cleaned up old temp waveform directory: {Directory}", dir);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to clean up temp directory: {Directory}", dir);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during temp directory cleanup");
        }
    }

    public async Task<(byte[] FileBytes, string ContentType, string Filename)?> ExportWaveformDataAsync(string jobId, string format)
    {
        try
        {
            // Get job status
            var jobStatus = GetJobStatus(jobId);
            if (jobStatus == null)
            {
                _logger.LogWarning("Export requested for non-existent job: {JobId}", jobId);
                return null;
            }

            // Check if job is completed
            if (jobStatus.Status != "completed")
            {
                _logger.LogWarning("Export requested for incomplete job: {JobId}, Status: {Status}", jobId, jobStatus.Status);
                return null;
            }

            // Get temp directory for this job
            var tempOutputDir = Path.Combine(Path.GetTempPath(), "SermonWaveforms", jobId);
            if (!Directory.Exists(tempOutputDir))
            {
                _logger.LogWarning("Temp directory not found for job: {JobId}", jobId);
                return null;
            }

            return format.ToLower() switch
            {
                "json" => await ExportAsJsonAsync(jobId, jobStatus, tempOutputDir),
                "csv" => await ExportAsCsvAsync(jobId, jobStatus, tempOutputDir),
                "zip" => await ExportAsZipAsync(jobId, jobStatus, tempOutputDir),
                _ => null
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error exporting waveform data for job {JobId}", jobId);
            return null;
        }
    }

    private async Task<(byte[] FileBytes, string ContentType, string Filename)> ExportAsJsonAsync(
        string jobId, WaveformJobStatus jobStatus, string tempOutputDir)
    {
        var exportData = new
        {
            jobId,
            exportedAt = DateTime.UtcNow.ToString("O"),
            totalFiles = jobStatus.TotalFiles,
            successfulFiles = jobStatus.SuccessfulFiles,
            failedFiles = jobStatus.FailedFiles,
            waveforms = new List<object>()
        };

        var waveformsList = (List<object>)exportData.waveforms;

        // Load all waveform data
        foreach (var result in jobStatus.Results)
        {
            if (result.Status == "success")
            {
                var filenameWithoutExt = Path.GetFileNameWithoutExtension(result.Filename);
                var waveformFilePath = Path.Combine(tempOutputDir, $"{filenameWithoutExt}.json");

                if (File.Exists(waveformFilePath))
                {
                    var jsonContent = await File.ReadAllTextAsync(waveformFilePath);
                    var jsonDoc = JsonDocument.Parse(jsonContent);
                    var root = jsonDoc.RootElement;

                    var waveformValues = new List<double>();
                    if (root.TryGetProperty("waveform_data", out var waveformArray))
                    {
                        foreach (var value in waveformArray.EnumerateArray())
                        {
                            waveformValues.Add(Math.Round(value.GetDouble(), 3));
                        }
                    }

                    waveformsList.Add(new
                    {
                        filename = result.Filename,
                        sampleCount = result.SampleCount,
                        fileSizeMb = result.FileSizeMb,
                        status = result.Status,
                        waveformData = waveformValues
                    });
                }
            }
            else
            {
                // Include failed files with error info
                waveformsList.Add(new
                {
                    filename = result.Filename,
                    sampleCount = 0,
                    fileSizeMb = 0.0,
                    status = result.Status,
                    error = result.Error
                });
            }
        }

        var jsonString = JsonSerializer.Serialize(exportData, new JsonSerializerOptions
        {
            WriteIndented = true
        });

        var bytes = Encoding.UTF8.GetBytes(jsonString);
        return (bytes, "application/json", $"waveforms-{jobId}.json");
    }

    private async Task<(byte[] FileBytes, string ContentType, string Filename)> ExportAsCsvAsync(
        string jobId, WaveformJobStatus jobStatus, string tempOutputDir)
    {
        var csv = new StringBuilder();

        // Header row
        csv.Append("filename,status,sampleCount,fileSizeMb,error");
        for (int i = 0; i < 480; i++)
        {
            csv.Append($",waveform_{i}");
        }
        csv.AppendLine();

        // Data rows
        foreach (var result in jobStatus.Results)
        {
            csv.Append($"\"{result.Filename}\",{result.Status},{result.SampleCount ?? 0},{result.FileSizeMb ?? 0:F2}");

            if (result.Status == "error")
            {
                csv.Append($",\"{result.Error?.Replace("\"", "\"\"")}\"");
                // Empty waveform columns for errors
                for (int i = 0; i < 480; i++)
                {
                    csv.Append(",");
                }
            }
            else
            {
                csv.Append(","); // Empty error column

                // Load waveform data
                var filenameWithoutExt = Path.GetFileNameWithoutExtension(result.Filename);
                var waveformFilePath = Path.Combine(tempOutputDir, $"{filenameWithoutExt}.json");

                if (File.Exists(waveformFilePath))
                {
                    var jsonContent = await File.ReadAllTextAsync(waveformFilePath);
                    var jsonDoc = JsonDocument.Parse(jsonContent);
                    var root = jsonDoc.RootElement;

                    if (root.TryGetProperty("waveform_data", out var waveformArray))
                    {
                        var values = waveformArray.EnumerateArray()
                            .Select(v => Math.Round(v.GetDouble(), 3).ToString("F3"))
                            .ToList();

                        // Pad or truncate to 480 values
                        while (values.Count < 480) values.Add("0.000");
                        if (values.Count > 480) values = values.Take(480).ToList();

                        csv.Append(string.Join(",", values));
                    }
                }
            }

            csv.AppendLine();
        }

        var bytes = Encoding.UTF8.GetBytes(csv.ToString());
        return (bytes, "text/csv", $"waveforms-{jobId}.csv");
    }

    private async Task<(byte[] FileBytes, string ContentType, string Filename)> ExportAsZipAsync(
        string jobId, WaveformJobStatus jobStatus, string tempOutputDir)
    {
        using var memoryStream = new MemoryStream();
        using (var archive = new ZipArchive(memoryStream, ZipArchiveMode.Create, true))
        {
            // Add individual waveform JSON files
            foreach (var result in jobStatus.Results.Where(r => r.Status == "success"))
            {
                var filenameWithoutExt = Path.GetFileNameWithoutExtension(result.Filename);
                var waveformFilePath = Path.Combine(tempOutputDir, $"{filenameWithoutExt}.json");

                if (File.Exists(waveformFilePath))
                {
                    var entry = archive.CreateEntry($"{filenameWithoutExt}.json", CompressionLevel.Optimal);
                    using var entryStream = entry.Open();
                    using var fileStream = File.OpenRead(waveformFilePath);
                    await fileStream.CopyToAsync(entryStream);
                }
            }

            // Add manifest file
            var manifest = new
            {
                jobId,
                exportedAt = DateTime.UtcNow.ToString("O"),
                totalFiles = jobStatus.TotalFiles,
                successfulFiles = jobStatus.SuccessfulFiles,
                failedFiles = jobStatus.FailedFiles,
                files = jobStatus.Results.Select(r => new
                {
                    filename = r.Filename,
                    jsonFile = r.Status == "success" ? $"{Path.GetFileNameWithoutExtension(r.Filename)}.json" : null,
                    status = r.Status,
                    error = r.Error
                }).ToList()
            };

            var manifestEntry = archive.CreateEntry("manifest.json", CompressionLevel.Optimal);
            using var manifestStream = manifestEntry.Open();
            await JsonSerializer.SerializeAsync(manifestStream, manifest, new JsonSerializerOptions
            {
                WriteIndented = true
            });
        }

        memoryStream.Position = 0;
        var bytes = memoryStream.ToArray();
        return (bytes, "application/zip", $"waveforms-{jobId}.zip");
    }
}
