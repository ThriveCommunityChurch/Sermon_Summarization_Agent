"""
Script to retry processing only the failed files from a previous batch run.

This script reads batch_summaries.json, identifies files with "error" status,
and reprocesses only those files.
"""

import json
import sys
from pathlib import Path
from agent import process_batch

def load_batch_results(batch_file: Path = Path("batch_summaries.json")) -> dict:
    """Load the batch results JSON file."""
    if not batch_file.exists():
        print(f"Error: {batch_file} not found.")
        print("Run a batch process first to generate this file.")
        sys.exit(1)
    
    with open(batch_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_failed_files(results: dict) -> list:
    """Extract list of failed filenames from batch results."""
    failed = []
    for key, data in results.items():
        if data.get("status") == "error":
            failed.append(data["filename"])
    return failed


def main():
    """Main function to retry failed files."""
    print("=" * 80)
    print("RETRY FAILED FILES")
    print("=" * 80)
    print()
    
    # Load previous batch results
    print("Loading previous batch results...")
    results = load_batch_results()
    
    # Get failed files
    failed_files = get_failed_files(results)
    
    if not failed_files:
        print("✅ No failed files found! All files processed successfully.")
        return
    
    print(f"Found {len(failed_files)} failed files:")
    print()
    
    # Show first 10 failed files as preview
    preview_count = min(10, len(failed_files))
    for i, filename in enumerate(failed_files[:preview_count], 1):
        print(f"  {i}. {filename}")
    
    if len(failed_files) > preview_count:
        print(f"  ... and {len(failed_files) - preview_count} more")
    
    print()
    print("=" * 80)
    
    # Ask for confirmation
    response = input(f"Retry processing these {len(failed_files)} files? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Cancelled.")
        return
    
    print()
    print("=" * 80)
    print(f"RETRYING {len(failed_files)} FAILED FILES")
    print("=" * 80)
    print()
    
    # Get the batch directory from user
    batch_dir = input("Enter the path to the audio files directory: ").strip().strip('"')
    batch_dir_path = Path(batch_dir)
    
    if not batch_dir_path.exists():
        print(f"Error: Directory not found: {batch_dir}")
        sys.exit(1)
    
    # Create a list of full paths for failed files
    failed_file_paths = []
    for filename in failed_files:
        file_path = batch_dir_path / filename
        if file_path.exists():
            failed_file_paths.append(str(file_path))
        else:
            print(f"Warning: File not found: {file_path}")
    
    if not failed_file_paths:
        print("Error: None of the failed files were found in the specified directory.")
        sys.exit(1)
    
    print(f"Found {len(failed_file_paths)} files to retry.")
    print()
    
    # Process only the failed files
    # Note: We'll pass the batch directory and let process_batch handle it,
    # but we need to modify the approach since process_batch processes all files
    
    # Alternative: Process files one by one
    from agent import process_single_file
    import datetime
    
    successful = 0
    still_failed = 0
    
    for i, file_path in enumerate(failed_file_paths, 1):
        filename = Path(file_path).name
        print("=" * 80)
        print(f"📝 Retrying file {i}/{len(failed_file_paths)}: {filename}")
        print("=" * 80)
        
        # Determine output directory
        file_stem = Path(file_path).stem
        output_dir = Path("batch_outputs") / file_stem
        
        try:
            result = process_single_file(file_path, output_dir)
            
            if result.get("status") == "success":
                successful += 1
                print(f"✅ Success: {filename}")
                print(f"   Summary: {result['summary'][:100]}...")
                print(f"   Word count: {result['word_count']}")
            else:
                still_failed += 1
                print(f"❌ Failed: {filename}")
                print(f"   Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            still_failed += 1
            print(f"❌ Failed: {filename}")
            print(f"   Error: {str(e)}")
        
        print()
    
    # Print final summary
    print("=" * 80)
    print("RETRY COMPLETE")
    print("=" * 80)
    print()
    print(f"Summary:")
    print(f"  Total files retried: {len(failed_file_paths)}")
    print(f"  Successful: {successful}")
    print(f"  Still failed: {still_failed}")
    print(f"  Success rate: {(successful / len(failed_file_paths) * 100):.1f}%")
    print()
    
    if still_failed > 0:
        print(f"⚠️  {still_failed} files still failed. Check the errors above.")
        print("   You may need to:")
        print("   - Check your internet connection")
        print("   - Verify your OpenAI API key and quota")
        print("   - Try again later if there are API issues")
    else:
        print("🎉 All files processed successfully!")


if __name__ == "__main__":
    main()

