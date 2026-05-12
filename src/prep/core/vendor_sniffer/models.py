from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VendorCandidate:
    path: str
    rel_path: str
    size_bytes: int
    file_count: int
    reason: str
    tier: Literal["auto", "propose"]
    in_gitignore: bool
    is_git_repo: bool


@dataclass(frozen=True)
class VendorScanResult:
    auto_excluded: list[str]
    proposed: list[VendorCandidate]
    gitignore_gaps: list[VendorCandidate]
    scanned_at: float
    status: Literal["pending", "complete", "failed"]
    error: str | None
