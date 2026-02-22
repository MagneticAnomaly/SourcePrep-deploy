"""Utility functions — slugify, date parsing, retry decorator."""

import re
import time
import functools
from datetime import datetime
from typing import Callable, TypeVar, Any

F = TypeVar("F", bound=Callable[..., Any])


def slugify(text: str) -> str:
    """Convert a text string into a URL-friendly slug.

    Lowercases, replaces spaces and special characters with hyphens,
    and strips leading/trailing hyphens.

    Examples:
        slugify("Hello World!") -> "hello-world"
        slugify("My Cool  Project") -> "my-cool-project"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def parse_date(date_string: str) -> datetime:
    """Parse a date string into a datetime object.

    Supports multiple common formats:
        - ISO 8601: "2024-01-15T10:30:00"
        - Date only: "2024-01-15"
        - US format: "01/15/2024"
        - Human readable: "Jan 15, 2024"

    Raises ValueError if the string cannot be parsed.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse date string: {date_string!r}")


def retry_decorator(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """A decorator that retries a function on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        delay_seconds: Initial delay between retries in seconds.
        backoff_factor: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch and retry on.

    Usage:
        @retry_decorator(max_retries=3, delay_seconds=0.5)
        def flaky_api_call():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay_seconds

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff_factor

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate a string to a maximum length, adding a suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
