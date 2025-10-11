#!/usr/bin/env python3
"""
Sermon Summary Update Automation Script

This script automates the process of updating sermon messages with summaries and tags in the Thrive Church Official App
with AI-generated summaries and tags from the batch_outputs directory.

Usage:
    python update_sermon_summaries.py [--dry-run] [--resume] [--folder FOLDER] [--use-cached-api] [--api-url URL] [--force-update]

Options:
    --api-url         Base URL for the API (example: http://localhost:8080/api/sermons)
    --dry-run         Preview changes without making API calls
    --resume          Resume from previous run (skip already processed messages)
    --folder          Process only a single folder (e.g., '2020-01-05-Recording' or full path)
    --use-cached-api  Use cached API data instead of fetching from server (faster for testing)
    --force-update    Update all messages even if they already have summaries/tags (overwrites existing data)
"""

import os
import json
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory
load_dotenv(Path(__file__).parent / ".env")

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class RateLimitException(Exception):
    """Raised when API returns 429 (Too Many Requests) status code."""
    pass

# ============================================================================
# CONFIGURATION
# ============================================================================

# API_BASE_URL will be set from command-line argument or environment variable
API_BASE_URL = None  # Set in main() from --api-url flag or API_BASE_URL env var

BATCH_OUTPUTS_DIR = Path(__file__).parent.parent / "batch_outputs"  # Root level batch_outputs directory
API_CONTENT_DIR = Path(__file__).parent / "api_content"
MODIFIED_MESSAGES_DIR = Path(__file__).parent / "modified_messages"
PROGRESS_FILE = Path(__file__).parent / "update_progress.json"
LOG_FILE = Path(__file__).parent / "update_sermon_summaries.log"

# API request settings
REQUEST_TIMEOUT = 30  # seconds
RETRY_ATTEMPTS = 3
BACKOFF_FACTOR = 1  # seconds between retries
DELAY_BETWEEN_REQUESTS = 5 # seconds

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging to both file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# HTTP SESSION SETUP
# ============================================================================

def create_http_session() -> requests.Session:
    """Create an HTTP session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=RETRY_ATTEMPTS,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "PUT"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# ============================================================================
# DIRECTORY SETUP
# ============================================================================

def setup_directories():
    """Create necessary directories if they don't exist."""
    API_CONTENT_DIR.mkdir(exist_ok=True)
    MODIFIED_MESSAGES_DIR.mkdir(exist_ok=True)
    logger.info(f"Directories created/verified: {API_CONTENT_DIR}, {MODIFIED_MESSAGES_DIR}")

# ============================================================================
# PROGRESS TRACKING
# ============================================================================

def load_progress() -> Dict:
    """Load progress from previous run."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed_message_ids": [], "failed_message_ids": []}

def save_progress(progress: Dict):
    """Save current progress."""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)

# ============================================================================
# API FUNCTIONS
# ============================================================================

def load_cached_sermon_data() -> Tuple[List[Dict], Dict[str, Dict]]:
    """
    Load sermon data from cached files instead of fetching from API.

    Returns:
        Tuple of (series_summaries, all_messages_by_id)

    Raises:
        FileNotFoundError: If cache files don't exist
        json.JSONDecodeError: If cache files are invalid
    """
    summaries_file = API_CONTENT_DIR / "all_series_summaries.json"
    all_series_file = API_CONTENT_DIR / "all_sermons.json"

    # Check if cache files exist
    if not summaries_file.exists():
        raise FileNotFoundError(f"Cache file not found: {summaries_file}")
    if not all_series_file.exists():
        raise FileNotFoundError(f"Cache file not found: {all_series_file}")

    logger.info("Loading sermon data from cache...")

    # Load series summaries
    with open(summaries_file, 'r', encoding='utf-8') as f:
        series_summaries = json.load(f)
    logger.info(f"Loaded {len(series_summaries)} sermon series from cache")

    # Load all series data
    with open(all_series_file, 'r', encoding='utf-8') as f:
        all_series_data = json.load(f)

    # Reconstruct messages_by_id dictionary
    all_messages_by_id = {}
    for series_data in all_series_data:
        series_id = series_data.get("Id")
        series_name = series_data.get("Name")
        messages = series_data.get("Messages", [])

        for message in messages:
            message_id = message.get("MessageId")
            if message_id:
                # Store series info with the message for context
                message["_SeriesId"] = series_id
                message["_SeriesName"] = series_name
                all_messages_by_id[message_id] = message

    logger.info(f"Loaded {len(all_messages_by_id)} messages from cache")

    return series_summaries, all_messages_by_id


def fetch_all_sermon_data(session: requests.Session) -> Tuple[List[Dict], Dict[str, Dict]]:
    """
    Fetch all sermon series and their messages from the API.
    
    Returns:
        Tuple of (series_summaries, all_messages_by_id)
    """
    logger.info("Fetching all sermon series summaries...")
    
    try:
        response = session.get(f"{API_BASE_URL}/", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        series_summaries = response.json().get("Summaries", [])
        logger.info(f"Found {len(series_summaries)} sermon series")
        
        # Save the summaries
        summaries_file = API_CONTENT_DIR / "all_series_summaries.json"
        with open(summaries_file, 'w', encoding='utf-8') as f:
            json.dump(series_summaries, f, indent=2)
        logger.info(f"Saved series summaries to {summaries_file}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch series summaries: {e}")
        raise
    
    # Fetch detailed data for each series
    all_series_data = []
    all_messages_by_id = {}
    
    for idx, series_summary in enumerate(series_summaries, 1):
        series_id = series_summary["Id"]
        logger.info(f"Fetching series {idx}/{len(series_summaries)}: {series_summary['Title']} (ID: {series_id})")
        
        try:
            response = session.get(f"{API_BASE_URL}/series/{series_id}", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            series_data = response.json()
            all_series_data.append(series_data)
            
            # Extract messages and index by MessageId
            messages = series_data.get("Messages", [])
            for message in messages:
                message_id = message.get("MessageId")
                if message_id:
                    # Store series info with the message for context
                    message["_SeriesId"] = series_id
                    message["_SeriesName"] = series_data.get("Name")
                    all_messages_by_id[message_id] = message
            
            logger.info(f"  Found {len(messages)} messages in this series")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch series {series_id}: {e}")
            continue
    
    # Save all series data
    all_series_file = API_CONTENT_DIR / "all_sermons.json"
    with open(all_series_file, 'w', encoding='utf-8') as f:
        json.dump(all_series_data, f, indent=2)
    logger.info(f"Saved all series data to {all_series_file}")
    logger.info(f"Total messages found: {len(all_messages_by_id)}")
    
    return series_summaries, all_messages_by_id

# ============================================================================
# SUMMARY PARSING
# ============================================================================

def parse_date_from_folder_name(folder_name: str) -> Optional[str]:
    """
    Parse date from folder name and normalize to YYYY-MM-DD format.
    Handles various formats like:
    - 2020-04-12-Recording
    - 2020-4-12-Recording
    - 2020-4-5-Recording

    Args:
        folder_name: Folder name (e.g., "2020-4-12-Recording")

    Returns:
        Normalized date string in YYYY-MM-DD format, or None if invalid
    """
    # Remove "-Recording" suffix if present
    date_part = folder_name.replace("-Recording", "")

    # Split by dash to get year, month, day
    parts = date_part.split("-")

    if len(parts) != 3:
        return None

    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])

        # Validate ranges
        if not (1900 <= year <= 2100):
            return None
        if not (1 <= month <= 12):
            return None
        if not (1 <= day <= 31):
            return None

        # Create a datetime object to validate the date is real
        date_obj = datetime(year, month, day)

        # Return normalized format
        return date_obj.strftime("%Y-%m-%d")

    except (ValueError, IndexError):
        return None

def parse_summary_folders(single_folder: Optional[str] = None) -> Dict[str, Dict]:
    """
    Parse all summary folders and extract date and summary data.

    Args:
        single_folder: Optional path to a single folder to process (e.g., "2020-01-05-Recording")

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to summary data
    """
    summaries_by_date = {}

    if single_folder:
        # Process only the specified folder
        folder_path = Path(single_folder)
        if not folder_path.is_absolute():
            # If relative path, assume it's relative to BATCH_OUTPUTS_DIR
            folder_path = BATCH_OUTPUTS_DIR / single_folder

        logger.info(f"Processing single folder: {folder_path}")

        if not folder_path.exists():
            logger.error(f"Folder not found: {folder_path}")
            return summaries_by_date

        if not folder_path.is_dir():
            logger.error(f"Path is not a directory: {folder_path}")
            return summaries_by_date

        folders_to_process = [folder_path]
    else:
        # Process all folders in BATCH_OUTPUTS_DIR
        logger.info(f"Parsing summary folders in {BATCH_OUTPUTS_DIR}...")
        folders_to_process = [f for f in BATCH_OUTPUTS_DIR.iterdir() if f.is_dir()]

    for folder in folders_to_process:
        if not folder.name.endswith("-Recording"):
            if single_folder:
                logger.warning(f"Folder name doesn't match expected format (YYYY-MM-DD-Recording): {folder.name}")
            continue

        # Extract and normalize date from folder name
        # Handles formats like: 2020-04-12-Recording, 2020-4-12-Recording, etc.
        date_str = parse_date_from_folder_name(folder.name)

        if not date_str:
            logger.warning(f"Could not parse date from folder name: {folder.name}")
            continue

        try:
            summary_file = folder / "summary.json"
            if not summary_file.exists():
                logger.warning(f"No summary.json found in {folder.name}")
                continue

            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)

            summaries_by_date[date_str] = {
                "folder_name": folder.name,
                "summary": summary_data.get("summary", ""),
                "tags": summary_data.get("tags", []),
                "word_count": summary_data.get("word_count"),
                "character_count": summary_data.get("character_count"),
                "model": summary_data.get("model"),
                "transcription_length": summary_data.get("transcription_length")
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Error parsing JSON in folder {folder.name}: {e}")
            continue

    logger.info(f"Parsed {len(summaries_by_date)} summary files")
    return summaries_by_date

# ============================================================================
# MATCHING AND UPDATING
# ============================================================================

def extract_audio_filename(audio_url: str) -> Optional[str]:
    """
    Extract the recording filename from an AudioUrl.

    Example:
        Input: "https://domain.com/2023/2023-10-16-Recording.mp3"
        Output: "2023-10-16-Recording"

    Args:
        audio_url: The full AudioUrl from the message

    Returns:
        The filename without extension, or None if invalid
    """
    if not audio_url:
        return None

    try:
        # Get the last part of the URL (filename with extension)
        filename_with_ext = audio_url.split("/")[-1]

        # Remove the .mp3 extension
        filename = filename_with_ext.replace(".mp3", "")

        return filename if filename else None
    except Exception:
        return None

def match_summaries_to_messages(
    summaries_by_date: Dict[str, Dict],
    messages_by_id: Dict[str, Dict],
    force_update: bool = False
) -> Tuple[List[Dict], List[str], List[str], List[str]]:
    """
    Match summaries to messages by date, with fallback to AudioUrl filename.

    Matching strategy:
    1. Primary: Match by date (handles most cases)
    2. Fallback: Match by AudioUrl filename (handles mislabeled dates)
    3. Skip messages that already have summaries/tags (unless force_update=True)

    Args:
        summaries_by_date: Dictionary of summaries indexed by date
        messages_by_id: Dictionary of messages indexed by MessageId
        force_update: If True, update all messages even if they have existing summaries/tags

    Returns:
        Tuple of (matched_updates, unmatched_summaries, unmatched_messages, skipped_messages)
    """
    logger.info("Matching summaries to messages...")

    matched_updates = []
    unmatched_summaries = []
    skipped_messages = []
    messages_by_date = {}
    messages_by_audio_filename = {}

    # Index messages by date AND by audio filename
    for message_id, message in messages_by_id.items():
        # Index by date
        date_str = message.get("Date", "")
        if date_str:
            try:
                # Handle both formats: "2025-03-02T00:00:00Z" and "2025-06-29"
                if "T" in date_str:
                    date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                date_key = date_obj.strftime("%Y-%m-%d")
                messages_by_date[date_key] = message
            except ValueError:
                logger.warning(f"Invalid date format for message {message_id}: {date_str}")

        # Index by audio filename
        audio_url = message.get("AudioUrl", "")
        if audio_url:
            audio_filename = extract_audio_filename(audio_url)
            if audio_filename:
                messages_by_audio_filename[audio_filename] = message

    # Match summaries to messages (try date first, then audio filename)
    for date_str, summary_data in summaries_by_date.items():
        folder_name = summary_data['folder_name']
        message = None
        match_method = None

        # Try matching by date first
        if date_str in messages_by_date:
            message = messages_by_date[date_str]
            match_method = "date"

        # Fallback: Try matching by audio filename
        elif folder_name in messages_by_audio_filename:
            message = messages_by_audio_filename[folder_name]
            match_method = "audio_filename"

        if message:
            # Check if message already has summary/tags (unless force_update is True)
            existing_summary = message.get("Summary")
            existing_tags = message.get("Tags", [])
            has_existing_data = (existing_summary and existing_summary.strip()) or (existing_tags and len(existing_tags) > 0)

            if has_existing_data and not force_update:
                # Skip this message - it already has data
                skipped_messages.append(f"{date_str} - {message.get('Title')}")
                logger.info(f"⊘ Skipped (already has data): {date_str} - {message.get('Title')} (use --force-update to overwrite)")
            else:
                # Add to matched updates
                matched_updates.append({
                    "message_id": message["MessageId"],
                    "date": date_str,
                    "series_name": message.get("_SeriesName"),
                    "title": message.get("Title"),
                    "summary": summary_data["summary"],
                    "tags": summary_data["tags"],
                    "original_message": message
                })

                if match_method == "date":
                    logger.info(f"✓ Matched by date: {date_str} - {message.get('Title')}")
                else:
                    logger.info(f"✓ Matched by audio filename: {folder_name} - {message.get('Title')} (date mismatch: folder={date_str}, message={message.get('Date', 'N/A')[:10]})")
        else:
            unmatched_summaries.append(date_str)
            logger.warning(f"✗ No message found for: {date_str} ({folder_name})")

    # Find messages without summaries
    matched_message_ids = {update["message_id"] for update in matched_updates}
    skipped_message_ids = set()

    # Extract message IDs from skipped messages (format: "YYYY-MM-DD - Title")
    for msg_id, msg in messages_by_id.items():
        msg_str = f"{msg.get('Date', 'N/A')[:10]} - {msg.get('Title')}"
        if msg_str in skipped_messages:
            skipped_message_ids.add(msg_id)

    unmatched_messages = [
        f"{msg.get('Date', 'N/A')[:10]} - {msg.get('Title')}"
        for msg_id, msg in messages_by_id.items()
        if msg_id not in matched_message_ids and msg_id not in skipped_message_ids
    ]

    logger.info(f"Matching complete: {len(matched_updates)} matched, "
                f"{len(skipped_messages)} skipped (already have data), "
                f"{len(unmatched_summaries)} unmatched summaries, "
                f"{len(unmatched_messages)} messages without summaries")

    return matched_updates, unmatched_summaries, unmatched_messages, skipped_messages

def create_updated_message(original_message: Dict, summary: str, tags: List[str]) -> Dict:
    """
    Create an updated message object with new summary and tags.
    Preserves all other existing properties.
    """
    # Create a copy of the original message
    updated_message = original_message.copy()

    # Remove internal tracking fields
    updated_message.pop("_SeriesId", None)
    updated_message.pop("_SeriesName", None)

    # Update summary and tags
    updated_message["Summary"] = summary
    updated_message["Tags"] = tags

    # Ensure Date is in the correct format (without time component if it's just a date)
    if "Date" in updated_message and "T" not in updated_message["Date"]:
        # Date is already in simple format, keep it
        pass

    return updated_message

def save_modified_messages(matched_updates: List[Dict]):
    """Save all modified messages to local JSON files."""
    logger.info(f"Saving {len(matched_updates)} modified messages to {MODIFIED_MESSAGES_DIR}...")

    for update in matched_updates:
        message_id = update["message_id"]
        updated_message = create_updated_message(
            update["original_message"],
            update["summary"],
            update["tags"]
        )

        # Save to file
        message_file = MODIFIED_MESSAGES_DIR / f"{message_id}.json"
        with open(message_file, 'w', encoding='utf-8') as f:
            json.dump({"Message": updated_message}, f, indent=2)

    logger.info(f"Saved {len(matched_updates)} modified messages")

# ============================================================================
# API UPDATE FUNCTIONS
# ============================================================================

def update_message_via_api(
    session: requests.Session,
    message_id: str,
    updated_message: Dict,
    dry_run: bool = False
) -> bool:
    """
    Update a single message via the API.

    Returns:
        True if successful, False otherwise

    Raises:
        RateLimitException: If API returns 429 (Too Many Requests)
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would update message {message_id}")
        return True

    try:
        url = f"{API_BASE_URL}/series/message/{message_id}"
        payload = {"Message": updated_message}

        # send request to api to update messages
        response = session.put(url, json=payload, timeout=REQUEST_TIMEOUT)

        # Check for rate limiting before raising for other status codes
        if response.status_code == 429:
            logger.error(f"✗ Rate limit exceeded (429) when updating message {message_id}")
            raise RateLimitException("API rate limit exceeded (429 Too Many Requests)")

        response.raise_for_status()

        logger.info(f"Updated message {message_id}")
        return True

    except RateLimitException:
        # Re-raise rate limit exceptions to be handled by caller
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to update message {message_id}: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"  Response: {e.response.text}")
        return False

def update_all_messages(
    session: requests.Session,
    matched_updates: List[Dict],
    dry_run: bool = False,
    resume: bool = False
) -> Tuple[int, int, List[str]]:
    """
    Update all matched messages via the API.

    Returns:
        Tuple of (successful_count, failed_count, failed_message_ids)
    """
    progress = load_progress() if resume else {"processed_message_ids": [], "failed_message_ids": []}

    successful_count = len(progress["processed_message_ids"])
    failed_count = len(progress["failed_message_ids"])
    failed_message_ids = progress["failed_message_ids"].copy()

    logger.info(f"Starting API updates (dry_run={dry_run}, resume={resume})...")
    if resume:
        logger.info(f"Resuming: {successful_count} already processed, {failed_count} previously failed")

    try:
        for idx, update in enumerate(matched_updates, 1):
            message_id = update["message_id"]

            # Skip if already processed
            if resume and message_id in progress["processed_message_ids"]:
                logger.info(f"[{idx}/{len(matched_updates)}] Skipping already processed: {message_id}")
                continue

            logger.info(f"[{idx}/{len(matched_updates)}] Updating: {update['date']} - {update['title']}")

            updated_message = create_updated_message(
                update["original_message"],
                update["summary"],
                update["tags"]
            )

            success = update_message_via_api(session, message_id, updated_message, dry_run)

            if success:
                successful_count += 1
                if not dry_run:
                    progress["processed_message_ids"].append(message_id)
                    # Remove from failed list if it was there
                    if message_id in progress["failed_message_ids"]:
                        progress["failed_message_ids"].remove(message_id)
            else:
                failed_count += 1
                failed_message_ids.append(message_id)
                if not dry_run:
                    progress["failed_message_ids"].append(message_id)

            # Save progress after each update
            if not dry_run:
                save_progress(progress)

            # Delay between requests
            if not dry_run:
                time.sleep(DELAY_BETWEEN_REQUESTS)

    except RateLimitException as e:
        # Rate limit hit - save progress and exit gracefully
        logger.warning("\n" + "=" * 80)
        logger.warning("RATE LIMIT EXCEEDED")
        logger.warning("=" * 80)
        logger.warning(f"API rate limit hit after processing {successful_count} messages")
        logger.warning("Progress has been saved. Use --resume to continue from where you left off.")
        logger.warning("Consider increasing DELAY_BETWEEN_REQUESTS in the script configuration.")
        logger.warning("=" * 80)

        # Save final progress
        if not dry_run:
            save_progress(progress)

        # Re-raise to be handled by main
        raise

    return successful_count, failed_count, failed_message_ids

# ============================================================================
# REPORTING
# ============================================================================

def generate_summary_report(
    matched_updates: List[Dict],
    unmatched_summaries: List[str],
    unmatched_messages: List[str],
    skipped_messages: List[str],
    successful_count: int,
    failed_count: int,
    failed_message_ids: List[str],
    dry_run: bool
):
    """Generate and display a summary report."""
    report = [
        "\n" + "=" * 80,
        "SUMMARY REPORT",
        "=" * 80,
        f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}",
        "",
        "MATCHING RESULTS:",
        f"  Total summaries processed: {len(matched_updates) + len(skipped_messages) + len(unmatched_summaries)}",
        f"  Successful matches: {len(matched_updates)}",
        f"  Skipped (already have data): {len(skipped_messages)}",
        f"  Unmatched summaries: {len(unmatched_summaries)}",
        f"  Messages without summaries: {len(unmatched_messages)}",
        "",
        "API UPDATE RESULTS:",
        f"  Successful updates: {successful_count}",
        f"  Failed updates: {failed_count}",
        ""
    ]

    if skipped_messages:
        report.append("SKIPPED MESSAGES (already have summaries/tags - use --force-update to overwrite):")
        for msg in sorted(skipped_messages)[:10]:  # Show first 10
            report.append(f"  - {msg}")
        if len(skipped_messages) > 10:
            report.append(f"  ... and {len(skipped_messages) - 10} more")
        report.append("")

    if unmatched_summaries:
        report.append("UNMATCHED SUMMARIES (no corresponding message found):")
        for date in sorted(unmatched_summaries):
            report.append(f"  - {date}")
        report.append("")

    if failed_message_ids:
        report.append("FAILED UPDATES:")
        for msg_id in failed_message_ids:
            report.append(f"  - {msg_id}")
        report.append("")

    if unmatched_messages:
        report.append(f"MESSAGES WITHOUT SUMMARIES ({len(unmatched_messages)}):")
        for msg in sorted(unmatched_messages)[:10]:  # Show first 10
            report.append(f"  - {msg}")
        if len(unmatched_messages) > 10:
            report.append(f"  ... and {len(unmatched_messages) - 10} more")
        report.append("")

    report.append("=" * 80)

    report_text = "\n".join(report)
    logger.info(report_text)

    # Save report to file
    report_file = BATCH_OUTPUTS_DIR / f"update_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    logger.info(f"Report saved to {report_file}")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Update sermon messages with AI-generated summaries and tags"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making API calls"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run (skip already processed messages)"
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Process only a single folder (e.g., '2020-01-05-Recording' or full path)"
    )
    parser.add_argument(
        "--use-cached-api",
        action="store_true",
        help="Use cached API data instead of fetching from server (faster for testing)"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="Base URL for the API (example: http://localhost:8080/api/sermons)"
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Update all messages even if they already have summaries/tags (overwrites existing data)"
    )
    args = parser.parse_args()

    # Set API_BASE_URL from command-line argument or .env file
    global API_BASE_URL
    if args.api_url:
        API_BASE_URL = args.api_url
    else:
        API_BASE_URL = os.getenv("API_BASE_URL")

    if not API_BASE_URL:
        logger.error("ERROR: API_BASE_URL not found!")
        logger.error("Please either:")
        logger.error("  1. Set API_BASE_URL in Update_Messages/.env file")
        logger.error("  2. Use --api-url flag: python update_sermon_summaries.py --api-url http://your-api-url/api/sermons")
        return

    logger.info("=" * 80)
    logger.info("SERMON SUMMARY UPDATE AUTOMATION")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    logger.info(f"Resume: {args.resume}")
    logger.info(f"Force update: {args.force_update}")
    logger.info(f"Use cached API data: {args.use_cached_api}")
    logger.info(f"API Base URL: {API_BASE_URL}")
    logger.info(f"Batch outputs directory: {BATCH_OUTPUTS_DIR}")
    if args.folder:
        logger.info(f"Single folder mode: {args.folder}")
    logger.info("")

    try:
        # Setup
        setup_directories()
        session = create_http_session()

        # Step 1: Fetch all sermon data from API (or load from cache)
        logger.info("\n" + "-" * 80)
        if args.use_cached_api:
            logger.info("STEP 1: Loading sermon data from cache")
            logger.info("-" * 80)
            try:
                series_summaries, messages_by_id = load_cached_sermon_data()
            except FileNotFoundError as e:
                logger.error(f"Cache files not found: {e}")
                logger.error("Please run without --use-cached-api first to fetch and cache the data")
                return 1
            except json.JSONDecodeError as e:
                logger.error(f"Invalid cache file: {e}")
                logger.error("Please delete the cache files and run without --use-cached-api to re-fetch")
                return 1
        else:
            logger.info("STEP 1: Fetching sermon data from API")
            logger.info("-" * 80)
            series_summaries, messages_by_id = fetch_all_sermon_data(session)

        # Step 2: Parse summary folders
        logger.info("\n" + "-" * 80)
        logger.info("STEP 2: Parsing summary folders")
        logger.info("-" * 80)
        summaries_by_date = parse_summary_folders(single_folder=args.folder)

        # Step 3: Match summaries to messages
        logger.info("\n" + "-" * 80)
        logger.info("STEP 3: Matching summaries to messages")
        logger.info("-" * 80)
        matched_updates, unmatched_summaries, unmatched_messages, skipped_messages = match_summaries_to_messages(
            summaries_by_date,
            messages_by_id,
            force_update=args.force_update
        )

        # Step 4: Save modified messages locally
        logger.info("\n" + "-" * 80)
        logger.info("STEP 4: Saving modified messages locally")
        logger.info("-" * 80)
        save_modified_messages(matched_updates)

        # Step 5: Update messages via API
        logger.info("\n" + "-" * 80)
        logger.info("STEP 5: Updating messages via API")
        logger.info("-" * 80)
        successful_count, failed_count, failed_message_ids = update_all_messages(
            session,
            matched_updates,
            dry_run=args.dry_run,
            resume=args.resume
        )

        # Step 6: Generate summary report
        logger.info("\n" + "-" * 80)
        logger.info("STEP 6: Generating summary report")
        logger.info("-" * 80)
        generate_summary_report(
            matched_updates,
            unmatched_summaries,
            unmatched_messages,
            skipped_messages,
            successful_count,
            failed_count,
            failed_message_ids,
            args.dry_run
        )

        logger.info("\n✓ Script completed successfully!")

    except RateLimitException:
        logger.warning("\n\n✗ Script stopped due to API rate limiting")
        logger.info("Progress has been saved. Use --resume to continue from where you left off.")
        logger.info("Consider increasing DELAY_BETWEEN_REQUESTS in the script configuration.")
        return 1
    except KeyboardInterrupt:
        logger.warning("\n\n✗ Script interrupted by user")
        logger.info("Progress has been saved. Use --resume to continue.")
        return 1
    except Exception as e:
        logger.error(f"\n\n✗ Script failed with error: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    exit(main())

