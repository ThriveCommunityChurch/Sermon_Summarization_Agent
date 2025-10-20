import os
import json
import subprocess
import whisper
import datetime
from pathlib import Path
from langchain_core.tools import tool

from classes.agent_state import AgentState

AUDIO_DIR = Path(os.environ.get("SERMON_AUDIO_DIR", r"C:\\Users\\Videos"))
DEFAULT_MODEL = "small.en"

# Global cache for loaded Whisper models
# Key: (model_name, device) tuple
# Value: loaded whisper model
_MODEL_CACHE = {}


def _find_latest_media(path: Path):
    """Find the latest media file in the given directory."""
    exts = (".mp3", ".mp4", ".wav", ".m4a", ".mov")
    if not path.exists():
        return None
    files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _validate_media_file(file_path: str) -> Path:
    """Validate that the provided file exists and is a supported media format."""
    supported_exts = (".mp3", ".mp4", ".wav", ".m4a", ".mov")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: '{file_path}'")

    if not path.is_file():
        raise ValueError(f"Path is not a file: '{file_path}'")

    if path.suffix.lower() not in supported_exts:
        raise ValueError(f"Unsupported file format: '{path.suffix}'. Supported formats: {supported_exts}")

    return path


def _extract_audio_if_needed(file_path: Path) -> Path:
    """Extract audio from video file if needed, return path to audio file."""
    video_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    audio_exts = (".mp3", ".wav", ".m4a", ".flac", ".ogg")

    if file_path.suffix.lower() in audio_exts:
        print(f"File is already audio format: {file_path.suffix}")
        return file_path

    if file_path.suffix.lower() in video_exts:
        print(f"Video file detected ({file_path.suffix}), extracting audio...")
        audio_path = file_path.with_suffix('.wav')

        if audio_path.exists() and audio_path.stat().st_mtime > file_path.stat().st_mtime:
            print(f"Audio file already exists and is up-to-date: {audio_path}")
            return audio_path

        try:
            cmd = [
                'ffmpeg',
                '-i', str(file_path),
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '48000',
                '-ac', '1',
                '-y',
                str(audio_path)
            ]

            print(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if audio_path.exists():
                print(f"Audio extracted successfully: {audio_path}")
                print(f"Audio file size: {audio_path.stat().st_size / (1024*1024):.1f} MB")
                return audio_path
            else:
                raise RuntimeError("FFmpeg completed but audio file was not created")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"FFmpeg failed to extract audio. Error: {e.stderr}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Make sure FFmpeg is installed and in your PATH."
            ) from e
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg is required to extract audio from video files but was not found. "
                "Please install FFmpeg and add it to your system PATH. "
                "Download from: https://ffmpeg.org/download.html"
            )

    print(f"Unknown file type ({file_path.suffix}), passing to Whisper directly...")
    return file_path


def _format_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


@tool
def transcribe_audio(state: dict | None = None):
    """
    CPU-only Whisper transcription with segment timestamps.

    Looks for state['filePath'] if provided; otherwise uses the latest media file in the given folder.

    Writes:
    - transcription.txt (full text)
    - transcription_segments.json (segments with start/end/text)

    Returns a short JSON string summary with keys: {"file", "model", "text_path", "segments_path"}.
    """
    file_path = None

    cli_file_path = os.environ.get("SERMON_FILE_PATH")
    if cli_file_path:
        file_path = str(_validate_media_file(cli_file_path))
        print(f"Using CLI-provided file: {file_path}")
    else:
        try:
            state_file_path = state.get("filePath")
            if state_file_path:
                file_path = str(_validate_media_file(state_file_path))
                print(f"Using AgentState file: {file_path}")
        except Exception:
            pass

        if not file_path:
            latest = _find_latest_media(AUDIO_DIR)
            if latest is None:
                raise FileNotFoundError(
                    f"No media files found in {AUDIO_DIR}. "
                    f"Provide a file path via --file argument or set AgentState.filePath."
                )
            file_path = str(latest)
            print(f"Auto-detected latest file: {file_path}")

    model_name = os.environ.get("WHISPER_MODEL", DEFAULT_MODEL)
    output_txt = Path("transcription.txt")
    output_json = Path("transcription_segments.json")

    audio_file_path = _extract_audio_if_needed(Path(file_path))
    file_path = str(audio_file_path)

    # Detect and configure device (GPU if available, otherwise CPU)
    # Allow forcing CPU mode via environment variable
    force_cpu = os.environ.get("WHISPER_FORCE_CPU", "false").lower() == "true"
    device = "cpu"
    use_fp16 = False

    try:
        import torch

        # Check if CUDA (NVIDIA GPU) is available and not forcing CPU
        if torch.cuda.is_available() and not force_cpu:
            device = "cuda"
            use_fp16 = True  # Enable fp16 for faster GPU inference
            gpu_name = torch.cuda.get_device_name(0)
            gpu_count = torch.cuda.device_count()
            print(f"GPU detected: {gpu_name}")
            print(f"   Number of GPUs available: {gpu_count}")
            print(f"   Using device: {device} with fp16 precision")
            print(f"   This will be MUCH faster than CPU!")
        else:
            # CPU fallback - optimize for multi-core
            if force_cpu:
                print("CPU mode forced via WHISPER_FORCE_CPU environment variable")
            torch.set_num_threads(max(1, os.cpu_count() or 1))
            os.environ.setdefault("OMP_NUM_THREADS", str(max(1, os.cpu_count() or 1)))
            os.environ.setdefault("MKL_NUM_THREADS", str(max(1, os.cpu_count() or 1)))
            print(f"No GPU detected. Using CPU with {os.cpu_count()} threads")
            print("   Note: GPU acceleration can significantly speed up transcription.")
            print("   To use GPU, ensure you have CUDA-enabled PyTorch installed.")
    except Exception as e:
        print(f"Error detecting device: {e}")
        print("   Falling back to CPU")
        device = "cpu"

    # Load Whisper model (with caching for batch processing)
    cache_key = (model_name, device)

    if cache_key in _MODEL_CACHE:
        print(f"Reusing cached Whisper model '{model_name}' on {device}...")
        model = _MODEL_CACHE[cache_key]
    else:
        print(f"Loading Whisper model '{model_name}' on {device}...")
        model = whisper.load_model(model_name, device=device)
        _MODEL_CACHE[cache_key] = model
        print(f"Model loaded and cached for future use")

    # Measure transcription time
    start = datetime.datetime.now()

    # Transcribe audio
    print(f"Starting Whisper transcription of: {file_path}")
    result = model.transcribe(file_path, fp16=use_fp16, language="English")

    output_txt.write_text(result.get("text", "").strip(), encoding="utf-8")

    segments_out = []
    for seg in result.get("segments", []) or []:
        segments_out.append(
            {
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "start_str": _format_ts(float(seg.get("start", 0.0))),
                "end_str": _format_ts(float(seg.get("end", 0.0))),
                "text": (seg.get("text") or "").strip(),
            }
        )
    output_json.write_text(json.dumps({"file": file_path, "segments": segments_out}, ensure_ascii=False, indent=2), encoding="utf-8")

    end = datetime.datetime.now()
    delta = end - start
    minutes, seconds = divmod(delta.seconds, 60)
    print(f"Transcription completed in {int(minutes)}m {int(seconds)}s")

    summary = {
        "file": file_path,
        "model": model_name,
        "text_path": str(output_txt.resolve()),
        "segments_path": str(output_json.resolve()),
    }

    return json.dumps(summary)