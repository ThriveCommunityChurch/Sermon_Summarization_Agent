# Sermon Summarization Agent

A LangGraph-based AI agent that transcribes and summarizes sermon video recordings from MP4 or MP3 files.

## Features

- **Transcription**: Converts audio from MP4/MP3 files to text using OpenAI Whisper
- **GPU Acceleration**: Automatically detects and uses NVIDIA GPU (CUDA) for much faster transcription
- **Summarization**: Generates end-user-friendly single-paragraph summaries using GPT-4o-mini
- **Semantic Tagging**: Automatically applies relevant topical tags to summaries for better organization and discovery
- **Batch Processing**: Process entire directories of sermon files at once
- **LangGraph Architecture**: Built with a graph-based workflow for clear separation of concerns
- **CLI Interface**: Easy-to-use command-line interface

## Requirements

- Python 3.8+
- FFmpeg (must be installed separately)
- OpenAI API key

## Installation

1. **Clone the repository**:
   ```bash
   cd C:\Users\wyatt\Documents\GitHub\Thrive\Sermon_Summarization_Agent
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   > **Note**: This installs CPU-only PyTorch. For GPU acceleration (4x faster), see the [GPU Acceleration](#gpu-acceleration-) section below.

4. **Install FFmpeg** (if not already installed):
   - **Windows**: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `apt install ffmpeg` or `yum install ffmpeg`

5. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

## Usage

### Single File Mode

Transcribe and summarize a single sermon file:

```bash
python agent.py --file path/to/sermon.mp4
```

### Batch Processing Mode

Process all audio files in a directory at once:

```bash
python agent.py --batch-dir "G:\Thrive\Sermon Videos\Audio Files"
```

This will:
- Find all audio files (MP3, MP4, WAV, M4A, MOV) in the directory
- Process each file sequentially
- Create organized subdirectories for each file's outputs
- Generate a consolidated `batch_summaries.json` with all results
- Display progress as files are processed
- Continue processing even if individual files fail

### Auto-detect Latest File

If no file is specified, the agent will auto-detect the latest media file in the configured directory:

```bash
python agent.py
```

### Options

- `--file`, `-f`: Path to a single sermon audio/video file (MP4, MP3, WAV, M4A, MOV)
- `--batch-dir`, `-b`: Path to directory containing multiple sermon files for batch processing

> **Note**: `--file` and `--batch-dir` are mutually exclusive. Use one or the other.

## Output

### Single File Mode

The agent generates the following files in the current directory:

- `transcription.txt`: Full transcription text
- `transcription_segments.json`: Transcription with timestamps
- `summary.txt`: Single-paragraph summary
- `summary.json`: Summary with metadata and semantic tags

### Batch Processing Mode

The agent generates:

1. **Individual file outputs** in organized subdirectories:
   ```
   batch_outputs/
   ├── 2025-10-05-Recording/
   │   ├── transcription.txt
   │   ├── transcription_segments.json
   │   ├── summary.txt
   │   └── summary.json
   ├── 2025-10-12-Recording/
   │   ├── transcription.txt
   │   ├── transcription_segments.json
   │   ├── summary.txt
   │   └── summary.json
   └── ...
   ```

2. **Consolidated JSON output** (`batch_summaries.json`):
   ```json
   {
     "2025-10-05-Recording": {
       "filename": "2025-10-05-Recording.mp3",
       "summary": "This sermon explores the transformative power of faith...",
       "transcription_path": "C:\\...\\batch_outputs\\2025-10-05-Recording\\transcription.txt",
       "summary_path": "C:\\...\\batch_outputs\\2025-10-05-Recording\\summary.txt",
       "word_count": 158,
       "date_processed": "2025-10-09T10:30:00Z",
       "status": "success"
     },
     "2025-10-12-Recording": {
       "filename": "2025-10-12-Recording.mp3",
       "summary": "The message focuses on the importance of community...",
       "transcription_path": "C:\\...\\batch_outputs\\2025-10-12-Recording\\transcription.txt",
       "summary_path": "C:\\...\\batch_outputs\\2025-10-12-Recording\\summary.txt",
       "word_count": 142,
       "date_processed": "2025-10-09T10:35:00Z",
       "status": "success"
     }
   }
   ```

   If a file fails to process, the entry will include error information:
   ```json
   {
     "problematic-file": {
       "filename": "problematic-file.mp3",
       "summary": null,
       "transcription_path": null,
       "summary_path": null,
       "word_count": 0,
       "date_processed": "2025-10-09T10:40:00Z",
       "status": "error",
       "error": "File not found or corrupted"
     }
   }
   ```

## Architecture

The agent uses LangGraph with three main nodes:

1. **Transcribe Node**: Converts audio to text using OpenAI Whisper
   - Automatically detects and uses GPU (CUDA) if available
   - Extracts audio from video files using FFmpeg
   - Generates timestamped segments
2. **Summarize Node**: Generates a summary using GPT-4o-mini
   - Creates end-user-friendly single-paragraph summaries
   - Includes metadata (word count, processing date, etc.)
3. **Tagging Node**: Applies semantic tags to summaries
   - Analyzes summary content using GPT-4o-mini
   - Selects up to 5 relevant tags from a predefined list (config/tags_config.py)
   - Tags are cached in memory for efficient batch processing
   - Updates summary.json with a tags array

## Semantic Tagging

The agent automatically applies relevant topical tags to each sermon summary for better organization and discovery.

### How It Works

1. **Tag Source**: Tags are defined in `config/tags_config.py`, which contains 102+ predefined sermon topics
2. **Hybrid Analysis**: GPT-4o-mini analyzes BOTH the summary (main themes) and transcript excerpt (comprehensive context) to determine relevant themes
3. **Selection**: The AI selects up to 5 most relevant tags from the available list
4. **Storage**: Tags are added to `summary.json` as a `tags` array field

### Available Tag Categories

Tags cover a wide range of sermon topics including:
- **Relationships & Family**: Marriage, Family, Friendship, Singleness
- **Theological Foundations**: Salvation, Faith, Trinity, Church, Holy Spirit
- **Spiritual Disciplines**: Prayer, Worship, Fasting, Bible Study
- **Personal Growth**: Hope, Love, Joy, Peace, Courage, Wisdom
- **Life Challenges**: Suffering, Anxiety, Doubt, Addiction, Grief
- **Biblical Studies**: Parables, Sermon on the Mount, specific book studies
- **Seasonal**: Advent, Christmas, Easter, Lent
- **And many more...**

### Example Output

```json
{
  "summary": "This sermon explores the transformative power of faith...",
  "word_count": 120,
  "character_count": 750,
  "model": "gpt-4o-mini",
  "transcription_length": 28500,
  "tags": ["Faith", "Salvation", "Hope", "Discipleship"]
}
```

### Extending Tags

To add new tags:
1. Edit `config/tags_config.py`
2. Add your new tag to the appropriate category list (or create a new category)
3. The tag will be automatically included in `ALL_TAGS` and available on the next run

### Performance

- Tags are loaded once and cached in memory during batch processing
- Hybrid analysis uses ~15000 characters of transcript + full summary
- Each sermon typically takes 3-4 seconds for tag classification
- Cost: ~$0.0008 per sermon (very affordable with GPT-4o-mini)

## Configuration

Environment variables (in `.env`):

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `WHISPER_MODEL`: Whisper model to use (default: `small.en`)
  - Options: `tiny`, `tiny.en`, `base`, `base.en`, `small`, `small.en`, `medium`, `medium.en`, `large`
  - Larger models are more accurate but slower (GPU highly recommended for medium/large)
- `WHISPER_FORCE_CPU`: Force CPU mode even if GPU is available (default: `false`)
- `SERMON_AUDIO_DIR`: Directory to search for sermon files (optional)

### GPU Acceleration ⚡

The agent automatically detects and uses NVIDIA GPUs (CUDA) for Whisper transcription, providing **significant speed improvements**.

**Performance Comparison:**
- **CPU**: ~15 minutes for a typical sermon
- **GPU (RTX 4080 SUPER)**: ~4 minutes for the same sermon
- **Speedup**: ~4x faster with GPU acceleration

**GPU Detection:**
- If you have an NVIDIA GPU with CUDA support (RTX series, GTX series, etc.), it will be automatically detected and used
- The agent will display GPU information at startup:
  ```
  🚀 GPU detected: NVIDIA GeForce RTX 4080 SUPER
     Number of GPUs available: 1
     Using device: cuda with fp16 precision
     This will be MUCH faster than CPU!
  ```
- fp16 precision is automatically enabled on GPU for faster inference

**Installing CUDA-Enabled PyTorch:**

By default, `requirements.txt` installs CPU-only PyTorch. To enable GPU acceleration:

1. **Uninstall CPU-only PyTorch**:
   ```bash
   pip uninstall torch torchvision torchaudio
   ```

2. **Install CUDA-enabled PyTorch** (for CUDA 11.8):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

   For other CUDA versions, visit: https://pytorch.org/get-started/locally/

3. **Verify GPU is detected**:
   ```bash
   python test_gpu.py
   ```

   You should see:
   ```
   ✓ CUDA available: True
   ✓ GPU 0: NVIDIA GeForce RTX [Your GPU Model]
   🚀 GPU is ready to use! Whisper will run MUCH faster.
   ```

**To force CPU mode:**
Set `WHISPER_FORCE_CPU=true` in your `.env` file (useful for testing or if you encounter GPU memory issues)

## Batch Processing Performance

Batch processing leverages GPU acceleration for optimal performance:

- **With GPU (RTX 4080 SUPER)**:
  - ~4 minutes per sermon (30-45 minute audio)
  - Can process 15 sermons per hour
  - Recommended for large batches

- **With CPU only**:
  - ~15 minutes per sermon
  - Can process 4 sermons per hour
  - Still functional but significantly slower

**Example batch processing time:**
- 10 sermons with GPU: ~40 minutes
- 10 sermons with CPU: ~2.5 hours

## Troubleshooting

### Batch Processing Issues

**Problem**: Files are being skipped or not found
- **Solution**: Ensure all files have supported extensions (.mp3, .mp4, .wav, .m4a, .mov)
- Check that the directory path is correct and accessible

**Problem**: Some files fail to process
- **Solution**: Check the `batch_summaries.json` for error details
- Individual file failures won't stop the batch - other files will continue processing
- Common issues: corrupted files, unsupported codecs, insufficient disk space

**Problem**: GPU out of memory during batch processing
- **Solution**:
  - Use a smaller Whisper model (e.g., `small.en` instead of `medium` or `large`)
  - Set `WHISPER_FORCE_CPU=true` to use CPU mode
  - Process files individually instead of in batch mode

## License

See LICENSE file for details.