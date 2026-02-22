"""Input validation and sanitization utilities."""

import re
from typing import Any, Optional


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_email(email: str) -> str:
    """Validate and normalize an email address."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError("email", f"Invalid email format: {email}")
    return email.lower().strip()


def validate_password(password: str, min_length: int = 8) -> bool:
    """Check password meets complexity requirements."""
    if len(password) < min_length:
        raise ValidationError("password", f"Must be at least {min_length} characters")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("password", "Must contain at least one uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValidationError("password", "Must contain at least one digit")
    return True


def sanitize_html(text: str) -> str:
    """Strip HTML tags from input text to prevent XSS."""
    return re.sub(r"<[^>]+>", "", text)


def validate_pagination(page: int, per_page: int, max_per_page: int = 100) -> tuple:
    """Validate and clamp pagination parameters."""
    page = max(1, page)
    per_page = max(1, min(per_page, max_per_page))
    offset = (page - 1) * per_page
    return page, per_page, offset
