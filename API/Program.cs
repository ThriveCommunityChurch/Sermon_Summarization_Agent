using SermonSummarizationAPI.Services;
using SermonSummarizationAPI.Middleware;
using SermonSummarizationAPI.Hubs;
using Microsoft.AspNetCore.Http.Features;

var builder = WebApplication.CreateBuilder(args);

// Configure Kestrel to allow large file uploads
builder.WebHost.ConfigureKestrel(options =>
{
    options.Limits.MaxRequestBodySize = 5L * 1024 * 1024 * 1024; // 5 GB
});

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowReactApp", policy =>
    {
        policy.WithOrigins("http://localhost:5173", "http://localhost:5174", "http://localhost:3000")
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials(); // Required for SignalR
    });
});

// Register services
builder.Services.AddMemoryCache();
builder.Services.AddScoped<IPythonAgentService, PythonAgentService>();
builder.Services.AddScoped<ISermonProcessingService, SermonProcessingService>();
builder.Services.AddScoped<ITokenTrackingService, TokenTrackingService>();
builder.Services.AddScoped<IWaveformService, WaveformService>();

// Add SignalR
builder.Services.AddSignalR();

// Configure file upload limits
builder.Services.Configure<FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = 5L * 1024 * 1024 * 1024; // 5 GB
});

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}
else
{
    app.UseHttpsRedirection();
}

app.UseCors("AllowReactApp");
app.UseAuthorization();
app.MapControllers();

// Map SignalR hub
app.MapHub<WaveformProgressHub>("/hubs/waveform-progress");

app.Run();

