using SermonSummarizationAPI.Models;

namespace SermonSummarizationAPI.Services;

/// <summary>
/// Service for orchestrating sermon processing
/// </summary>
public class SermonProcessingService : ISermonProcessingService
{
    private readonly IPythonAgentService _pythonAgentService;
    private readonly ILogger<SermonProcessingService> _logger;
    private readonly Dictionary<string, SermonProcessResponse> _processingCache = new();
    private readonly object _lockObject = new();

    public SermonProcessingService(IPythonAgentService pythonAgentService, ILogger<SermonProcessingService> logger)
    {
        _pythonAgentService = pythonAgentService;
        _logger = logger;
    }

    public async Task<SermonProcessResponse> ProcessUploadedFileAsync(HttpRequest request)
    {
        try
        {
            // Validations - following the pattern from ThriveChurchOfficialAPI
            if (request == null || request.Body == null ||
                request.ContentLength == null || request.ContentLength == 0 ||
                request.Form.Files == null || !request.Form.Files.Any())
            {
                return new SermonProcessResponse
                {
                    Status = "failed",
                    Error = "No file provided"
                };
            }

            var file = request.Form.Files[0];
            var fileName = file.FileName;

            // Validate file extension
            var allowedExtensions = new[] { ".mp3", ".mp4", ".wav", ".m4a", ".mov" };
            var fileExtension = Path.GetExtension(fileName).ToLower();

            if (!allowedExtensions.Contains(fileExtension))
            {
                return new SermonProcessResponse
                {
                    Status = "failed",
                    Error = $"File type not supported. Allowed types: {string.Join(", ", allowedExtensions)}"
                };
            }

            // Save the uploaded file to a temporary location
            var tempFilePath = Path.Combine(Path.GetTempPath(), Guid.NewGuid() + fileExtension);
            using (var stream = new FileStream(tempFilePath, FileMode.Create))
            {
                await file.CopyToAsync(stream);
            }

            _logger.LogInformation("File uploaded successfully: {FileName}", fileName);

            // Process the file through the Python agent
            var result = await _pythonAgentService.ProcessSermonAsync(tempFilePath);

            // Cache the result
            if (result.Id != null)
            {
                lock (_lockObject)
                {
                    _processingCache[result.Id] = result;
                }
            }

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing uploaded file");
            return new SermonProcessResponse
            {
                Status = "failed",
                Error = ex.Message
            };
        }
        finally
        {
            // Clean up the temporary file if it exists
            try
            {
                var tempFiles = Directory.GetFiles(Path.GetTempPath(), "*.mp3");
                foreach (var tempFile in tempFiles)
                {
                    if (File.Exists(tempFile))
                    {
                        File.Delete(tempFile);
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Failed to clean up temporary files: {Error}", ex.Message);
            }
        }
    }

    public SermonProcessResponse? GetProcessingStatusAsync(string id)
    {
        lock (_lockObject)
        {
            if (_processingCache.TryGetValue(id, out var result))
            {
                return result;
            }
        }

        return null;
    }
}

