import argparse
import os
import json
import datetime
import time
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage

from classes.agent_state import AgentState
from nodes.transcription_node import transcribe_audio
from nodes.waveform_node import generate_waveform
from nodes.summarization_node import summarize_sermon
from nodes.tagging_node import tag_sermon
from nodes.clip_generation_node import generate_video_clip
from utils.api_retry import call_llm_with_retry
from utils.token_counter import reset_global_tracker

# Load environment variables from .env file
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError(
        "OPENAI_API_KEY not found in environment variables. "
        "Please create a .env file with your OpenAI API key. "
        "See .env.example for reference."
    )


def should_continue(state):
    """Determine whether to continue processing or end the workflow."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If there is no function call, then we finish
    if not last_message.tool_calls:
        return "end"
    # Otherwise if there is, we continue
    else:
        return "continue"


def call_model(state):
    """Call the LLM model to determine next action with retry logic."""
    messages = state["messages"]
    response = call_llm_with_retry(model, messages, max_retries=3)
    return {"messages": [response]}


# Build tools - transcribe, waveform, summarize, tag, and clip generation
tools = [transcribe_audio, generate_waveform, summarize_sermon, tag_sermon, generate_video_clip]
tool_node = ToolNode(tools)

# Use GPT-4o-mini as the orchestration model
model = ChatOpenAI(model='gpt-4o-mini', api_key=api_key, temperature=0)
model = model.bind_tools(tools)

# Define the LangGraph workflow
workflow = StateGraph(MessagesState)

# Add nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# Add edges
workflow.add_edge(START, "agent")

# Conditional edge: agent -> tools or end
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END,
    },
)

# After tools execute, return to agent to allow sequential tool calls
workflow.add_edge("tools", "agent")

# Set up memory for conversation state
memory = MemorySaver()

# Compile the workflow
app = workflow.compile(checkpointer=memory)


def find_audio_files(directory: Path) -> List[Path]:
    """Find all supported audio/video files in the given directory."""
    supported_exts = {".mp3", ".mp4", ".wav", ".m4a", ".mov"}
    audio_files = []

    for file_path in directory.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_exts:
            audio_files.append(file_path)

    # Sort by modification time (oldest first)
    audio_files.sort(key=lambda p: p.stat().st_mtime)
    return audio_files


def is_file_already_processed(file_stem: str, outputs_dir: Path = Path("batch_outputs")) -> bool:
    """
    Check if a file has already been successfully processed.

    Args:
        file_stem: The filename without extension (e.g., "2025-01-05-Recording")
        outputs_dir: The batch outputs directory

    Returns:
        True if the file has been successfully processed, False otherwise
    """
    file_output_dir = outputs_dir / file_stem

    # Check if output directory exists
    if not file_output_dir.exists():
        return False

    # Check for required files
    transcription_path = file_output_dir / "transcription.txt"
    summary_json_path = file_output_dir / "summary.json"

    # Transcription must exist and be non-empty
    if not transcription_path.exists():
        return False

    try:
        transcription_text = transcription_path.read_text(encoding='utf-8').strip()
        if not transcription_text:
            return False
    except Exception:
        return False

    # Summary JSON must exist and be valid
    if not summary_json_path.exists():
        return False

    try:
        with open(summary_json_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)

        # Check if it has tags array (indicates successful completion of all steps)
        # OR if it explicitly has status: success
        has_tags = "tags" in summary_data and isinstance(summary_data["tags"], list)
        has_success_status = summary_data.get("status") == "success"

        if not (has_tags or has_success_status):
            return False

    except (json.JSONDecodeError, Exception):
        return False

    # All checks passed - file was successfully processed
    return True


def clear_batch_outputs(outputs_dir: Path = Path("batch_outputs")):
    """
    Clear the batch outputs directory for a clean run.

    Args:
        outputs_dir: The batch outputs directory to clear
    """
    if outputs_dir.exists():
        import shutil
        print(f"⚠️  Clearing {outputs_dir}/ directory (use --resume to preserve existing results)")
        shutil.rmtree(outputs_dir)
        print(f"   Removed {outputs_dir}/ directory")
    outputs_dir.mkdir(exist_ok=True)


def process_single_file(file_path: str, output_dir: Path = None) -> Dict[str, Any]:
    """
    Process a single sermon file through transcription and summarization.

    Args:
        file_path: Path to the audio/video file
        output_dir: Optional directory for outputs (default: current directory)

    Returns:
        Dictionary with processing results and metadata
    """
    # Reset token tracker for this file
    reset_global_tracker()

    # Change to output directory if specified
    original_dir = Path.cwd()
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(output_dir)

    try:
        # Set the file path in environment
        os.environ["SERMON_FILE_PATH"] = file_path

        # Create a unique thread for this file
        file_name = Path(file_path).stem
        thread = {"configurable": {"thread_id": f"sermon_{file_name}"}}
        thread["recursion_limit"] = 150

        # Create the initial message instructing the agent
        inputs = [
            HumanMessage(content=(
                "Please perform the following tasks in sequence:\n"
                "1) Use the transcribe_audio tool to transcribe the sermon audio/video file\n"
                "2) Use the generate_waveform tool to generate audio waveform data from the audio file\n"
                "3) After transcription and waveform generation are complete, use the summarize_sermon tool to generate "
                "a single-paragraph summary of the sermon's core message and purpose\n"
                "4) After summarization is complete, use the tag_sermon tool to apply relevant "
                "semantic tags to the summary based on its content\n"
                "5) After tagging is complete, use the generate_video_clip tool to create a summary video "
                "clip from the most important moments (only if ENABLE_CLIP_GENERATION is true)"
            ))
        ]

        # Deterministic linear execution: transcribe -> waveform -> summarize -> tag -> clip (optional)
        try:
            transcribe_audio.invoke({})
            generate_waveform.invoke({})
            summarize_sermon.invoke({})
            tag_sermon.invoke({})

            # Conditionally generate clip
            if os.environ.get("ENABLE_CLIP_GENERATION", "false").lower() == "true":
                print("\nGenerating summary video clip...")
                generate_video_clip.invoke({})
            else:
                print("\nSkipping video clip generation (ENABLE_CLIP_GENERATION not set)")
        except Exception as e:
            raise

        # Read the generated summary
        summary_path = Path("summary.txt")
        summary_json_path = Path("summary.json")
        transcription_path = Path("transcription.txt")

        summary_text = ""
        word_count = 0

        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8").strip()
            word_count = len(summary_text.split())

        result = {
            "filename": Path(file_path).name,
            "summary": summary_text,
            "transcription_path": str(transcription_path.resolve()) if transcription_path.exists() else None,
            "summary_path": str(summary_path.resolve()) if summary_path.exists() else None,
            "word_count": word_count,
            "date_processed": datetime.datetime.now().isoformat(),
            "status": "success"
        }

        return result

    except Exception as e:
        return {
            "filename": Path(file_path).name,
            "summary": None,
            "transcription_path": None,
            "summary_path": None,
            "word_count": 0,
            "date_processed": datetime.datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }
    finally:
        # Return to original directory
        os.chdir(original_dir)


def process_batch(batch_dir: str, resume: bool = False) -> None:
    """
    Process all audio files in a directory in batch mode.

    Args:
        batch_dir: Path to directory containing audio files
        resume: If True, skip files that have already been successfully processed.
                If False, clear the batch_outputs directory before starting.
    """
    batch_path = Path(batch_dir)

    if not batch_path.exists():
        print(f"Error: Directory not found: {batch_dir}")
        return

    if not batch_path.is_dir():
        print(f"Error: Path is not a directory: {batch_dir}")
        return

    # Find all audio files
    audio_files = find_audio_files(batch_path)

    if not audio_files:
        print(f"No audio files found in: {batch_dir}")
        print("   Supported formats: MP3, MP4, WAV, M4A, MOV")
        return

    # Create outputs directory
    outputs_dir = Path("batch_outputs")

    # Handle resume vs clean run
    if resume:
        outputs_dir.mkdir(exist_ok=True)
        print("\n" + "="*80)
        print("SERMON SUMMARIZATION AGENT - BATCH MODE (RESUME)")
        print("="*80)
        print(f"\n✓ Resume mode enabled - skipping already processed files")

        # Check which files are already processed
        already_processed = []
        files_to_process = []

        for audio_file in audio_files:
            file_stem = audio_file.stem
            if is_file_already_processed(file_stem, outputs_dir):
                already_processed.append(audio_file)
            else:
                files_to_process.append(audio_file)

        print(f"\nProcessing directory: {batch_dir}")
        print(f"Found {len(audio_files)} total audio file(s)")
        print(f"  ✓ Already processed: {len(already_processed)}")
        print(f"  → To process: {len(files_to_process)}")

        if not files_to_process:
            print("\n🎉 All files have already been processed!")
            return

        # Update audio_files to only include files that need processing
        audio_files = files_to_process

    else:
        # Clean run - clear outputs directory
        clear_batch_outputs(outputs_dir)
        print("\n" + "="*80)
        print("SERMON SUMMARIZATION AGENT - BATCH MODE")
        print("="*80)
        print(f"\nProcessing directory: {batch_dir}")
        print(f"Found {len(audio_files)} audio file(s) to process\n")

    # Start timing
    batch_start_time = datetime.datetime.now()

    # Process each file
    batch_results = {}

    for idx, audio_file in enumerate(audio_files, 1):
        file_name = audio_file.stem

        print(f"\n{'='*80}")
        print(f"📝 Processing file {idx}/{len(audio_files)}: {audio_file.name}")

        # Calculate and display estimated time remaining (after first file)
        if idx > 1:
            elapsed = datetime.datetime.now() - batch_start_time
            avg_time_per_file = elapsed.total_seconds() / (idx - 1)
            remaining_files = len(audio_files) - idx + 1
            est_remaining_seconds = avg_time_per_file * remaining_files

            est_hours, remainder = divmod(int(est_remaining_seconds), 3600)
            est_minutes, est_seconds = divmod(remainder, 60)

            if est_hours > 0:
                print(f"⏱️  Est. time remaining: {est_hours}h {est_minutes}m {est_seconds}s")
            elif est_minutes > 0:
                print(f"⏱️  Est. time remaining: {est_minutes}m {est_seconds}s")
            else:
                print(f"⏱️  Est. time remaining: {est_seconds}s")

        print(f"{'='*80}\n")

        # Create subdirectory for this file's outputs
        file_output_dir = outputs_dir / file_name

        # Process the file
        result = process_single_file(str(audio_file), file_output_dir)

        # Store result using filename (without extension) as key
        batch_results[file_name] = result

        # Display result
        if result["status"] == "success":
            print(f"\nSuccessfully processed: {audio_file.name}")
            print(f"   Summary: {result['summary'][:100]}..." if len(result['summary']) > 100 else f"   Summary: {result['summary']}")
            print(f"   Word count: {result['word_count']}")
            print(f"   Outputs saved to: {file_output_dir}")
        else:
            print(f"\nFailed to process: {audio_file.name}")
            print(f"   Error: {result.get('error', 'Unknown error')}")

        print(f"\nProgress: {idx}/{len(audio_files)} files completed ({idx/len(audio_files)*100:.1f}%)")

        # Add a small delay between files to avoid rate limiting (except for last file)
        if idx < len(audio_files):
            time.sleep(2)  # 2 second delay between files

    # End timing
    batch_end_time = datetime.datetime.now()
    total_elapsed = batch_end_time - batch_start_time

    # Calculate timing statistics
    total_seconds = total_elapsed.total_seconds()
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    # Calculate average time per file
    avg_seconds_per_file = total_seconds / len(audio_files) if len(audio_files) > 0 else 0
    avg_minutes, avg_secs = divmod(int(avg_seconds_per_file), 60)

    # Write consolidated JSON output
    batch_json_path = Path("batch_summaries.json")
    with open(batch_json_path, "w", encoding="utf-8") as f:
        json.dump(batch_results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("BATCH PROCESSING COMPLETE")
    print("="*80)
    print(f"\n Summary:")
    print(f"   Total files: {len(audio_files)}")

    success_count = sum(1 for r in batch_results.values() if r["status"] == "success")
    error_count = len(audio_files) - success_count

    print(f"   Successful: {success_count}")
    print(f"   Failed: {error_count}")

    # Display timing information
    print(f"\n  Timing:")
    if hours > 0:
        print(f"   Total time: {hours}h {minutes}m {seconds}s")
    else:
        print(f"   Total time: {minutes}m {seconds}s")

    if avg_minutes > 0:
        print(f"   Average per file: {avg_minutes}m {avg_secs}s")
    else:
        print(f"   Average per file: {avg_secs}s")

    print(f"\n Consolidated results saved to: {batch_json_path.resolve()}")
    print(f" Individual outputs saved to: {outputs_dir.resolve()}")
    print()


def main():
    """Main entry point for the CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Transcribe and summarize sermon recordings using AI"
    )

    # Create mutually exclusive group for file vs batch processing
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--file", "-f",
        type=str,
        help="Path to a single sermon audio/video file (MP4, MP3, WAV, M4A, MOV)"
    )
    group.add_argument(
        "--batch-dir", "-b",
        type=str,
        help="Path to directory containing multiple sermon files for batch processing"
    )

    # Add resume flag for batch processing
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume batch processing by skipping already processed files (only works with --batch-dir)"
    )

    args = parser.parse_args()

    # Handle batch mode
    if args.batch_dir:
        process_batch(args.batch_dir, resume=args.resume)
        return

    # Warn if --resume is used without --batch-dir
    if args.resume and not args.batch_dir:
        print("Warning: --resume flag only works with --batch-dir. Ignoring.")
        print()

    # Handle single file mode
    if args.file:
        os.environ["SERMON_FILE_PATH"] = args.file
        print(f"Using provided file: {args.file}")
    else:
        print("No file specified. Will auto-detect latest file in sermon directory.")

    # Create a thread for this conversation
    thread = {"configurable": {"thread_id": "sermon_summarization_1"}}
    thread["recursion_limit"] = 150

    # Create the initial message instructing the agent
    inputs = [
        HumanMessage(content=(
            "Please perform the following tasks in sequence:\n"
            "1) Use the transcribe_audio tool to transcribe the sermon audio/video file\n"
            "2) Use the generate_waveform tool to generate audio waveform data from the audio file\n"
            "3) After transcription and waveform generation are complete, use the summarize_sermon tool to generate "
            "a single-paragraph summary of the sermon's core message and purpose\n"
            "4) After summarization is complete, use the tag_sermon tool to apply relevant "
            "semantic tags to the summary based on its content\n"
            "5) After tagging is complete, use the generate_video_clip tool to create a summary video "
            "clip from the most important moments (only if ENABLE_CLIP_GENERATION is true)"
        ))
    ]

    print("\n" + "="*80)
    print("SERMON SUMMARIZATION AGENT")
    print("="*80)
    print("\nStarting sermon transcription and summarization workflow...\n")

    # Deterministic linear execution: transcribe -> waveform -> summarize -> tag -> clip (optional)
    transcribe_audio.invoke({})
    generate_waveform.invoke({})
    summarize_sermon.invoke({})
    tag_sermon.invoke({})

    # Conditionally generate clip
    if os.environ.get("ENABLE_CLIP_GENERATION", "false").lower() == "true":
        print("\nGenerating summary video clip...")
        generate_video_clip.invoke({})
    else:
        print("\nSkipping video clip generation (ENABLE_CLIP_GENERATION not set)")

    print("\n" + "="*80)
    print("WORKFLOW COMPLETE")
    print("="*80)
    print("\nOutput files generated:")
    print("  - transcription.txt: Full sermon transcription")
    print("  - transcription_segments.json: Transcription with timestamps")
    print("  - summary.txt: Single-paragraph sermon summary")
    print("  - summary.json: Summary with metadata, tags, and waveform data")
    if os.environ.get("ENABLE_CLIP_GENERATION", "false").lower() == "true":
        print(f"  - {args.file.split('.')[0]}_Summary.mp4: Summary video clip")
        print(f"  - {args.file.split('.')[0]}_Summary_metadata.json: Clip generation metadata")
    print("\n")


if __name__ == "__main__":
    main()