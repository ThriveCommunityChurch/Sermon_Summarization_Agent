"""
Tag parser utility for loading and caching sermon tags.

This module provides functionality to load tags from the Python configuration
and cache them for efficient reuse during batch processing.
"""

from typing import List, Optional
from config.tags_config import get_all_tags


# Global cache for tags to avoid repeated function calls
_TAGS_CACHE: Optional[List[str]] = None


def load_tags() -> List[str]:
    """
    Load all available tags from the configuration.

    Results are cached in memory to avoid repeated calls during batch processing.

    Returns:
        List of tag names (e.g., ["Marriage", "Family", "Prayer", ...])
    """
    global _TAGS_CACHE

    # Return cached tags if available
    if _TAGS_CACHE is not None:
        return _TAGS_CACHE

    # Load tags from configuration
    tags = get_all_tags()

    # Cache the tags for future use
    _TAGS_CACHE = tags

    return tags


def clear_tags_cache():
    """
    Clear the cached tags.
    
    This is useful for testing or if the tags file is updated during runtime.
    """
    global _TAGS_CACHE
    _TAGS_CACHE = None


def get_tags_count() -> int:
    """
    Get the number of available tags.
    
    Returns:
        Number of tags available, or 0 if tags haven't been loaded yet
    """
    if _TAGS_CACHE is None:
        return 0
    return len(_TAGS_CACHE)


def format_tags_for_prompt(tags: List[str]) -> str:
    """
    Format tags as a readable string for LLM prompts.
    
    Args:
        tags: List of tag names
        
    Returns:
        Formatted string with tags separated by commas
    """
    return ", ".join(tags)

