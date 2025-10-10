"""
Tagging node for applying semantic tags to sermon summaries.

This module provides functionality to analyze sermon summaries and apply
relevant tags from a predefined list in tags.txt.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from classes.agent_state import AgentState
from utils.tag_parser import load_tags, format_tags_for_prompt
from utils.api_retry import call_llm_with_retry


def _load_summary_json() -> Dict[str, Any]:
    """
    Load the summary.json file.
    
    Returns:
        Dictionary containing summary metadata
        
    Raises:
        FileNotFoundError: If summary.json doesn't exist
        ValueError: If summary.json is empty or invalid
    """
    json_path = Path("summary.json")
    
    if not json_path.exists():
        raise FileNotFoundError(
            "No summary.json found. Run summarize_sermon first to generate summary.json"
        )
    
    content = json_path.read_text(encoding="utf-8").strip()
    
    if not content:
        raise ValueError("summary.json file is empty.")
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in summary.json: {e}")
    
    if "summary" not in data:
        raise ValueError("summary.json does not contain a 'summary' field.")
    
    return data


def _load_transcription() -> str:
    """
    Load transcription text for comprehensive tag analysis.

    Returns:
        Transcription text, or empty string if not available
    """
    txt_path = Path("transcription.txt")

    if not txt_path.exists():
        return ""

    return txt_path.read_text(encoding="utf-8").strip()


def _classify_with_llm(summary_text: str, available_tags: List[str], transcription: str) -> List[str]:
    """
    Use GPT-4o-mini to classify the sermon and select relevant tags.

    Uses a hybrid approach: analyzes both the summary (for main themes) and
    transcript excerpt (for comprehensive coverage) to ensure accurate tag selection.

    Args:
        summary_text: The sermon summary text (distilled main themes)
        available_tags: List of available tag names
        transcription: Full transcription for comprehensive context

    Returns:
        List of selected tag names
    """
    # Initialize GPT-4o-mini for classification
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    # Format tags for the prompt
    tags_str = format_tags_for_prompt(available_tags)

    # Create the system prompt with hybrid approach instructions
    system_prompt = (
        "You are an expert at analyzing sermon content and applying relevant topical tags. "
        "Your task is to analyze BOTH the sermon summary and transcript excerpt to select "
        "the most relevant tags from a provided list.\n\n"
        "Analysis Strategy:\n"
        "- Use the SUMMARY to identify the main themes and primary focus of the sermon\n"
        "- Use the TRANSCRIPT EXCERPT to identify secondary themes and ensure comprehensive coverage\n"
        "- Having both sources provides better context for accurate tag selection\n"
        "- The transcript may reveal important themes that didn't make it into the summary\n\n"
        "Selection Guidelines:\n"
        "- Select no more than 5 tags that best represent the sermon's themes and topics\n"
        "- Prioritize main themes from the summary, but include important secondary themes from the transcript\n"
        "- Focus on the primary themes, not every minor topic mentioned\n"
        "- Only select tags from the provided list - do not create new tags\n"
        "- Consider both theological themes and practical life applications\n"
        "- If the sermon is part of a book study, include the relevant book tag\n"
        "- Return ONLY the tag names as a JSON array, nothing else\n"
        "- Tag names are case-sensitive and must match exactly\n\n"
        f"Available tags:\n{tags_str}\n\n"
        "Respond with a JSON array of selected tags, for example:\n"
        '["Faith", "Prayer", "Suffering", "Hope"]'
    )

    # Limit transcription to ~15000 characters for comprehensive context while managing tokens
    transcript_excerpt = transcription[:15000] if transcription else ""
    if len(transcription) > 15000:
        transcript_excerpt += "..."

    # Build the user prompt with both sources clearly labeled
    user_prompt = (
        "=== SERMON SUMMARY (Main Themes) ===\n"
        f"{summary_text}\n\n"
        "=== TRANSCRIPT EXCERPT (Comprehensive Context) ===\n"
        f"{transcript_excerpt}\n\n"
        "=== INSTRUCTIONS ===\n"
        "Please analyze BOTH the summary and transcript excerpt above, then return the most "
        "relevant tags as a JSON array. Use the summary to identify main themes and the "
        "transcript to ensure comprehensive coverage of all important topics discussed."
    )
    
    # Generate the classification with retry logic
    print("Analyzing sermon content (summary + transcript) and applying tags with GPT-4o-mini...")
    response = call_llm_with_retry(
        llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_retries=3
    )
    
    # Parse the response
    response_text = response.content.strip()
    
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        # Remove ```json or ``` at start and ``` at end
        lines = response_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()
    
    try:
        selected_tags = json.loads(response_text)
        
        if not isinstance(selected_tags, list):
            print(f"Warning: LLM returned non-list response: {response_text}")
            return []
        
        # Validate that all tags are in the available list
        valid_tags = [tag for tag in selected_tags if tag in available_tags]
        
        if len(valid_tags) != len(selected_tags):
            invalid_tags = [tag for tag in selected_tags if tag not in available_tags]
            print(f"Warning: LLM returned invalid tags (ignored): {invalid_tags}")
        
        return valid_tags
        
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse LLM response as JSON: {response_text}")
        print(f"Error: {e}")
        return []


@tool
def tag_sermon(state: AgentState):
    """
    Apply semantic tags to the sermon summary based on content analysis.

    This tool uses a hybrid approach: it analyzes BOTH the sermon summary (for main themes)
    and the transcript excerpt (for comprehensive coverage) to determine which tags from the
    predefined list in config/tags_config.py are most relevant. It then updates summary.json
    to include a "tags" array field.

    Reads:
    - config/tags_config.py (list of available tags)
    - summary.json (summary with metadata - main themes)
    - transcription.txt (full transcript - comprehensive context)

    Writes:
    - summary.json (updated with tags array)

    Returns a JSON string with keys: {"tags", "tags_count", "summary_path"}.
    """
    # Load available tags from configuration
    try:
        available_tags = load_tags()
        print(f"Loaded {len(available_tags)} available tags from configuration")
    except Exception as e:
        error_msg = f"Failed to load tags: {e}"
        print(f"Error: {error_msg}")
        return json.dumps({"error": error_msg, "tags": [], "tags_count": 0})

    # Load the summary (main themes)
    try:
        summary_data = _load_summary_json()
        summary_text = summary_data["summary"]
        print(f"Loaded summary ({len(summary_text)} characters)")
    except Exception as e:
        error_msg = f"Failed to load summary: {e}"
        print(f"Error: {error_msg}")
        return json.dumps({"error": error_msg, "tags": [], "tags_count": 0})

    # Load transcription (comprehensive context)
    transcription = _load_transcription()
    if transcription:
        print(f"Loaded transcript ({len(transcription)} characters) for comprehensive analysis")
    else:
        print("Warning: No transcript found. Using summary only for tag classification.")
        transcription = ""  # Ensure it's an empty string, not None

    # Classify and select tags using LLM with hybrid approach
    selected_tags = _classify_with_llm(summary_text, available_tags, transcription)
    
    if not selected_tags:
        print("Warning: No tags were selected for this sermon")
    
    # Update summary.json with tags
    summary_data["tags"] = selected_tags
    
    output_json = Path("summary.json")
    output_json.write_text(
        json.dumps(summary_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"Applied {len(selected_tags)} tags: {', '.join(selected_tags)}")
    print(f"Updated summary.json with tags")
    
    # Return result
    result = {
        "tags": selected_tags,
        "tags_count": len(selected_tags),
        "summary_path": str(output_json.resolve()),
    }
    
    return json.dumps(result)

