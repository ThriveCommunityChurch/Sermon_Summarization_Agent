"""
Video Clip Generation Node

This module provides functionality to automatically generate short-form "recap" videos
from full sermon recordings. It uses AI-powered analysis to identify the most important
moments from the transcript, then uses FFMPEG to extract and concatenate those segments
into a summary video.

Key Features:
- AI-powered segment selection using GPT-4o-mini
- Intelligent segment merging and optimization
- FFMPEG-based video processing with proper audio/video sync
- GPU-accelerated encoding with automatic CPU fallback
- Configurable duration and quality settings
- Comprehensive metadata output

Workflow:
1. Load transcript segments and summary data
2. Use AI to score segments by importance (1-10 scale)
3. Optimize selection (merge adjacent, filter short, fit duration)
4. Detect GPU encoding capability (NVIDIA CUDA)
5. Build FFMPEG filter_complex command (GPU or CPU)
6. Execute FFMPEG to generate summary video
7. Save metadata with segment information

GPU Encoding:
- Automatically detects NVIDIA GPU and CUDA support
- Uses h264_nvenc encoder for 3-5x faster encoding
- Falls back to CPU (libx264) if GPU unavailable or fails
- Maintains comparable quality to CPU encoding
- Configurable via ENABLE_GPU_ENCODING environment variable

System Requirements for GPU Encoding:
- NVIDIA GPU with CUDA support (GTX 900 series or newer recommended)
- NVIDIA drivers installed (nvidia-smi must be available)
- FFMPEG compiled with --enable-cuda --enable-nvenc
  * Windows: Download from https://github.com/BtbN/FFmpeg-Builds/releases
  * Linux: Build from source or use NVIDIA's FFMPEG build
- CUDA Toolkit (optional, but recommended for best performance)

Environment Variables:
- ENABLE_GPU_ENCODING: "true" (default) or "false" to disable GPU encoding
- GPU_ENCODER_PRESET: "p1" to "p7" (default: "p4" for balanced speed/quality)
  * p1: Fastest, lowest quality
  * p4: Balanced (recommended)
  * p7: Slowest, highest quality
- GPU_DEVICE_INDEX: CUDA device index (default: 0 for first GPU)
- MAX_CLIP_DURATION: Maximum clip duration in seconds (default: 600)
- MIN_SEGMENT_LENGTH: Minimum segment length in seconds (default: 30)
- CONTEXT_PADDING: Padding around segments in seconds (default: 2)
- MERGE_GAP_THRESHOLD: Gap threshold for merging segments (default: 15)
- ENABLE_FADE_TRANSITIONS: "true" or "false" (default: "true")
- FADE_DURATION: Fade duration in seconds (default: 0.5)
- CLIP_OUTPUT_DIR: Output directory (default: same as input)

Output:
- {ORIGINAL_FILENAME}_Summary.mp4 (summary video)
- {ORIGINAL_FILENAME}_Summary_metadata.json (processing details including GPU info)

Performance Comparison:
- CPU (libx264, medium preset): ~1x realtime (10 min video = 10 min encoding)
- GPU (h264_nvenc, p4 preset): ~3-5x realtime (10 min video = 2-3 min encoding)
- Quality: Comparable at similar settings (CRF 23 vs CQ 23)
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from utils.api_retry import call_llm_with_retry
from utils.token_counter import count_messages_tokens, get_global_tracker


# Configuration constants
MAX_CLIP_DURATION = int(os.environ.get("MAX_CLIP_DURATION", "600"))  # 10 minutes default
MIN_SEGMENT_LENGTH = int(os.environ.get("MIN_SEGMENT_LENGTH", "30"))  # 30 seconds minimum
CONTEXT_PADDING = int(os.environ.get("CONTEXT_PADDING", "5"))  # 5 seconds padding default
MERGE_GAP_THRESHOLD = int(os.environ.get("MERGE_GAP_THRESHOLD", "15"))  # 15 seconds merge gap default
ENABLE_FADE_TRANSITIONS = os.environ.get("ENABLE_FADE_TRANSITIONS", "true").lower() == "true"
FADE_DURATION = float(os.environ.get("FADE_DURATION", "0.5"))  # 0.5 seconds fade default
CLIP_OUTPUT_DIR = os.environ.get("CLIP_OUTPUT_DIR", "")  # Empty = same as original

# GPU Encoding Configuration
ENABLE_GPU_ENCODING = os.environ.get("ENABLE_GPU_ENCODING", "true").lower() == "true"
GPU_ENCODER_PRESET = os.environ.get("GPU_ENCODER_PRESET", "p6")  # p1-p7, p4 is balanced
GPU_DEVICE_INDEX = int(os.environ.get("GPU_DEVICE_INDEX", "0"))  # CUDA device index


def _check_nvidia_gpu_available() -> bool:
    """
    Check if NVIDIA GPU is available on the system.

    Uses nvidia-smi to detect NVIDIA GPU presence.

    Returns:
        True if NVIDIA GPU is detected, False otherwise
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0 and "GPU" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_ffmpeg_cuda_support() -> bool:
    """
    Check if FFMPEG has CUDA/NVENC support compiled in.

    Queries FFMPEG encoders to see if h264_nvenc is available.

    Returns:
        True if FFMPEG supports CUDA encoding, False otherwise
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_nvenc" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _detect_gpu_encoding_capability() -> Dict[str, Any]:
    """
    Detect GPU encoding capability and return configuration.

    Checks for:
    1. NVIDIA GPU presence (via nvidia-smi)
    2. FFMPEG CUDA/NVENC support (via ffmpeg -encoders)
    3. User preference (ENABLE_GPU_ENCODING env var)

    Returns:
        Dictionary with:
        - enabled: Whether GPU encoding should be used
        - gpu_available: Whether NVIDIA GPU is detected
        - ffmpeg_cuda_support: Whether FFMPEG has CUDA support
        - reason: Explanation of the decision
    """
    gpu_available = _check_nvidia_gpu_available()
    ffmpeg_cuda_support = _check_ffmpeg_cuda_support()
    user_enabled = ENABLE_GPU_ENCODING

    # Determine if GPU encoding should be enabled
    enabled = user_enabled and gpu_available and ffmpeg_cuda_support

    # Build reason string
    if not user_enabled:
        reason = "GPU encoding disabled by user (ENABLE_GPU_ENCODING=false)"
    elif not gpu_available:
        reason = "NVIDIA GPU not detected (nvidia-smi check failed)"
    elif not ffmpeg_cuda_support:
        reason = "FFMPEG does not have CUDA/NVENC support compiled in"
    elif enabled:
        reason = "GPU encoding enabled (NVIDIA GPU + FFMPEG CUDA support detected)"
    else:
        reason = "GPU encoding disabled (unknown reason)"

    return {
        "enabled": enabled,
        "gpu_available": gpu_available,
        "ffmpeg_cuda_support": ffmpeg_cuda_support,
        "reason": reason
    }


def _load_transcript_segments() -> Dict[str, Any]:
    """
    Load timestamped transcript segments from JSON file.
    
    Returns:
        Dictionary containing file path and list of segments
        
    Raises:
        FileNotFoundError: If transcription_segments.json doesn't exist
        ValueError: If file is empty or malformed
    """
    segments_path = Path("transcription_segments.json")
    
    if not segments_path.exists():
        raise FileNotFoundError(
            "transcription_segments.json not found. "
            "Run transcription first to generate timestamped segments."
        )
    
    try:
        data = json.loads(segments_path.read_text(encoding="utf-8"))
        
        if "segments" not in data or not data["segments"]:
            raise ValueError("No segments found in transcription_segments.json")
        
        return data
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in transcription_segments.json: {e}")


def _load_summary_data() -> Dict[str, Any]:
    """
    Load summary and tags for context in segment selection.
    
    Returns:
        Dictionary containing summary text and tags
        
    Raises:
        FileNotFoundError: If summary.json doesn't exist
    """
    summary_path = Path("summary.json")
    
    if not summary_path.exists():
        raise FileNotFoundError(
            "summary.json not found. "
            "Run summarization first to generate summary data."
        )
    
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        return data
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in summary.json: {e}")


def _get_original_video_path() -> Path:
    """
    Retrieve the original video file path from environment.
    
    The transcription node stores the original file path in SERMON_FILE_PATH.
    For video files, this will be the original MP4/MOV file before audio extraction.
    
    Returns:
        Path object pointing to the original video file
        
    Raises:
        FileNotFoundError: If video file path not found or file doesn't exist
        ValueError: If file is not a video format
    """
    # Check environment for file path
    file_path = os.environ.get("SERMON_FILE_PATH")
    
    if not file_path:
        raise FileNotFoundError(
            "Original video file path not found in environment. "
            "Ensure SERMON_FILE_PATH is set by transcription node."
        )
    
    video_path = Path(file_path)
    
    # If the path points to extracted audio (WAV), find the original video
    if video_path.suffix.lower() == ".wav":
        # Look for video file with same base name
        video_exts = [".mp4", ".mov", ".avi", ".mkv"]
        for ext in video_exts:
            potential_video = video_path.with_suffix(ext)
            if potential_video.exists():
                video_path = potential_video
                break
        else:
            raise FileNotFoundError(
                f"Original video file not found. Searched for: "
                f"{[str(video_path.with_suffix(ext)) for ext in video_exts]}"
            )
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Validate it's a video file
    video_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    if video_path.suffix.lower() not in video_exts:
        raise ValueError(
            f"File is not a supported video format: {video_path.suffix}. "
            f"Supported formats: {video_exts}"
        )
    
    print(f"Original video file: {video_path}")
    return video_path


def _parse_timestamp_to_seconds(timestamp: str) -> float:
    """
    Parse timestamp string to seconds.

    Supports formats: "MM:SS" or "HH:MM:SS"

    Args:
        timestamp: Time string like "02:30" or "1:02:30"

    Returns:
        Time in seconds as float
    """
    parts = timestamp.strip().split(":")

    if len(parts) == 2:  # MM:SS
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}. Expected MM:SS or HH:MM:SS")


def _find_segments_in_range(
    segments: List[Dict[str, Any]],
    start_time: float,
    end_time: float
) -> List[Dict[str, Any]]:
    """
    Find all transcript segments that overlap with the given time range.

    Args:
        segments: List of all transcript segments
        start_time: Range start in seconds
        end_time: Range end in seconds

    Returns:
        List of segments within the time range
    """
    matching_segments = []

    for seg in segments:
        seg_start = seg["start"]
        seg_end = seg["end"]

        # Check if segment overlaps with the range
        # Segment overlaps if: seg_start < end_time AND seg_end > start_time
        if seg_start < end_time and seg_end > start_time:
            matching_segments.append(seg)

    return matching_segments


def _merge_segments_into_range(
    segments: List[Dict[str, Any]],
    start_time: float,
    end_time: float,
    importance_score: int,
    reason: str
) -> Dict[str, Any]:
    """
    Merge multiple segments into a single time range.

    Args:
        segments: List of segments to merge
        start_time: Desired start time
        end_time: Desired end time
        importance_score: AI-assigned importance score
        reason: Reason for selection

    Returns:
        Single merged segment dictionary
    """
    if not segments:
        # No segments found, create empty range
        return {
            "start": start_time,
            "end": end_time,
            "start_str": f"{int(start_time//60):02d}:{int(start_time%60):02d}",
            "end_str": f"{int(end_time//60):02d}:{int(end_time%60):02d}",
            "text": "",
            "importance_score": importance_score,
            "selection_reason": reason
        }

    # Use the AI-specified time range, but combine text from all segments
    combined_text = " ".join(seg["text"] for seg in segments)

    return {
        "start": start_time,
        "end": end_time,
        "start_str": f"{int(start_time//60):02d}:{int(start_time%60):02d}",
        "end_str": f"{int(end_time//60):02d}:{int(end_time%60):02d}",
        "text": combined_text,
        "importance_score": importance_score,
        "selection_reason": reason
    }


def _select_important_segments_with_ai(
    segments: List[Dict[str, Any]],
    summary_data: Dict[str, Any],
    max_duration: int = MAX_CLIP_DURATION
) -> List[Dict[str, Any]]:
    """
    Use GPT-4o-mini to analyze transcript and select important TIME RANGES.

    This function sends the transcript and summary context to the AI, which returns
    time ranges (30-60 seconds each) representing the most important moments.
    This approach creates longer, more coherent clips instead of short isolated segments.

    Args:
        segments: List of transcript segments with start/end/text
        summary_data: Summary and tags for context
        max_duration: Maximum total duration in seconds (default: 600 = 10 min)

    Returns:
        List of selected time ranges with importance scores, sorted by timestamp
    """
    print(f"\n{'='*60}")
    print("AI SEGMENT SELECTION (TIME RANGES)")
    print(f"{'='*60}")
    print(f"Analyzing {len(segments)} segments...")
    print(f"Target duration: {max_duration} seconds ({max_duration/60:.1f} minutes)")

    # Initialize GPT-4o-mini
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    # Prepare context
    summary_text = summary_data.get("summary", "")
    tags = summary_data.get("tags", [])

    # Build system prompt - NOW REQUESTING TIME RANGES
    system_prompt = (
        "You are an expert video editor specializing in creating engaging sermon highlight reels. "
        "Your task is to analyze a sermon transcript and identify the most important TIME RANGES "
        "that should be included in a 10-minute summary video.\n\n"
        "**IMPORTANT**: Select LONGER, COHERENT TIME RANGES (30-60 seconds each), not individual sentences. "
        "Each selection should capture a complete thought, story, or teaching point.\n\n"
        "Consider the following when selecting ranges:\n"
        "1. **Introduction** (score: 8-10): Opening 30-60s with scripture reading and topic introduction\n"
        "2. **Key Points** (score: 8-10): 45-60s segments covering main arguments and core teachings\n"
        "3. **Illustrations** (score: 7-9): 30-45s segments with memorable stories and examples\n"
        "4. **Application** (score: 8-10): 45-60s segments with practical takeaways and calls to action\n"
        "5. **Conclusion** (score: 8-10): Final 30-45s with summary and closing thoughts\n\n"
        "Return a JSON array of TIME RANGES with this structure:\n"
        "[\n"
        '  {"start_time": "00:00", "end_time": "00:45", "score": 9, "reason": "Opening scripture and topic introduction"},\n'
        '  {"start_time": "05:20", "end_time": "06:15", "score": 10, "reason": "Core theological point about grace with illustration"},\n'
        '  {"start_time": "12:30", "end_time": "13:20", "score": 8, "reason": "Practical application for daily life"},\n'
        "  ...\n"
        "]\n\n"
        "Guidelines:\n"
        "- Select 8-12 time ranges that tell a coherent story when combined\n"
        "- Each range should be 30-60 seconds long (longer is better for coherence)\n"
        "- Prioritize ranges aligned with the summary themes\n"
        "- Ensure narrative flow (intro → body → conclusion)\n"
        "- Target total duration around 10 minutes\n"
        "- Use MM:SS format for timestamps (e.g., '05:30' for 5 minutes 30 seconds)\n"
        "- Return ONLY the JSON array, no additional text"
    )

    # Build user prompt with full transcript (not individual segments)
    # This allows AI to see the full context and select coherent time ranges
    full_transcript = ""
    for seg in segments:
        full_transcript += f"[{seg['start_str']}] {seg['text']} "

    # Get total sermon duration
    total_duration = segments[-1]["end"] if segments else 0
    total_duration_str = f"{int(total_duration//60)}:{int(total_duration%60):02d}"

    user_prompt = (
        f"=== SERMON SUMMARY ===\n{summary_text}\n\n"
        f"=== KEY THEMES ===\n{', '.join(tags) if tags else 'Not specified'}\n\n"
        f"=== SERMON DURATION ===\n{total_duration_str} ({total_duration:.0f} seconds)\n\n"
        f"=== FULL TRANSCRIPT ===\n{full_transcript}\n\n"
        f"=== TASK ===\n"
        f"Analyze the transcript above and return a JSON array of TIME RANGES (30-60 seconds each) "
        f"representing the most important moments for a {max_duration/60:.0f}-minute highlight reel. "
        f"Each range should include start_time (MM:SS), end_time (MM:SS), score (1-10), and reason. "
        f"Select 8-12 ranges that tell a coherent story."
    )

    # Call AI with retry logic
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    input_tokens = count_messages_tokens(messages)
    print(f"Sending request to GPT-4o-mini ({input_tokens} input tokens)...")

    response = call_llm_with_retry(llm, messages, max_retries=3)
    response_text = response.content.strip()

    output_tokens = count_messages_tokens([{"role": "assistant", "content": response_text}])
    total_tokens = input_tokens + output_tokens

    # Track tokens for clip generation
    tracker = get_global_tracker()
    tracker.add_clip_generation_tokens(input_tokens, output_tokens)

    print(f"AI analysis complete. Tokens used: {total_tokens} (input: {input_tokens}, output: {output_tokens})")

    # Parse AI response - NOW EXPECTING TIME RANGES
    try:
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        time_ranges = json.loads(response_text)

        if not isinstance(time_ranges, list):
            raise ValueError("AI response is not a JSON array")

        print(f"AI selected {len(time_ranges)} time ranges")

        # Convert time ranges to segment objects
        selected_segments = []
        total_duration = segments[-1]["end"] if segments else 0

        for i, range_obj in enumerate(time_ranges):
            try:
                start_time_str = range_obj.get("start_time", "")
                end_time_str = range_obj.get("end_time", "")
                score = range_obj.get("score", 0)
                reason = range_obj.get("reason", "")

                if not start_time_str or not end_time_str:
                    print(f"Warning: Missing start_time or end_time in range {i}, skipping")
                    continue

                # Parse timestamps
                start_time = _parse_timestamp_to_seconds(start_time_str)
                end_time = _parse_timestamp_to_seconds(end_time_str)

                # Validate time range
                if start_time >= end_time:
                    print(f"Warning: Invalid time range {start_time_str} - {end_time_str} (start >= end), skipping")
                    continue

                if start_time < 0 or end_time > total_duration:
                    print(f"Warning: Time range {start_time_str} - {end_time_str} exceeds video bounds, clamping")
                    start_time = max(0, start_time)
                    end_time = min(total_duration, end_time)

                # Find all segments within this time range
                range_segments = _find_segments_in_range(segments, start_time, end_time)

                # Merge into a single segment
                merged_segment = _merge_segments_into_range(
                    range_segments,
                    start_time,
                    end_time,
                    score,
                    reason
                )

                duration = end_time - start_time
                print(f"  Range {i+1}: {start_time_str} - {end_time_str} ({duration:.0f}s) - {reason}")

                selected_segments.append(merged_segment)

            except (ValueError, KeyError) as e:
                print(f"Warning: Error processing range {i}: {e}, skipping")
                continue

        if not selected_segments:
            raise ValueError("No valid time ranges found in AI response")

        # Sort by timestamp (maintain chronological order)
        selected_segments.sort(key=lambda x: x["start"])

        total_selected_duration = sum(seg["end"] - seg["start"] for seg in selected_segments)
        print(f"\nTotal selected duration: {total_selected_duration:.0f}s ({total_selected_duration/60:.1f} min)")

        return selected_segments

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing AI response: {e}")
        print(f"Response was: {response_text[:500]}...")
        raise ValueError(f"Failed to parse AI segment selection: {e}")


def _optimize_segment_selection(
    selected_segments: List[Dict[str, Any]],
    max_duration: int = MAX_CLIP_DURATION,
    min_segment_length: int = MIN_SEGMENT_LENGTH,
    context_padding: int = 5,
    merge_gap_threshold: int = 15
) -> List[Dict[str, Any]]:
    """
    Optimize selected segments to fit within duration constraint.

    This function:
    1. Extends segments with context padding for smoother transitions
    2. Merges segments with larger gap threshold (15s instead of 5s)
    3. Ensures minimum segment length for coherence
    4. Trims selection to fit within max_duration
    5. Maintains chronological order

    Args:
        selected_segments: Segments selected by AI (sorted by timestamp)
        max_duration: Maximum total duration in seconds
        min_segment_length: Minimum length for individual segments
        context_padding: Seconds to add before/after each segment for context (default: 5)
        merge_gap_threshold: Maximum gap in seconds to merge segments (default: 15)

    Returns:
        Optimized list of segments
    """
    print(f"\n{'='*60}")
    print("SEGMENT OPTIMIZATION (ENHANCED)")
    print(f"{'='*60}")

    if not selected_segments:
        return []

    # Step 0: Extend segments with context padding
    # This adds a few seconds before/after each segment for smoother transitions
    print(f"Extending segments with {context_padding}s context padding...")
    extended = []
    for seg in selected_segments:
        extended_seg = seg.copy()
        extended_seg["start"] = max(0, seg["start"] - context_padding)
        extended_seg["end"] = seg["end"] + context_padding  # Will be clamped later if needed

        # Update time strings
        extended_seg["start_str"] = f"{int(extended_seg['start']//60):02d}:{int(extended_seg['start']%60):02d}"
        extended_seg["end_str"] = f"{int(extended_seg['end']//60):02d}:{int(extended_seg['end']%60):02d}"

        extended.append(extended_seg)

    # Step 1: Merge segments with larger gap threshold (15s instead of 5s)
    merged = []
    current = extended[0].copy()

    for next_seg in extended[1:]:
        # If segments are within merge_gap_threshold seconds, merge them
        gap = next_seg["start"] - current["end"]

        if gap <= merge_gap_threshold:
            # Merge: extend current segment to include next (and fill the gap)
            current["end"] = next_seg["end"]
            current["end_str"] = next_seg["end_str"]
            current["text"] += " " + next_seg["text"]
            current["importance_score"] = max(
                current["importance_score"],
                next_seg["importance_score"]
            )
            print(f"  Merged segments (gap: {gap:.1f}s): {current['start_str']} - {current['end_str']}")
        else:
            # Gap too large, save current and start new
            merged.append(current)
            current = next_seg.copy()

    # Don't forget the last segment
    merged.append(current)

    print(f"After merging: {len(merged)} segments (from {len(extended)} extended segments)")
    print(f"Merge gap threshold: {merge_gap_threshold}s (increased from 5s for better coherence)")

    # Step 2: Filter out segments that are too short
    filtered = []
    for seg in merged:
        duration = seg["end"] - seg["start"]
        if duration >= min_segment_length:
            filtered.append(seg)
        else:
            print(f"  Filtered out short segment ({duration:.1f}s): {seg['start_str']} - {seg['end_str']}")

    print(f"After filtering: {len(filtered)} segments (min length: {min_segment_length}s)")

    # Step 3: Ensure total duration fits within max_duration
    total_duration = sum(seg["end"] - seg["start"] for seg in filtered)

    if total_duration <= max_duration:
        print(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min) - within limit")
        return filtered

    print(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min) - exceeds limit")
    print(f"Trimming to fit within {max_duration}s ({max_duration/60:.1f} min)...")

    # Sort by importance score (descending) to keep best segments
    filtered.sort(key=lambda x: x["importance_score"], reverse=True)

    # Select segments until we hit duration limit
    final_segments = []
    current_duration = 0

    for seg in filtered:
        seg_duration = seg["end"] - seg["start"]
        if current_duration + seg_duration <= max_duration:
            final_segments.append(seg)
            current_duration += seg_duration
        else:
            print(f"  Skipped segment (would exceed limit): {seg['start_str']} - {seg['end_str']}")

    # Re-sort by timestamp for chronological order
    final_segments.sort(key=lambda x: x["start"])

    final_duration = sum(seg["end"] - seg["start"] for seg in final_segments)
    print(f"Final selection: {len(final_segments)} segments, {final_duration:.1f}s ({final_duration/60:.1f} min)")

    return final_segments


def _build_ffmpeg_command(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_path: Path,
    enable_fades: bool = ENABLE_FADE_TRANSITIONS,
    fade_duration: float = FADE_DURATION,
    use_gpu: bool = False
) -> List[str]:
    """
    Build FFMPEG filter_complex command for extracting and concatenating segments.

    Uses the filter_complex approach for reliable, seamless concatenation with
    proper audio/video sync. Optionally adds fade-in/fade-out transitions.

    Supports both CPU (libx264) and GPU (h264_nvenc) encoding.

    Args:
        video_path: Path to original video file
        segments: List of segments to extract (with start/end times)
        output_path: Path for output video file
        enable_fades: Whether to add fade transitions (default: from config)
        fade_duration: Duration of fade effects in seconds (default: from config)
        use_gpu: Whether to use GPU-accelerated encoding (default: False)

    Returns:
        List of command arguments for subprocess.run()

    Notes:
        GPU Encoding Requirements:
        - NVIDIA GPU with CUDA support
        - FFMPEG compiled with --enable-cuda --enable-nvenc
        - nvidia-smi must be available

        GPU Encoding Benefits:
        - 3-5x faster encoding on supported hardware
        - Lower CPU usage during encoding
        - Similar quality to CPU encoding at comparable settings

        GPU Encoder Presets (p1-p7):
        - p1: Fastest, lowest quality
        - p4: Balanced (default) - good speed/quality tradeoff
        - p7: Slowest, highest quality
    """
    if not segments:
        raise ValueError("No segments provided for video generation")

    print(f"Building FFMPEG command with {len(segments)} segments...")
    if enable_fades:
        print(f"Fade transitions enabled (duration: {fade_duration}s)")
    if use_gpu:
        print(f"GPU encoding enabled (h264_nvenc, preset: {GPU_ENCODER_PRESET})")

    # Build filter_complex string
    filter_parts = []
    video_labels = []
    audio_labels = []

    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        duration = end - start

        # Video filter: trim, reset PTS, and optionally add fades
        if enable_fades and duration > fade_duration * 2:
            # Add fade-in at start and fade-out at end
            # fade=t=in:st=0:d=FADE_DURATION,fade=t=out:st=DURATION-FADE_DURATION:d=FADE_DURATION
            fade_out_start = duration - fade_duration
            video_filter = (
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
                f"fade=t=in:st=0:d={fade_duration},"
                f"fade=t=out:st={fade_out_start}:d={fade_duration}[v{i}]"
            )
        else:
            # No fades if segment is too short or fades disabled
            video_filter = f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]"

        filter_parts.append(video_filter)
        video_labels.append(f"[v{i}]")

        # Audio filter: trim, reset PTS, and optionally add fades
        if enable_fades and duration > fade_duration * 2:
            # Add audio fade-in and fade-out
            fade_out_start = duration - fade_duration
            audio_filter = (
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={fade_duration},"
                f"afade=t=out:st={fade_out_start}:d={fade_duration}[a{i}]"
            )
        else:
            # No fades if segment is too short or fades disabled
            audio_filter = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]"

        filter_parts.append(audio_filter)
        audio_labels.append(f"[a{i}]")

    # Concatenate all segments
    # For concat filter with v=1:a=1, inputs must be interleaved: [v0][a0][v1][a1]...
    interleaved_labels = []
    for i in range(len(segments)):
        interleaved_labels.append(f"[v{i}]")
        interleaved_labels.append(f"[a{i}]")

    concat_filter = (
        f"{''.join(interleaved_labels)}"
        f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
    )
    filter_parts.append(concat_filter)

    # Join all filter parts with semicolons
    filter_complex = ";".join(filter_parts)

    # Build complete FFMPEG command
    cmd = ["ffmpeg"]

    # Add hardware acceleration flags for GPU encoding
    if use_gpu:
        # Use CUDA hardware acceleration for decoding
        # Note: We don't use -hwaccel_output_format cuda because our filters
        # (trim, setpts, fade) need to operate on CPU frames. The workflow is:
        # 1. Decode with CUDA (GPU) - faster input reading
        # 2. Transfer to CPU for filtering (trim, setpts, fade)
        # 3. Transfer back to GPU for h264_nvenc encoding
        cmd.extend([
            "-hwaccel", "cuda",
            "-hwaccel_device", str(GPU_DEVICE_INDEX)
        ])

    # Add input file and filter
    cmd.extend([
        "-i", str(video_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]"
    ])

    # Add video encoding settings (CPU or GPU)
    if use_gpu:
        # GPU encoding with h264_nvenc
        # Preset: p1 (fastest) to p7 (slowest/best quality)
        # CQ (Constant Quality): 0-51, lower = better quality (similar to CRF)
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", GPU_ENCODER_PRESET,  # p1-p7, p4 is balanced
            "-cq", "23",  # Constant Quality (similar to CRF)
            "-b:v", "0",  # Use CQ mode (0 = no bitrate limit)
            "-rc", "vbr",  # Variable bitrate mode
        ])
    else:
        # CPU encoding with libx264
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",  # Balance between speed and quality
            "-crf", "23",  # Constant Rate Factor (18-28, lower = better quality)
        ])

    # Add audio encoding settings (same for both CPU and GPU)
    cmd.extend([
        "-c:a", "aac",
        "-b:a", "192k",
        "-y",  # Overwrite output file if exists
        str(output_path)
    ])

    return cmd


def _execute_ffmpeg_command(cmd: List[str], total_duration: float = 0) -> Dict[str, Any]:
    """
    Execute FFMPEG command with real-time progress monitoring and error handling.

    Args:
        cmd: FFMPEG command as list of arguments
        total_duration: Total duration of output video in seconds (for progress calculation)

    Returns:
        Dictionary with execution statistics (duration, success)

    Raises:
        RuntimeError: If FFMPEG execution fails
    """
    import re
    import time

    print(f"\n{'='*60}")
    print("VIDEO PROCESSING")
    print(f"{'='*60}")
    print(f"Running FFMPEG command...")
    print(f"Command: {' '.join(cmd[:3])} ... (full command logged)")

    start_time = time.time()

    try:
        # Run FFMPEG with real-time output capture for progress monitoring
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # FFMPEG writes progress to stderr
        stderr_output = []
        last_progress_time = 0

        print("\nProgress:")

        for line in process.stderr:
            stderr_output.append(line)

            # Parse progress from FFMPEG output
            # FFMPEG outputs lines like: "frame=  123 fps= 45 q=28.0 size=    1024kB time=00:00:05.12 bitrate=1638.4kbits/s speed=1.5x"
            if "time=" in line:
                # Extract time processed
                time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if time_match:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
                    seconds = float(time_match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds

                    # Calculate percentage if total duration is known
                    if total_duration > 0:
                        percentage = (current_time / total_duration) * 100
                        percentage = min(100, percentage)  # Cap at 100%

                        # Update progress every 2 seconds to avoid spam
                        if time.time() - last_progress_time >= 2:
                            print(f"  {percentage:.1f}% complete ({current_time:.1f}s / {total_duration:.1f}s)")
                            last_progress_time = time.time()
                    else:
                        # No total duration, just show time processed
                        if time.time() - last_progress_time >= 2:
                            print(f"  Processed: {current_time:.1f}s")
                            last_progress_time = time.time()

        # Wait for process to complete
        process.wait()

        execution_time = time.time() - start_time

        if process.returncode != 0:
            error_msg = (
                f"FFMPEG failed with exit code {process.returncode}\n"
                f"STDERR: {''.join(stderr_output[-50:])}\n"  # Last 50 lines
                f"Command: {' '.join(cmd)}"
            )
            print(f"\nERROR: {error_msg}")
            raise RuntimeError(error_msg)

        print(f"\nFFMPEG processing complete! (took {execution_time:.1f}s)")

        return {
            "success": True,
            "execution_time_seconds": execution_time,
            "ffmpeg_output": "".join(stderr_output)
        }

    except FileNotFoundError:
        raise RuntimeError(
            "FFMPEG not found. Please install FFMPEG and add it to your system PATH.\n"
            "Download from: https://ffmpeg.org/download.html\n"
            "Windows: choco install ffmpeg\n"
            "macOS: brew install ffmpeg\n"
            "Linux: apt install ffmpeg"
        )
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"\nERROR: FFMPEG execution failed after {execution_time:.1f}s: {e}")
        raise


@tool
def generate_video_clip(state: dict | None = None):
    """
    Generate a summary video clip from the full sermon recording.

    This tool analyzes the transcript segments using AI to identify the most
    important moments, then uses FFMPEG to extract and concatenate those segments
    into a cohesive summary video under 10 minutes in length.

    Reads:
    - transcription_segments.json (timestamped segments)
    - summary.json (summary and tags for context)
    - Original video file (from environment)

    Writes:
    - {ORIGINAL_FILENAME}_Summary.mp4 (summary video)
    - {ORIGINAL_FILENAME}_Summary_metadata.json (segment info and statistics)

    Returns:
        JSON string with keys: {"status", "output_path", "duration", "segment_count"}
    """
    import time

    try:
        workflow_start_time = time.time()

        print(f"\n{'='*80}")
        print("VIDEO CLIP GENERATION (PHASE 2 ENHANCED)")
        print(f"{'='*80}\n")

        # Step 1: Load data
        print("Loading transcript segments and summary data...")
        transcript_data = _load_transcript_segments()
        summary_data = _load_summary_data()
        video_path = _get_original_video_path()

        segments = transcript_data["segments"]
        original_video_duration = segments[-1]["end"] if segments else 0
        print(f"Loaded {len(segments)} transcript segments")
        print(f"Original video duration: {original_video_duration:.1f}s ({original_video_duration/60:.1f} min)")

        # Step 2: AI segment selection
        ai_start_time = time.time()
        selected_segments = _select_important_segments_with_ai(
            segments,
            summary_data,
            max_duration=MAX_CLIP_DURATION
        )
        ai_duration = time.time() - ai_start_time

        if not selected_segments:
            raise ValueError("AI did not select any segments")

        # Store original selection count for metadata
        original_selection_count = len(selected_segments)

        # Step 3: Optimize selection
        optimization_start_time = time.time()
        optimized_segments = _optimize_segment_selection(
            selected_segments,
            max_duration=MAX_CLIP_DURATION,
            min_segment_length=MIN_SEGMENT_LENGTH,
            context_padding=CONTEXT_PADDING,
            merge_gap_threshold=MERGE_GAP_THRESHOLD
        )
        optimization_duration = time.time() - optimization_start_time

        if not optimized_segments:
            raise ValueError("No segments remaining after optimization")

        # Step 4: Determine output path
        if CLIP_OUTPUT_DIR:
            output_dir = Path(CLIP_OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = video_path.parent

        output_filename = f"{video_path.stem}_Summary.mp4"
        output_path = output_dir / output_filename

        print(f"\nOutput will be saved to: {output_path}")

        # Step 5: Detect GPU encoding capability
        gpu_config = _detect_gpu_encoding_capability()
        print(f"\nGPU Encoding Status: {gpu_config['reason']}")

        use_gpu = gpu_config["enabled"]
        gpu_fallback_occurred = False

        # Step 6: Build and execute FFMPEG command (with GPU fallback)
        total_output_duration = sum(seg["end"] - seg["start"] for seg in optimized_segments)

        # Try GPU encoding first if enabled
        if use_gpu:
            try:
                print("\nAttempting GPU-accelerated encoding...")
                ffmpeg_cmd = _build_ffmpeg_command(
                    video_path,
                    optimized_segments,
                    output_path,
                    enable_fades=ENABLE_FADE_TRANSITIONS,
                    fade_duration=FADE_DURATION,
                    use_gpu=True
                )
                ffmpeg_stats = _execute_ffmpeg_command(ffmpeg_cmd, total_duration=total_output_duration)
            except Exception as gpu_error:
                print(f"\n⚠️  GPU encoding failed: {gpu_error}")
                print("Falling back to CPU encoding...")
                gpu_fallback_occurred = True
                use_gpu = False

                # Retry with CPU encoding
                ffmpeg_cmd = _build_ffmpeg_command(
                    video_path,
                    optimized_segments,
                    output_path,
                    enable_fades=ENABLE_FADE_TRANSITIONS,
                    fade_duration=FADE_DURATION,
                    use_gpu=False
                )
                ffmpeg_stats = _execute_ffmpeg_command(ffmpeg_cmd, total_duration=total_output_duration)
        else:
            # Use CPU encoding directly
            print("\nUsing CPU encoding...")
            ffmpeg_cmd = _build_ffmpeg_command(
                video_path,
                optimized_segments,
                output_path,
                enable_fades=ENABLE_FADE_TRANSITIONS,
                fade_duration=FADE_DURATION,
                use_gpu=False
            )
            ffmpeg_stats = _execute_ffmpeg_command(ffmpeg_cmd, total_duration=total_output_duration)

        # Step 6: Verify output file was created
        if not output_path.exists():
            raise RuntimeError("FFMPEG completed but output file was not created")

        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        original_size_mb = video_path.stat().st_size / (1024 * 1024)
        size_reduction_ratio = (1 - (output_size_mb / original_size_mb)) * 100 if original_size_mb > 0 else 0

        print(f"Output file created: {output_path}")
        print(f"File size: {output_size_mb:.1f} MB (original: {original_size_mb:.1f} MB, {size_reduction_ratio:.1f}% reduction)")

        # Step 7: Save enhanced metadata
        total_duration = sum(seg["end"] - seg["start"] for seg in optimized_segments)
        workflow_duration = time.time() - workflow_start_time

        # Get token usage from global tracker
        tracker = get_global_tracker()
        clip_input_tokens = tracker.clip_generation_input_tokens
        clip_output_tokens = tracker.clip_generation_output_tokens
        clip_total_tokens = clip_input_tokens + clip_output_tokens

        metadata = {
            "version": "2.0",  # Phase 2 enhanced metadata
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),

            # Video information
            "original_video": {
                "path": str(video_path),
                "duration_seconds": original_video_duration,
                "file_size_mb": original_size_mb
            },
            "output_video": {
                "path": str(output_path),
                "duration_seconds": total_duration,
                "file_size_mb": output_size_mb,
                "size_reduction_percent": size_reduction_ratio
            },

            # Processing statistics
            "processing_stats": {
                "total_workflow_time_seconds": workflow_duration,
                "ai_selection_time_seconds": ai_duration,
                "optimization_time_seconds": optimization_duration,
                "ffmpeg_execution_time_seconds": ffmpeg_stats.get("execution_time_seconds", 0),
                "original_segment_count": len(segments),
                "ai_selected_count": original_selection_count,
                "final_segment_count": len(optimized_segments)
            },

            # Configuration used
            "configuration": {
                "max_clip_duration": MAX_CLIP_DURATION,
                "min_segment_length": MIN_SEGMENT_LENGTH,
                "context_padding": CONTEXT_PADDING,
                "merge_gap_threshold": MERGE_GAP_THRESHOLD,
                "enable_fade_transitions": ENABLE_FADE_TRANSITIONS,
                "fade_duration": FADE_DURATION,
                "gpu_encoding_enabled": use_gpu,
                "gpu_encoding_attempted": gpu_config["enabled"],
                "gpu_fallback_occurred": gpu_fallback_occurred,
                "gpu_encoder_preset": GPU_ENCODER_PRESET if use_gpu else None
            },

            # GPU encoding information
            "gpu_info": {
                "gpu_available": gpu_config["gpu_available"],
                "ffmpeg_cuda_support": gpu_config["ffmpeg_cuda_support"],
                "encoding_method": "GPU (h264_nvenc)" if use_gpu else "CPU (libx264)",
                "status": gpu_config["reason"]
            },

            # Token usage information
            "tokens": {
                "total": clip_total_tokens,
                "input": clip_input_tokens,
                "output": clip_output_tokens
            },

            # Detailed segment information
            "segments": [
                {
                    "index": i,
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "duration_seconds": seg["end"] - seg["start"],
                    "start_time_formatted": seg["start_str"],
                    "end_time_formatted": seg["end_str"],
                    "importance_score": seg.get("importance_score", 0),
                    "selection_reason": seg.get("selection_reason", ""),
                    "text_preview": seg["text"][:250] + "..." if len(seg["text"]) > 250 else seg["text"],
                    "full_text_length": len(seg["text"])
                }
                for i, seg in enumerate(optimized_segments)
            ],

            # Summary statistics
            "summary": {
                "total_segments": len(optimized_segments),
                "total_duration_seconds": total_duration,
                "total_duration_formatted": f"{int(total_duration//60)}:{int(total_duration%60):02d}",
                "average_segment_duration": total_duration / len(optimized_segments) if optimized_segments else 0,
                "compression_ratio": (original_video_duration / total_duration) if total_duration > 0 else 0,
                "average_importance_score": sum(seg.get("importance_score", 0) for seg in optimized_segments) / len(optimized_segments) if optimized_segments else 0
            }
        }

        metadata_path = output_path.with_name(f"{output_path.stem}_metadata.json")
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nEnhanced metadata saved to: {metadata_path}")
        print(f"  - Processing time: {workflow_duration:.1f}s")
        print(f"  - Compression ratio: {metadata['summary']['compression_ratio']:.1f}x")
        print(f"  - Average importance score: {metadata['summary']['average_importance_score']:.1f}/10")
        print(f"  - AI tokens used: {clip_total_tokens} (input: {clip_input_tokens}, output: {clip_output_tokens})")

        # Step 8: Return result
        print(f"\n{'='*80}")
        print("CLIP GENERATION COMPLETE")
        print(f"{'='*80}")
        print(f"Summary video: {output_path}")
        print(f"Duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        print(f"Segments: {len(optimized_segments)}")
        print(f"File size: {output_size_mb:.1f} MB")

        result = {
            "status": "success",
            "output_path": str(output_path),
            "duration_seconds": total_duration,
            "segment_count": len(optimized_segments),
            "file_size_mb": output_size_mb
        }

        return json.dumps(result)

    except Exception as e:
        error_msg = f"Video clip generation failed: {e}"
        print(f"\nERROR: {error_msg}")

        return json.dumps({
            "status": "error",
            "error": str(e)
        })

