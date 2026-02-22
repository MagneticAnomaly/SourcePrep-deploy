"""Data serialization and deserialization utilities."""

import json
import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional


class JSONSerializer:
    """Serialize and deserialize data to/from JSON with custom type handling."""

    @staticmethod
    def serialize(data: Any, pretty: bool = False) -> str:
        indent = 2 if pretty else None
        return json.dumps(data, default=_json_default, indent=indent)

    @staticmethod
    def deserialize(text: str) -> Any:
        return json.loads(text)


class CSVSerializer:
    """Serialize and deserialize tabular data to/from CSV format."""

    @staticmethod
    def serialize(rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> str:
        if not rows:
            return ""
        if fieldnames is None:
            fieldnames = list(rows[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    @staticmethod
    def deserialize(text: str) -> List[Dict[str, str]]:
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)


def _json_default(obj: Any) -> Any:
    """Custom JSON serializer for types not supported by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
