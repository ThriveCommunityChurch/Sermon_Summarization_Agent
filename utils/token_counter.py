"""
Token counting utility for tracking OpenAI API usage.
"""

import tiktoken
from typing import Dict, Any

# Initialize the encoding for GPT-4o-mini
try:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
except KeyError:
    # Fallback to cl100k_base if model not found
    encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string.
    
    Args:
        text: The text to count tokens for
        
    Returns:
        Number of tokens
    """
    if not text:
        return 0
    
    try:
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        print(f"Warning: Failed to count tokens: {e}")
        return 0


def count_messages_tokens(messages: list) -> int:
    """
    Count tokens in a list of messages (for API calls).
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        
    Returns:
        Total number of tokens
    """
    total_tokens = 0
    
    for message in messages:
        if isinstance(message, dict):
            # Add tokens for role and content
            if 'role' in message:
                total_tokens += count_tokens(message['role'])
            if 'content' in message:
                total_tokens += count_tokens(message['content'])
            # Add overhead for message structure (typically 4 tokens per message)
            total_tokens += 4
        elif hasattr(message, 'content'):
            # Handle LangChain message objects
            total_tokens += count_tokens(str(message.content))
            total_tokens += 4
    
    return total_tokens


class TokenTracker:
    """
    Tracks token usage across different operations.
    """

    def __init__(self):
        self.transcription_tokens = 0
        self.summarization_input_tokens = 0
        self.summarization_output_tokens = 0
        self.tagging_input_tokens = 0
        self.tagging_output_tokens = 0

    def add_transcription_tokens(self, count: int):
        """Add tokens used for transcription."""
        self.transcription_tokens += count

    def add_summarization_tokens(self, input_count: int, output_count: int):
        """Add tokens used for summarization (input and output separately)."""
        self.summarization_input_tokens += input_count
        self.summarization_output_tokens += output_count

    def add_tagging_tokens(self, input_count: int, output_count: int):
        """Add tokens used for tagging (input and output separately)."""
        self.tagging_input_tokens += input_count
        self.tagging_output_tokens += output_count

    def get_total_tokens(self) -> int:
        """Get total tokens used."""
        return (self.transcription_tokens +
                self.summarization_input_tokens + self.summarization_output_tokens +
                self.tagging_input_tokens + self.tagging_output_tokens)

    def get_breakdown(self) -> Dict[str, int]:
        """Get token usage breakdown."""
        return {
            "transcription": self.transcription_tokens,
            "summarization": self.summarization_input_tokens + self.summarization_output_tokens,
            "summarization_input": self.summarization_input_tokens,
            "summarization_output": self.summarization_output_tokens,
            "tagging": self.tagging_input_tokens + self.tagging_output_tokens,
            "tagging_input": self.tagging_input_tokens,
            "tagging_output": self.tagging_output_tokens,
            "total": self.get_total_tokens()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert tracker to dictionary for JSON serialization."""
        return {
            "tokens": {
                "transcription": self.transcription_tokens,
                "summarization": self.summarization_input_tokens + self.summarization_output_tokens,
                "summarization_input": self.summarization_input_tokens,
                "summarization_output": self.summarization_output_tokens,
                "tagging": self.tagging_input_tokens + self.tagging_output_tokens,
                "tagging_input": self.tagging_input_tokens,
                "tagging_output": self.tagging_output_tokens,
                "total": self.get_total_tokens()
            }
        }


# Global token tracker instance
_global_tracker = TokenTracker()


def get_global_tracker() -> TokenTracker:
    """Get the global token tracker instance."""
    return _global_tracker


def reset_global_tracker():
    """Reset the global token tracker."""
    global _global_tracker
    _global_tracker = TokenTracker()

