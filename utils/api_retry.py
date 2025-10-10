"""
Utility functions for handling API retries with exponential backoff.

This module provides retry logic for OpenAI API calls to handle:
- Connection errors
- Rate limiting
- Temporary network issues
- Timeouts
"""

import time
import functools
from typing import Callable, TypeVar, Any
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError

T = TypeVar('T')


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> Callable:
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        jitter: Whether to add random jitter to delay (default: True)
    
    Returns:
        Decorated function that retries on API errors
    
    Example:
        @retry_with_exponential_backoff(max_retries=3)
        def call_openai_api():
            return llm.invoke(messages)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except (APIConnectionError, APITimeoutError) as e:
                    last_exception = e
                    error_type = "Connection" if isinstance(e, APIConnectionError) else "Timeout"
                    
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        actual_delay = min(delay, max_delay)
                        
                        # Add jitter if enabled (random variation ±25%)
                        if jitter:
                            import random
                            actual_delay *= (0.75 + 0.5 * random.random())
                        
                        print(f"   {error_type} error on attempt {attempt + 1}/{max_retries + 1}")
                        print(f"   Retrying in {actual_delay:.1f} seconds...")
                        time.sleep(actual_delay)
                        
                        # Increase delay for next attempt
                        delay *= exponential_base
                    else:
                        print(f"   {error_type} error on final attempt {attempt + 1}/{max_retries + 1}")
                        print(f"   All retries exhausted. Giving up.")
                
                except RateLimitError as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # For rate limits, use longer delays
                        actual_delay = min(delay * 2, max_delay)
                        
                        print(f"   Rate limit exceeded on attempt {attempt + 1}/{max_retries + 1}")
                        print(f"   Waiting {actual_delay:.1f} seconds before retry...")
                        time.sleep(actual_delay)
                        
                        delay *= exponential_base
                    else:
                        print(f"   Rate limit exceeded on final attempt {attempt + 1}/{max_retries + 1}")
                        print(f"   All retries exhausted. Giving up.")
                
                except APIError as e:
                    # For other API errors, don't retry (might be auth, invalid request, etc.)
                    print(f"   API error (non-retryable): {e}")
                    raise
                
                except Exception as e:
                    # For unexpected errors, don't retry
                    print(f"   Unexpected error (non-retryable): {e}")
                    raise
            
            # If we get here, all retries failed
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("All retries failed with unknown error")
        
        return wrapper
    return decorator


def call_llm_with_retry(llm: Any, messages: list, max_retries: int = 3) -> Any:
    """
    Call an LLM with automatic retry logic.
    
    This is a convenience function that wraps LLM calls with retry logic.
    
    Args:
        llm: The LangChain LLM instance
        messages: List of messages to send to the LLM
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        LLM response
    
    Example:
        llm = ChatOpenAI(model="gpt-4o-mini")
        response = call_llm_with_retry(llm, [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello!"}
        ])
    """
    @retry_with_exponential_backoff(max_retries=max_retries)
    def _call():
        return llm.invoke(messages)
    
    return _call()

