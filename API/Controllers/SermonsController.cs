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
    private readonly ILogger<SermonsController> _logger;

    public SermonsController(ISermonProcessingService sermonProcessingService, ILogger<SermonsController> logger)
    {
        _sermonProcessingService = sermonProcessingService;
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
}

