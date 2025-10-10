# Bulk Sermon Message Updater Tool

This tool is designed to update sermon messages in bulk within the Thrive Church Official App using the directory containing all of the AI-generated summaries and semantic tags from the Sermon Summarization Agent in this repository. Since this is likely to be a one-time operation, this tool is not intended to be built into the agent itself. However, it is intended to be a standalone tool that can be used to update the sermon messages in the future if needed.

## Overview

This tool reads AI-generated sermon summaries and tags from the `batch_outputs/` directory and applies them to sermon messages via the church's API. It handles date matching, mislabeled audio files, and provides robust error handling with resume capability.

## Features

- ✅ **Dual Matching Strategy**: Matches summaries to messages by date, with fallback to audio filename for mislabeled recordings
- ✅ **Flexible Date Parsing**: Handles various date formats (`YYYY-MM-DD`, `YYYY-M-D`, etc.)
- ✅ **API Caching**: Cache sermon data locally to speed up testing iterations
- ✅ **Dry-Run Mode**: Preview changes without making actual API calls
- ✅ **Resume Capability**: Resume from previous run if interrupted
- ✅ **Single-Folder Testing**: Test with individual sermons before batch processing
- ✅ **Progress Tracking**: Saves progress after each update
- ✅ **Comprehensive Logging**: Detailed logs for debugging and auditing

## Prerequisites

### 1. Python Dependencies

```bash
cd Update_Messages
pip install -r requirements.txt
```

**Required packages:**
- `requests>=2.31.0` - HTTP client for API calls
- `urllib3>=2.0.0` - HTTP library
- `python-dotenv>=1.0.0` - Environment variable management

### 2. Environment Configuration

Create a `.env` file in the `Update_Messages/` directory:

```bash
cp .env.example .env
```

Edit `.env` and set your API URL:

```env
API_BASE_URL=http://your-api-server.com:8080/api/sermons
```

**Note:** The `.env` file should never be committed to version control.

### 3. Input Data Structure

The script expects AI-generated summaries in the following structure:

```
batch_outputs/
├── 2020-01-05-Recording/
│   └── summary.json
├── 2020-01-12-Recording/
│   └── summary.json
└── ...
```

Each `summary.json` should contain:

```json
{
  "summary": "AI-generated summary text...",
  "tags": ["Faith", "Grace", "Community"],
  "word_count": 113,
  "character_count": 710,
  "model": "gpt-4o-mini",
  "transcription_length": 25054
}
```

## Usage

### Basic Commands

#### 1. Dry-Run (Preview Changes)

Preview what would be updated without making actual API calls:

```bash
python update_sermon_summaries.py --dry-run
```

#### 2. Test with Single Sermon

Test with one sermon before processing all:

```bash
python update_sermon_summaries.py --folder "2020-01-05-Recording" --dry-run
```

#### 3. Use Cached API Data

Skip the ~52-second API fetch by using cached data (faster for testing):

```bash
python update_sermon_summaries.py --dry-run --use-cached-api
```

#### 4. Live Update (Production)

Actually update the messages via API:

```bash
python update_sermon_summaries.py
```

#### 5. Resume from Previous Run

If interrupted, resume from where you left off:

```bash
python update_sermon_summaries.py --resume
```

#### 6. Override API URL

Use a different API endpoint (e.g., localhost for testing):

```bash
python update_sermon_summaries.py --api-url http://localhost:8080/api/sermons --dry-run
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without making API calls |
| `--resume` | Resume from previous run (skip already processed messages) |
| `--folder FOLDER` | Process only a single folder (e.g., `2020-01-05-Recording`) |
| `--use-cached-api` | Use cached API data instead of fetching from server |
| `--api-url URL` | Override API base URL from .env file |

## How It Works

### Workflow

1. **Fetch Sermon Data**: Retrieves all sermon series and messages from the API (or loads from cache)
2. **Parse Summaries**: Reads all `summary.json` files from `batch_outputs/`
3. **Match Summaries to Messages**: Uses dual matching strategy:
   - **Primary**: Match by date (YYYY-MM-DD)
   - **Fallback**: Match by audio filename (handles mislabeled dates)
4. **Generate Modified Messages**: Creates updated message objects with summaries and tags
5. **Save Locally**: Saves modified messages to `modified_messages/` directory
6. **Update via API**: Sends updates to the API (with rate limiting)
7. **Generate Report**: Creates a summary report of the operation

### Matching Strategy

The tool uses a **dual matching strategy** to handle real-world data issues:

#### Primary: Date Matching
- Extracts date from folder name (e.g., `2020-01-05-Recording` → `2020-01-05`)
- Normalizes various date formats (`YYYY-M-D`, `YYYY-MM-DD`)
- Matches against message date in the database

#### Fallback: Audio Filename Matching
- Some audio files were mislabeled with incorrect dates (e.g., Monday instead of Sunday)
- Falls back to matching the folder name against the AudioUrl filename
- Example:
  - Folder: `2023-10-16-Recording` (Monday - mislabeled)
  - Message Date: `2023-10-15` (Sunday - correct)
  - AudioUrl: `https://domain.com/2023/2023-10-16-Recording.mp3`
  - **Match!** Audio filename matches folder name

### Rate Limiting

- **Delay between requests**: 0.5 seconds (configurable in script)
- **Retry logic**: 3 attempts with exponential backoff
- **Timeout**: 30 seconds per request

## Output Files

### Generated Directories

```
Update_Messages/
├── api_content/                    # Cached API data
│   ├── all_sermons.json           # All 505 messages from 92 series
│   └── all_series_summaries.json  # Series summaries list
├── modified_messages/              # Modified message JSON files
│   ├── 6314e0a38746e349ce5ab92b.json
│   ├── 6314e0a38746e349ce5ab92c.json
│   └── ...
├── update_progress.json            # Progress tracking (for --resume)
├── update_sermon_summaries.log     # Detailed execution log
└── update_report_YYYYMMDD_HHMMSS.txt  # Summary report
```

### Modified Message Format

Each file in `modified_messages/` contains the complete message with updated fields:

```json
{
  "Message": {
    "MessageId": "6314e0a38746e349ce5ab92b",
    "Title": "Our Plans and God's Plans",
    "Date": "2020-01-05T00:00:00Z",
    "Speaker": "Pastor Name",
    "AudioUrl": "https://domain.com/2023/2023-10-16-Recording.mp3",
    "Summary": "AI-generated summary...",
    "Tags": ["Love", "Discipleship", "Community"],
    ...
  }
}
```

**Important:** All original fields are preserved. Only `Summary` and `Tags` are updated.

## Testing Observations

### Performance

- **Without cache**: ~52 seconds to fetch 505 messages from 92 series
- **With cache**: ~0.25 seconds to load from disk
- **Processing rate**: ~708 messages per second (with cache)
- **API update rate**: ~2 requests per second (0.5s delay)

### Matching Results (Test Run)

- **Total summaries**: 180 folders in `batch_outputs/`
- **Successful matches**: 177 (98.3% match rate)
- **Unmatched summaries**: 3
  - `2020-04-12` - Easter Sunday (no recording)
  - `2022-07-31` - Summer break
  - `2022-11-27` - Thanksgiving weekend
- **Messages without summaries**: 326 (from 2015-2019, before batch processing)

### Date Mismatch Examples

The fallback matching successfully handled mislabeled audio files:

```
✓ Matched by audio filename: 2023-10-16-Recording - Covered With Joy 
  (date mismatch: folder=2023-10-16, message=2023-10-15)
```

## Safety Features

### Data Preservation

- ✅ **Never modifies source files**: Original summaries in `batch_outputs/` are read-only
- ✅ **Never modifies cache**: API cache files are read-only
- ✅ **Preserves all message fields**: Only updates `Summary` and `Tags`
- ✅ **Removes internal tracking fields**: Strips `_SeriesId` and `_SeriesName` before API update

### Error Handling

- ✅ **Progress tracking**: Saves progress after each update
- ✅ **Resume capability**: Can resume from interruption
- ✅ **Retry logic**: Automatically retries failed requests
- ✅ **Comprehensive logging**: All operations logged for debugging
- ✅ **Dry-run mode**: Test without making changes

## Troubleshooting

### API URL Not Found

```
ERROR: API_BASE_URL not found!
```

**Solution**: Create `.env` file with `API_BASE_URL` or use `--api-url` flag.

### Cache Files Not Found

```
ERROR: Cache files not found
```

**Solution**: Run without `--use-cached-api` first to fetch and cache data.

### No Matches Found

Check the log file for details:
- Verify folder names follow `YYYY-MM-DD-Recording` format
- Check that `summary.json` exists in each folder
- Review date matching logic in logs

### API Connection Issues

- Verify API URL is correct
- Check network connectivity
- Review API server logs
- Ensure API is running and accessible

## Best Practices

### Before Running in Production

1. ✅ **Test with dry-run**: Always preview changes first
2. ✅ **Test single folder**: Verify one message before batch processing
3. ✅ **Review modified files**: Inspect generated JSON files in `modified_messages/`
4. ✅ **Check logs**: Review `update_sermon_summaries.log` for issues
5. ✅ **Backup database**: Ensure API database is backed up

### During Production Run

1. ✅ **Monitor logs**: Watch for errors or warnings
2. ✅ **Check progress**: Progress is saved after each update
3. ✅ **Don't interrupt**: Let it complete or use Ctrl+C gracefully
4. ✅ **Use resume**: If interrupted, use `--resume` to continue

### After Production Run

1. ✅ **Review report**: Check `update_report_*.txt` for summary
2. ✅ **Verify in app**: Spot-check updated messages in the app
3. ✅ **Archive logs**: Save logs for future reference
4. ✅ **Clean up**: Optionally delete `modified_messages/` after successful run

## File Structure

```
Update_Messages/
├── .env                           # API configuration (not in git)
├── .env.example                   # Example configuration
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── update_sermon_summaries.py     # Main script
├── api_content/                   # Cached API data (generated)
├── modified_messages/             # Modified message files (generated)
├── update_progress.json           # Progress tracking (generated)
├── update_sermon_summaries.log    # Execution log (generated)
└── update_report_*.txt            # Summary reports (generated)
```

## Contributing

When making changes to this tool:

1. Test with `--dry-run` first
2. Test with single folder before batch
3. Update this README if adding new features
4. Never commit `.env` file or API credentials
5. Document any new command-line options

## License

Internal tool for Thrive Community Church © 2025.

