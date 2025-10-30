#!/usr/bin/env python3
"""
Bulk Waveform Generator

Processes multiple audio files in a directory to generate waveform data.
Outputs line-by-line JSON progress updates to stdout for real-time tracking.
Saves individual waveform JSON files to waveform_outputs/{job_id}/ directory.

Usage:
    python bulk_waveform_generator.py --directory "path/to/audio/files" --job-id "unique-job-id"
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Import the waveform generation function from existing node
from nodes.waveform_node import _generate_waveform_data


def find_audio_files(directory: Path) -> List[Path]:
    """
    Find all supported audio/video files in the given directory.
    
    Args:
        directory: Path to directory to scan
        
    Returns:
        List of audio file paths sorted by name
    """
    supported_exts = {".mp3", ".mp4", ".wav", ".m4a", ".mov"}
    audio_files = []

    for file_path in directory.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_exts:
            audio_files.append(file_path)

    # Sort by filename for consistent ordering
    audio_files.sort(key=lambda p: p.name.lower())
    return audio_files


def output_progress(progress_type: str, data: Dict[str, Any]) -> None:
    """
    Output a progress update as a JSON line to stdout.
    
    Args:
        progress_type: Type of progress update (started, progress, file_complete, completed, error)
        data: Additional data for the progress update
    """
    progress_data = {
        "type": progress_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data
    }
    print(json.dumps(progress_data), flush=True)


def process_audio_file(
    audio_file: Path,
    output_dir: Path,
    sample_count: int = 480
) -> Dict[str, Any]:
    """
    Process a single audio file to generate waveform data.
    
    Args:
        audio_file: Path to audio file
        output_dir: Directory to save waveform JSON
        sample_count: Number of waveform samples to generate
        
    Returns:
        Dictionary with processing result
    """
    try:
        # Generate waveform data
        waveform_data = _generate_waveform_data(str(audio_file), sample_count=sample_count)
        
        # Get file size in MB
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Create output filename (replace extension with .json)
        output_filename = audio_file.stem + ".json"
        output_path = output_dir / output_filename
        
        # Save waveform data to JSON file
        waveform_json = {
            "filename": audio_file.name,
            "waveform_data": waveform_data,
            "sample_count": len(waveform_data),
            "file_size_mb": round(file_size_mb, 2),
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }
        
        output_path.write_text(
            json.dumps(waveform_json, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        # Try to return relative path if possible, otherwise use absolute path
        try:
            relative_path = output_path.relative_to(Path.cwd())
            output_path_str = str(relative_path)
        except ValueError:
            # If output_path is not relative to cwd (e.g., in temp directory), use absolute path
            output_path_str = str(output_path.resolve())

        return {
            "filename": audio_file.name,
            "status": "success",
            "sample_count": len(waveform_data),
            "file_size_mb": round(file_size_mb, 2),
            "output_path": output_path_str
        }
        
    except FileNotFoundError as e:
        return {
            "filename": audio_file.name,
            "status": "error",
            "error": f"File not found: {str(e)}"
        }
    except Exception as e:
        return {
            "filename": audio_file.name,
            "status": "error",
            "error": str(e)
        }


def main():
    """Main entry point for bulk waveform generation."""
    parser = argparse.ArgumentParser(
        description="Generate waveform data for multiple audio files in a directory"
    )
    parser.add_argument(
        "--directory", "-d",
        type=str,
        required=True,
        help="Path to directory containing audio files"
    )
    parser.add_argument(
        "--job-id", "-j",
        type=str,
        required=True,
        help="Unique job ID for this processing run"
    )
    parser.add_argument(
        "--sample-count", "-s",
        type=int,
        default=480,
        help="Number of waveform samples to generate (default: 480)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Output directory for waveform JSON files (default: waveform_outputs/{job_id})"
    )

    args = parser.parse_args()

    # Validate directory
    directory = Path(args.directory)
    if not directory.exists():
        output_progress("error", {
            "error": f"Directory not found: {args.directory}"
        })
        sys.exit(1)

    if not directory.is_dir():
        output_progress("error", {
            "error": f"Path is not a directory: {args.directory}"
        })
        sys.exit(1)

    # Find all audio files
    audio_files = find_audio_files(directory)

    if not audio_files:
        output_progress("error", {
            "error": "No audio files found in directory",
            "supported_formats": [".mp3", ".mp4", ".wav", ".m4a", ".mov"]
        })
        sys.exit(1)

    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("waveform_outputs") / args.job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output started message
    output_progress("started", {
        "total_files": len(audio_files),
        "job_id": args.job_id,
        "directory": str(directory)
    })
    
    # Track timing
    start_time = time.time()
    successful = 0
    failed = 0
    
    # Process each file
    for idx, audio_file in enumerate(audio_files, 1):
        # Output progress update
        output_progress("progress", {
            "current": idx,
            "total": len(audio_files),
            "filename": audio_file.name,
            "status": "processing"
        })
        
        # Process the file
        result = process_audio_file(audio_file, output_dir, args.sample_count)
        
        # Update counters
        if result["status"] == "success":
            successful += 1
        else:
            failed += 1
        
        # Output file completion
        output_progress("file_complete", result)
    
    # Calculate duration
    duration_seconds = time.time() - start_time
    
    # Output completion message
    output_progress("completed", {
        "total_files": len(audio_files),
        "successful": successful,
        "failed": failed,
        "duration_seconds": round(duration_seconds, 2),
        "output_directory": str(output_dir)
    })


if __name__ == "__main__":
    main()

