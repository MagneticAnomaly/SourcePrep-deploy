"""Cursor-based and offset pagination for API responses."""

from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar
import base64
import json

T = TypeVar("T")


@dataclass
class Page:
    """A page of results with pagination metadata."""
    items: List[Any]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

    @property
    def total_pages(self) -> int:
        return (self.total + self.per_page - 1) // self.per_page


def paginate_offset(items: List[Any], page: int = 1, per_page: int = 20) -> Page:
    """Apply offset-based pagination to a list."""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return Page(
        items=items[start:end],
        total=total,
        page=page,
        per_page=per_page,
        has_next=end < total,
        has_prev=page > 1,
    )


def encode_cursor(data: Dict[str, Any]) -> str:
    """Encode pagination cursor as base64 JSON."""
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def decode_cursor(cursor: str) -> Dict[str, Any]:
    """Decode a base64-encoded pagination cursor."""
    return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())


def paginate_cursor(
    items: List[Any],
    cursor: Optional[str] = None,
    limit: int = 20,
    id_field: str = "id",
) -> Dict[str, Any]:
    """Apply cursor-based pagination."""
    start_after = None
    if cursor:
        decoded = decode_cursor(cursor)
        start_after = decoded.get("after")

    filtered = items
    if start_after is not None:
        for i, item in enumerate(items):
            val = item.get(id_field) if isinstance(item, dict) else getattr(item, id_field, None)
            if val == start_after:
                filtered = items[i + 1:]
                break

    page_items = filtered[:limit]
    has_more = len(filtered) > limit

    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        last_id = last.get(id_field) if isinstance(last, dict) else getattr(last, id_field, None)
        next_cursor = encode_cursor({"after": last_id})

    return {"items": page_items, "next_cursor": next_cursor, "has_more": has_more}
