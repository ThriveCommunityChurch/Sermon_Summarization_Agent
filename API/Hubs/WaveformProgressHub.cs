using Microsoft.AspNetCore.SignalR;

namespace SermonSummarizationAPI.Hubs;

/// <summary>
/// SignalR hub for broadcasting bulk waveform generation progress updates
/// </summary>
public class WaveformProgressHub : Hub
{
    private readonly ILogger<WaveformProgressHub> _logger;

    public WaveformProgressHub(ILogger<WaveformProgressHub> logger)
    {
        _logger = logger;
    }

    public override async Task OnConnectedAsync()
    {
        _logger.LogInformation("Client connected: {ConnectionId}", Context.ConnectionId);
        await base.OnConnectedAsync();
    }

    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        if (exception != null)
        {
            _logger.LogWarning(exception, "Client disconnected with error: {ConnectionId}", Context.ConnectionId);
        }
        else
        {
            _logger.LogInformation("Client disconnected: {ConnectionId}", Context.ConnectionId);
        }
        await base.OnDisconnectedAsync(exception);
    }

    /// <summary>
    /// Client subscribes to updates for a specific job
    /// </summary>
    /// <param name="jobId">The job identifier to subscribe to</param>
    public async Task SubscribeToJob(string jobId)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, $"job-{jobId}");
        _logger.LogInformation("Client {ConnectionId} subscribed to job {JobId}", 
            Context.ConnectionId, jobId);
    }

    /// <summary>
    /// Client unsubscribes from job updates
    /// </summary>
    /// <param name="jobId">The job identifier to unsubscribe from</param>
    public async Task UnsubscribeFromJob(string jobId)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"job-{jobId}");
        _logger.LogInformation("Client {ConnectionId} unsubscribed from job {JobId}", 
            Context.ConnectionId, jobId);
    }
}

