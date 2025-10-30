using Microsoft.AspNetCore.Mvc;
using SermonSummarizationAPI.Models;
using SermonSummarizationAPI.Services;

namespace SermonSummarizationAPI.Controllers;

/// <summary>
/// Controller for sermon processing endpoints
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class SermonsController : ControllerBase
{
    private readonly ISermonProcessingService _sermonProcessingService;
    private readonly IWaveformService _waveformService;
    private readonly ILogger<SermonsController> _logger;

    public SermonsController(
        ISermonProcessingService sermonProcessingService,
        IWaveformService waveformService,
        ILogger<SermonsController> logger)
    {
        _sermonProcessingService = sermonProcessingService;
        _waveformService = waveformService;
        _logger = logger;
    }

    /// <summary>
    /// Process a sermon file (upload and process)
    /// </summary>
    /// <returns>Processing result with summary, tags, and token usage</returns>
    [Produces("application/json")]
    [HttpPost("process")]
    [ProducesResponseType(200)]
    [ProducesResponseType(400)]
    public async Task<ActionResult<SermonProcessResponse>> ProcessSermon()
    {
        var response = await _sermonProcessingService.ProcessUploadedFileAsync(Request);

        if (response.Status == "failed")
        {
            return StatusCode(400, response);
        }

        return response;
    }

    /// <summary>
    /// Get processing status by ID
    /// </summary>
    /// <param name="id">The processing request ID</param>
    /// <returns>Processing status and results</returns>
    [HttpGet("{id}/status")]
    [ProducesResponseType(typeof(SermonProcessResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<SermonProcessResponse> GetStatus(string id)
    {
        _logger.LogInformation("Retrieving status for processing ID: {Id}", id);

        var result = _sermonProcessingService.GetProcessingStatusAsync(id);

        if (result == null)
        {
            return NotFound();
        }

        return Ok(result);
    }

    /// <summary>
    /// Health check endpoint
    /// </summary>
    [HttpGet("health")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public ActionResult<object> Health()
    {
        return Ok(new { status = "healthy", timestamp = DateTime.UtcNow });
    }

    /// <summary>
    /// Start bulk waveform generation for a directory of audio files
    /// </summary>
    /// <param name="request">Request containing directory path</param>
    /// <returns>Job response with job ID and initial status</returns>
    [HttpPost("bulk-waveform")]
    [ProducesResponseType(typeof(BulkWaveformJobResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<BulkWaveformJobResponse>> StartBulkWaveform([FromBody] BulkWaveformRequest request)
    {
        _logger.LogInformation("Starting bulk waveform generation for directory: {Directory}", request.DirectoryPath);

        var response = await _waveformService.StartBulkWaveformJobAsync(request.DirectoryPath);

        if (response.Status == "failed")
        {
            return BadRequest(response);
        }

        return Ok(response);
    }

    /// <summary>
    /// Get the status of a bulk waveform generation job
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <returns>Current job status with progress information</returns>
    [HttpGet("bulk-waveform/{jobId}/status")]
    [ProducesResponseType(typeof(WaveformJobStatus), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<WaveformJobStatus> GetBulkWaveformStatus(string jobId)
    {
        _logger.LogInformation("Retrieving status for bulk waveform job: {JobId}", jobId);

        var status = _waveformService.GetJobStatus(jobId);

        if (status == null)
        {
            return NotFound(new { error = "Job not found" });
        }

        return Ok(status);
    }

    /// <summary>
    /// Get waveform data for a specific file in a job
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <param name="filename">Name of the audio file</param>
    /// <returns>Waveform data with amplitude values</returns>
    [HttpGet("bulk-waveform/{jobId}/waveform/{filename}")]
    [ProducesResponseType(typeof(WaveformData), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<WaveformData>> GetWaveformData(string jobId, string filename)
    {
        _logger.LogInformation("Retrieving waveform data for job {JobId}, file {Filename}", jobId, filename);

        var data = await _waveformService.GetWaveformDataAsync(jobId, filename);

        if (data == null)
        {
            return NotFound(new { error = "Waveform data not found" });
        }

        return Ok(data);
    }

    /// <summary>
    /// Export waveform data for a completed job in the specified format
    /// </summary>
    /// <param name="jobId">Unique job identifier</param>
    /// <param name="format">Export format (json, csv, zip)</param>
    /// <returns>File download with waveform data</returns>
    [HttpGet("bulk-waveform/{jobId}/export")]
    [ProducesResponseType(typeof(FileContentResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> ExportWaveformData(
        string jobId,
        [FromQuery] string format = "json")
    {
        _logger.LogInformation("Export requested for job {JobId} in format {Format}", jobId, format);

        // Validate format
        var validFormats = new[] { "json", "csv", "zip" };
        if (!validFormats.Contains(format.ToLower()))
        {
            return BadRequest(new { error = $"Invalid format. Supported formats: {string.Join(", ", validFormats)}" });
        }

        // Check if job exists
        var jobStatus = _waveformService.GetJobStatus(jobId);
        if (jobStatus == null)
        {
            return NotFound(new { error = "Job not found or data no longer available" });
        }

        // Check if job is completed
        if (jobStatus.Status != "completed")
        {
            return Conflict(new { error = "Export only available for completed jobs. Current status: " + jobStatus.Status });
        }

        // Export data
        var result = await _waveformService.ExportWaveformDataAsync(jobId, format.ToLower());

        if (result == null)
        {
            return NotFound(new { error = "Failed to export data. Job data may no longer be available." });
        }

        return File(result.Value.FileBytes, result.Value.ContentType, result.Value.Filename);
    }
}

