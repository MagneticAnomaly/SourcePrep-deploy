from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VendorCandidate":
        return cls(
            path=d["path"],
            rel_path=d["rel_path"],
            size_bytes=int(d["size_bytes"]),
            file_count=int(d["file_count"]),
            reason=d["reason"],
            tier=d["tier"],
            in_gitignore=bool(d["in_gitignore"]),
            is_git_repo=bool(d["is_git_repo"]),
        )


@dataclass(frozen=True)
class VendorScanResult:
    auto_excluded: list[str]
    proposed: list[VendorCandidate]
    gitignore_gaps: list[VendorCandidate]
    scanned_at: float
    status: Literal["pending", "complete", "failed"]
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VendorScanResult":
        return cls(
            auto_excluded=list(d.get("auto_excluded", [])),
            proposed=[VendorCandidate.from_dict(c) for c in d.get("proposed", [])],
            gitignore_gaps=[VendorCandidate.from_dict(c) for c in d.get("gitignore_gaps", [])],
            scanned_at=float(d.get("scanned_at", 0.0)),
            status=d.get("status", "pending"),
            error=d.get("error"),
        )
