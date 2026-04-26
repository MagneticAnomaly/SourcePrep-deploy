"""Per-swarm-execution event logger (Phase 119 — verbose swarm logs).

Writes one JSONL file per ``SwarmOrchestrator.execute()`` invocation to
``<data_dir>/logs/swarm/swarm_<ts>_<stage>_<run_id_short>.jsonl``.

Each line is a structured event so users / agents can inspect post-hoc
exactly what each swarm did: which phases ran, which models were used,
per-worker prompts/responses, durations, parse failures.

Design notes:
  * One file per swarm session — easy to list, easy to grep, no row-locking.
  * JSONL (newline-delimited JSON) — each line is independently parseable;
    partial files survive crashes.
  * The logger is best-effort: write failures are logged but never raise.
    A swarm that finishes but can't write its log still succeeds.
  * Filename embeds (timestamp, stage, short run_id) so a directory listing
    is sortable + identifiable without parsing.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SwarmEventLogger:
    """JSONL event logger for one ``SwarmOrchestrator.execute()`` session.

    Instantiate at the start of a swarm run; call ``phase_start`` /
    ``phase_end`` / ``worker_dispatch`` / ``worker_complete`` /
    ``parse_failure`` as the orchestrator progresses; call
    ``session_end`` once at the very end.  After construction, ``path``
    is the JSONL file the events are written to.
    """

    run_id: str
    stage: str
    project_id: str
    log_dir: Path
    started_at: float = field(default_factory=time.time)
    _path: Optional[Path] = None

    def __post_init__(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("swarm_event_logger: cannot create log_dir %s: %s",
                           self.log_dir, exc)
            # Fall through with a None path — every event() call will no-op.
            return
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.started_at))
        # Sanitize stage so filenames stay shell-friendly.
        safe_stage = "".join(c if c.isalnum() or c in "-_." else "_"
                             for c in (self.stage or "swarm"))
        short_id = (self.run_id or "noid")[:8]
        self._path = self.log_dir / f"swarm_{ts}_{safe_stage}_{short_id}.jsonl"
        self.event(
            "session_start",
            stage=self.stage,
            project_id=self.project_id,
            run_id=self.run_id,
        )

    @property
    def path(self) -> Optional[Path]:
        """JSONL file this logger writes to (None if init failed)."""
        return self._path

    def event(self, kind: str, **payload: Any) -> None:
        """Append one structured event line.

        Best-effort — write failures are logged at WARNING but never
        propagate.  ``ts`` is wall-clock seconds since epoch;
        ``elapsed_s`` is monotonic-ish elapsed time since the logger
        was constructed.
        """
        if self._path is None:
            return
        record = {
            "ts": time.time(),
            "elapsed_s": round(time.time() - self.started_at, 3),
            "kind": kind,
            **payload,
        }
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.warning("swarm_event_logger write failed (%s): %s", kind, exc)

    # -- Convenience wrappers -------------------------------------------------

    def phase_start(self, phase: str, model: Optional[str] = None,
                    n_items: Optional[int] = None) -> None:
        self.event("phase_start", phase=phase, model=model, n_items=n_items)

    def phase_end(self, phase: str, *, success: bool, duration_s: float,
                  **kw: Any) -> None:
        self.event("phase_end", phase=phase, success=success,
                   duration_s=round(duration_s, 3), **kw)

    def worker_dispatch(self, worker_id: str, work_item_id: str,
                        model: Optional[str], prompt_chars: int) -> None:
        self.event(
            "worker_dispatch",
            worker_id=worker_id,
            work_item_id=work_item_id,
            model=model,
            prompt_chars=prompt_chars,
        )

    def worker_complete(self, worker_id: str, *, success: bool,
                        duration_s: float, response_chars: int,
                        parse_ok: bool, error: Optional[str] = None) -> None:
        self.event(
            "worker_complete",
            worker_id=worker_id,
            success=success,
            duration_s=round(duration_s, 3),
            response_chars=response_chars,
            parse_ok=parse_ok,
            error=error,
        )

    def parse_failure(self, *, where: str, raw_chars: int,
                      reason: Optional[str] = None) -> None:
        """Record a JSON parse failure (coordinator, worker, or synthesis)."""
        self.event("parse_failure", where=where, raw_chars=raw_chars,
                   reason=reason)

    def session_end(self, *, success: bool,
                    summary: Optional[dict[str, Any]] = None) -> None:
        self.event("session_end", success=success, summary=summary or {})


def default_log_dir() -> Path:
    """Resolve ``<data_dir>/logs/swarm/``.  Creates the directory.

    Imported lazily (inside the function) to avoid a circular import
    when SwarmOrchestrator is itself imported during early daemon
    startup.
    """
    from prep.core.paths import data_dir as _data_dir
    p = _data_dir() / "logs" / "swarm"
    p.mkdir(parents=True, exist_ok=True)
    return p
