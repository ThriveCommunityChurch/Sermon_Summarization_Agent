import os
import json
import librosa
import numpy as np
from pathlib import Path
from langchain_core.tools import tool
from typing import List


def _generate_waveform_data(audio_file_path: str, sample_count: int = 480) -> List[float]:
    """
    Generate normalized waveform amplitude data from an audio file.

    Args:
        audio_file_path: Path to the audio file
        sample_count: Number of amplitude samples to generate (default: 480)
    
    Returns:
        List of normalized amplitude values between 0.15 and 1.0
    
    Raises:
        FileNotFoundError: If audio file doesn't exist
        Exception: If audio processing fails
    """
    try:
        # Load audio file (librosa automatically resamples)
        # sr=None preserves original sample rate, mono=True converts to single channel
        y, sr = librosa.load(audio_file_path, sr=None, mono=True)
        
        # Calculate samples per bar
        samples_per_bar = len(y) // sample_count
        waveform = []
        
        # Calculate RMS (Root Mean Square) for each bar
        for i in range(sample_count):
            start = i * samples_per_bar
            end = min(start + samples_per_bar, len(y))
            segment = y[start:end]
            
            # RMS provides better amplitude representation than peak values
            rms = np.sqrt(np.mean(segment**2))
            waveform.append(float(rms))
        
        # Normalize to 0.15-1.0 range
        waveform = np.array(waveform)
        min_val = waveform.min()
        max_val = waveform.max()
        
        # Handle uniform/silent audio
        if max_val - min_val < 0.0001:
            print("Audio appears to be uniform or silent, returning mid-level waveform")
            return [0.7] * sample_count
        
        # Scale to 0.15-1.0 range
        # Formula: 0.15 + ((value - min) / (max - min)) * 0.85
        normalized = 0.15 + ((waveform - min_val) / (max_val - min_val)) * 0.85
        
        return normalized.tolist()
    
    except FileNotFoundError:
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    except Exception as e:
        raise Exception(f"Failed to generate waveform: {str(e)}")


@tool
def generate_waveform(state: dict | None = None):
    """
    Generate audio waveform data from the extracted audio file.

    Reads the audio file path from environment (set by transcription node),
    generates 480 normalized amplitude values using RMS calculation,
    and saves to summary.json.
    
    Writes:
    - Updates summary.json with waveform_data field (or creates if doesn't exist)
    
    Returns a JSON string with keys: {"status", "sample_count", "waveform_path"}.
    """
    try:
        # Get audio file path from environment (set by transcription node)
        audio_file_path = os.environ.get("AUDIO_FILE_PATH")
        
        if not audio_file_path:
            raise ValueError(
                "Audio file path not found in environment. "
                "Run transcription first to set AUDIO_FILE_PATH."
            )
        
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        print(f"Generating waveform from: {audio_file_path}")
        print(f"Audio file size: {audio_path.stat().st_size / (1024*1024):.1f} MB")

        # Generate waveform data
        waveform_data = _generate_waveform_data(str(audio_path), sample_count=480)
        
        print(f"[OK] Generated {len(waveform_data)} amplitude values")
        print(f"  Range: {min(waveform_data):.3f} to {max(waveform_data):.3f}")
        
        # Read existing summary.json if it exists
        summary_json_path = Path("summary.json")
        if summary_json_path.exists():
            try:
                summary_data = json.loads(summary_json_path.read_text(encoding="utf-8"))
                print(f"Updating existing summary.json")
            except json.JSONDecodeError:
                print(f"Warning: summary.json exists but is invalid, creating new data")
                summary_data = {}
        else:
            print(f"Creating new summary.json")
            summary_data = {}
        
        # Add waveform data to summary
        summary_data["waveform_data"] = waveform_data
        
        # Write updated summary.json
        summary_json_path.write_text(
            json.dumps(summary_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        print(f"[OK] Waveform data saved to: {summary_json_path.resolve()}")
        
        # Return result
        result = {
            "status": "success",
            "sample_count": len(waveform_data),
            "waveform_path": str(summary_json_path.resolve()),
            "min_amplitude": min(waveform_data),
            "max_amplitude": max(waveform_data),
        }
        
        return json.dumps(result)
    
    except Exception as e:
        error_msg = f"Error generating waveform: {e}"
        print(f"[ERROR] {error_msg}")
        
        # Return error but don't fail the workflow
        # This allows summarization to continue even if waveform generation fails
        return json.dumps({
            "status": "error",
            "error": str(e),
            "sample_count": 0
        })

