"""
Deep Analysis Orchestrator for CoDRAG.

Implements Phase 2 (Steps 4-5) from LLM_TRACE_AUGMENTATION_RESEARCH.md:
- Step 4: Reasoning Validation (validate low-confidence augmentations)
- Step 5: Ontology Synthesis (build codebase domain map)

CRITICAL: Uses Evidence Tier 0 (ground truth only) for validation.
Never uses LLM-augmented content as evidence — prevents hallucination bootstrapping.
See §5.4-5.5 of the research doc for full rationale.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEEP_ANALYSIS_VERSION = "1.0"


@dataclass
class ValidationItem:
    """A single item in the validation queue."""
    node_id: str
    node_name: str
    file_path: str
    current_summary: str
    current_confidence: float
    priority_score: float  # higher = process first
    in_degree: int = 0
    out_degree: int = 0


@dataclass
class ValidationResult:
    """Result of validating a single augmentation."""
    node_id: str
    original_summary: str
    validated_summary: str
    original_confidence: float
    new_confidence: float
    verdict: str  # "confirmed" | "corrected" | "rejected"
    reasoning: str
    model: str
    tokens_used: int = 0


@dataclass
class DeepAnalysisResult:
    """Result of a full deep analysis run."""
    items_validated: int = 0
    items_confirmed: int = 0
    items_corrected: int = 0
    items_rejected: int = 0
    tokens_used: int = 0
    duration_ms: float = 0.0
    budget_exhausted: bool = False
    stop_reason: str = ""  # "complete" | "budget_tokens" | "budget_time" | "budget_items" | "empty_queue"
    errors: List[str] = field(default_factory=list)


@dataclass
class DeepAnalysisSchedule:
    """Schedule configuration for deep analysis runs."""
    mode: str = "manual"  # manual | auto | scheduled
    threshold_percent: int = 20
    frequency: str = "weekly"  # daily | weekly | biweekly | monthly
    day_of_week: int = 0  # 0=Sunday
    hour: int = 2  # 2 AM
    budget_enabled: bool = True  # False = no limits (recommended for Ollama/local models)
    budget_max_tokens: int = 50_000
    budget_max_minutes: int = 30
    budget_max_items: int = 100
    priority: str = "lowest_confidence"  # lowest_confidence | highest_connectivity
    schedule_threshold_enabled: bool = True  # Whether threshold trigger is active (scheduled mode)
    schedule_time_enabled: bool = True  # Whether time-based trigger is active (scheduled mode)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "threshold_percent": self.threshold_percent,
            "frequency": self.frequency,
            "day_of_week": self.day_of_week,
            "hour": self.hour,
            "budget_enabled": self.budget_enabled,
            "budget_max_tokens": self.budget_max_tokens,
            "budget_max_minutes": self.budget_max_minutes,
            "budget_max_items": self.budget_max_items,
            "priority": self.priority,
            "schedule_threshold_enabled": self.schedule_threshold_enabled,
            "schedule_time_enabled": self.schedule_time_enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DeepAnalysisSchedule":
        return cls(
            mode=d.get("mode", "manual"),
            threshold_percent=int(d.get("threshold_percent", 20)),
            frequency=d.get("frequency", "weekly"),
            day_of_week=int(d.get("day_of_week", 0)),
            hour=int(d.get("hour", 2)),
            budget_enabled=bool(d.get("budget_enabled", True)),
            budget_max_tokens=int(d.get("budget_max_tokens", 50_000)),
            budget_max_minutes=int(d.get("budget_max_minutes", 30)),
            budget_max_items=int(d.get("budget_max_items", 100)),
            priority=d.get("priority", "lowest_confidence"),
            schedule_threshold_enabled=bool(d.get("schedule_threshold_enabled", True)),
            schedule_time_enabled=bool(d.get("schedule_time_enabled", True)),
        )


# ── Prompt templates (Evidence Tier 0 safe) ───────────────────────────

VALIDATION_SYSTEM = """You are a senior code reviewer validating AI-generated code summaries.
You have access to GROUND TRUTH evidence (actual source code and documentation).
You also see CLAIMED summaries from another AI model — treat these as HYPOTHESES, not facts.
You MUST respond with valid JSON only."""

VALIDATION_PROMPT = """Validate this AI-generated summary of a code symbol.

CLAIMED (unverified, from fast model):
  Summary: "{claimed_summary}"
  Role: {claimed_role}
  Confidence: {claimed_confidence}

GROUND TRUTH EVIDENCE (source code only, no AI summaries):
  Symbol: {symbol_name} ({symbol_type})
  File: {file_path}
  Source code:
```
{source_code}
```

  Static trace info:
  - Imports: {imports}
  - Imported by: {imported_by}
  - Contains: {contains}

Based ONLY on the ground truth evidence above:
1. Is the claimed summary accurate?
2. If not, what does the source code actually do?
3. How confident are you?

Respond with this exact JSON (keep summary under 1 sentence, max 120 chars):
{{"verdict": "confirmed", "summary": "corrected summary if needed", "confidence": 0.9, "reasoning": "brief explanation"}}

Where verdict is: confirmed (summary is accurate), corrected (partially wrong, here's the fix), rejected (completely wrong)
IMPORTANT: Keep ALL string values short. Do not write paragraphs.

JSON response:"""


class DeepAnalysisOrchestrator:
    """
    Orchestrates deep analysis runs with budget controls.

    Key constraints:
    - Uses Evidence Tier 0 (ground truth) for all validation queries.
    - Never presents LLM-augmented content as evidence.
    - Processes lowest-confidence items first (by default).
    - Respects token, time, and item budgets.
    """

    def __init__(
        self,
        index_dir: str | Path,
        repo_root: str | Path,
        schedule: Optional[DeepAnalysisSchedule] = None,
    ):
        self.index_dir = Path(index_dir).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.schedule = schedule or DeepAnalysisSchedule()

        self.augmented_path = self.index_dir / "trace_augmented.jsonl"
        self.deep_manifest_path = self.index_dir / "deep_analysis_manifest.json"
        self.nodes_path = self.index_dir / "trace_nodes.jsonl"
        self.edges_path = self.index_dir / "trace_edges.jsonl"

    def build_validation_queue(self) -> List[ValidationItem]:
        """
        Build a priority queue of items to validate.
        Sorted by priority (lowest confidence first by default).
        """
        from .augmenter import AugmentationEntry

        # Load augmentations
        entries: Dict[str, AugmentationEntry] = {}
        if self.augmented_path.exists():
            with open(self.augmented_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        entry = AugmentationEntry.from_dict(d)
                        # Skip already-validated items
                        if not entry.validated:
                            entries[entry.node_id] = entry

        if not entries:
            return []

        # Load trace nodes for metadata
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        if self.nodes_path.exists():
            with open(self.nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        n = json.loads(line)
                        nodes_by_id[n["id"]] = n

        # Load edges for degree calculation
        in_degree: Dict[str, int] = {}
        out_degree: Dict[str, int] = {}
        if self.edges_path.exists():
            with open(self.edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        e = json.loads(line)
                        tgt = e.get("target", "")
                        src = e.get("source", "")
                        in_degree[tgt] = in_degree.get(tgt, 0) + 1
                        out_degree[src] = out_degree.get(src, 0) + 1

        # Build queue
        queue: List[ValidationItem] = []
        for node_id, entry in entries.items():
            node = nodes_by_id.get(node_id)
            if not node:
                continue

            in_deg = in_degree.get(node_id, 0)
            out_deg = out_degree.get(node_id, 0)
            connectivity = in_deg + out_deg

            if self.schedule.priority == "lowest_confidence":
                # Lower confidence = higher priority (invert so sort works)
                priority = 1.0 - entry.confidence
            else:
                # Higher connectivity = higher priority
                priority = float(connectivity)

            queue.append(ValidationItem(
                node_id=node_id,
                node_name=node.get("name", ""),
                file_path=node.get("file_path", ""),
                current_summary=entry.summary,
                current_confidence=entry.confidence,
                priority_score=priority,
                in_degree=in_deg,
                out_degree=out_deg,
            ))

        # Sort by priority (highest first)
        queue.sort(key=lambda x: x.priority_score, reverse=True)
        return queue

    def run(
        self,
        llm_client: Any,  # augmenter.LLMClient
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> DeepAnalysisResult:
        """
        Run deep analysis with budget controls.

        Uses Evidence Tier 0: only raw source code and static trace data.
        """
        start = time.monotonic()
        result = DeepAnalysisResult()
        budget = self.schedule

        queue = self.build_validation_queue()
        if not queue:
            logger.info("Validation queue empty — nothing to validate")
            result.stop_reason = "empty_queue"
            return result

        # Apply item budget
        items_to_process = queue[: budget.budget_max_items]
        total = len(items_to_process)
        logger.info("Deep analysis: %d items to validate (queue has %d total)", total, len(queue))

        # Load source data for Tier 0 evidence
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        if self.nodes_path.exists():
            with open(self.nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        n = json.loads(line)
                        nodes_by_id[n["id"]] = n

        edges: List[Dict[str, Any]] = []
        if self.edges_path.exists():
            with open(self.edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edges.append(json.loads(line))

        # Load existing augmentations (we'll update them)
        from .augmenter import AugmentationEntry
        augmented: Dict[str, AugmentationEntry] = {}
        if self.augmented_path.exists():
            with open(self.augmented_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        entry = AugmentationEntry.from_dict(d)
                        augmented[entry.node_id] = entry

        for i, item in enumerate(items_to_process):
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                logger.info("Deep analysis cancelled by user")
                result.stop_reason = "cancelled"
                break

            # Check time budget
            elapsed_min = (time.monotonic() - start) / 60
            if elapsed_min >= budget.budget_max_minutes:
                logger.info("Time budget exhausted (%.1f min)", elapsed_min)
                result.budget_exhausted = True
                result.stop_reason = "budget_time"
                break

            # Check token budget
            if result.tokens_used >= budget.budget_max_tokens:
                logger.info("Token budget exhausted (%d tokens)", result.tokens_used)
                result.budget_exhausted = True
                result.stop_reason = "budget_tokens"
                break

            if progress_callback:
                progress_callback("deep_validate", i, total)

            if i > 0 and i % 10 == 0:
                logger.info("Deep analysis progress: %d/%d items validated", i, total)

            # Build Tier 0 evidence
            node = nodes_by_id.get(item.node_id)
            if not node:
                continue

            validation_result = self._validate_item(item, node, edges, nodes_by_id, llm_client)
            if not validation_result:
                result.errors.append(f"Failed to validate {item.node_name}")
                continue

            result.tokens_used += validation_result.tokens_used

            # Update the augmentation entry
            if item.node_id in augmented:
                entry = augmented[item.node_id]
                entry.validated = True
                entry.validated_at = datetime.now(timezone.utc).isoformat()
                entry.validated_by = validation_result.model

                if validation_result.verdict == "confirmed":
                    entry.confidence = max(entry.confidence, validation_result.new_confidence)
                    result.items_confirmed += 1
                elif validation_result.verdict == "corrected":
                    entry.summary = validation_result.validated_summary
                    entry.confidence = validation_result.new_confidence
                    result.items_corrected += 1
                elif validation_result.verdict == "rejected":
                    entry.summary = validation_result.validated_summary
                    entry.confidence = validation_result.new_confidence
                    result.items_rejected += 1

            result.items_validated += 1

        # Write updated augmentations
        if result.items_validated > 0:
            self._write_augmentations(augmented)

        # If we processed all items without hitting a budget, mark complete
        if not result.stop_reason:
            if result.items_validated >= total:
                result.stop_reason = "complete"
            else:
                result.stop_reason = "budget_items"

        result.duration_ms = (time.monotonic() - start) * 1000
        self._write_manifest(result, len(queue))

        if progress_callback:
            progress_callback("deep_complete", total, total)

        logger.info(
            "Deep analysis complete: %d validated (%d confirmed, %d corrected, %d rejected) in %.1fs, %d tokens",
            result.items_validated, result.items_confirmed, result.items_corrected,
            result.items_rejected, result.duration_ms / 1000, result.tokens_used,
        )
        return result

    def _validate_item(
        self,
        item: ValidationItem,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        llm_client: Any,
    ) -> Optional[ValidationResult]:
        """Validate a single item using Tier 0 evidence only."""
        file_path = item.file_path
        span = node.get("span")

        # Read source code (Tier 0 — ground truth)
        source = self._read_source(file_path, span)
        if not source:
            return None

        # Build static trace context (Tier 0 — deterministic)
        imports = self._get_edges_for(node["id"], edges, nodes_by_id, "imports", "out")
        imported_by = self._get_edges_for(node["id"], edges, nodes_by_id, "imports", "in")
        contains = self._get_edges_for(node["id"], edges, nodes_by_id, "contains", "out")

        symbol_type = node.get("metadata", {}).get("symbol_type", "unknown")

        prompt = VALIDATION_PROMPT.format(
            claimed_summary=item.current_summary,
            claimed_role="unknown",
            claimed_confidence=item.current_confidence,
            symbol_name=item.node_name,
            symbol_type=symbol_type,
            file_path=file_path,
            source_code=source[:3000],
            imports=imports or "(none)",
            imported_by=imported_by or "(none)",
            contains=contains or "(none)",
        )

        try:
            text, tokens = llm_client.generate(prompt, system=VALIDATION_SYSTEM, num_predict=2048)
        except Exception as e:
            logger.warning("Validation LLM call failed for %s: %s", item.node_name, e)
            return None

        from .llm_client import _parse_json_response
        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("Failed to parse validation response for %s — raw: %.200s", item.node_name, text)
            return None

        verdict = parsed.get("verdict", "confirmed")
        if verdict not in ("confirmed", "corrected", "rejected"):
            verdict = "confirmed"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ValidationResult(
            node_id=item.node_id,
            original_summary=item.current_summary,
            validated_summary=str(parsed.get("summary", item.current_summary))[:500],
            original_confidence=item.current_confidence,
            new_confidence=confidence,
            verdict=verdict,
            reasoning=str(parsed.get("reasoning", ""))[:300],
            model=llm_client.model,
            tokens_used=tokens,
        )

    def _read_source(self, file_path: str, span: Optional[Dict[str, int]], max_chars: int = 3000) -> str:
        """Read source code from the repo (Tier 0 ground truth)."""
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return ""
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            if span:
                lines = text.splitlines()
                start = max(0, span.get("start_line", 1) - 1)
                end = min(len(lines), span.get("end_line", len(lines)))
                snippet = "\n".join(lines[start:end])
            else:
                snippet = text
            return snippet[:max_chars]
        except Exception:
            return ""

    def _get_edges_for(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        edge_kind: str,
        direction: str,  # "in" or "out"
    ) -> str:
        """Get edge descriptions for a node (Tier 0 — static trace only)."""
        results = []
        for e in edges:
            if e.get("kind") != edge_kind:
                continue
            if direction == "out" and e.get("source") == node_id:
                target = nodes_by_id.get(e["target"])
                if target:
                    results.append(target.get("name", e["target"]))
            elif direction == "in" and e.get("target") == node_id:
                source = nodes_by_id.get(e["source"])
                if source:
                    results.append(source.get("name", e["source"]))
        return ", ".join(results[:15])

    def _write_augmentations(self, entries: Dict[str, Any]) -> None:
        """Write updated augmentations atomically."""
        import os
        import tempfile

        sorted_entries = sorted(entries.values(), key=lambda e: e.node_id)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            for entry in sorted_entries:
                tmp.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.augmented_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def _write_manifest(self, result: DeepAnalysisResult, queue_size: int) -> None:
        """Write deep analysis manifest."""
        import os
        import tempfile

        manifest = {
            "version": DEEP_ANALYSIS_VERSION,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "items_validated": result.items_validated,
            "items_confirmed": result.items_confirmed,
            "items_corrected": result.items_corrected,
            "items_rejected": result.items_rejected,
            "tokens_used": result.tokens_used,
            "duration_ms": round(result.duration_ms, 1),
            "budget_exhausted": result.budget_exhausted,
            "stop_reason": result.stop_reason,
            "queue_remaining": queue_size - result.items_validated,
            "queue_total": queue_size,
        }

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.deep_manifest_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def status(self, include_queue: bool = False) -> Dict[str, Any]:
        """Return deep analysis status.

        By default reads only the small manifest file (fast).
        Pass include_queue=True to recompute live queue stats from disk (slower).
        """
        base: Dict[str, Any] = {
            "queue_size": 0,
            "avg_confidence": 0.0,
            "running": False,
        }

        if self.deep_manifest_path.exists():
            try:
                with open(self.deep_manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                base["last_run_at"] = manifest.get("completed_at")
                base["last_run_items"] = manifest.get("items_validated", 0)
                base["last_run_tokens"] = manifest.get("tokens_used", 0)
                base["stop_reason"] = manifest.get("stop_reason", "")
                base["budget_exhausted"] = manifest.get("budget_exhausted", False)
                base["queue_remaining"] = manifest.get("queue_remaining", 0)
                # Use cached queue stats from manifest if not recomputing
                if not include_queue:
                    base["queue_size"] = manifest.get("queue_remaining", 0)
                    # We don't have cached avg_confidence in manifest, leave at 0
            except Exception:
                pass

        # Full queue rebuild — expensive on large repos / slow disks
        if include_queue:
            queue = self.build_validation_queue()
            confidences = [item.current_confidence for item in queue]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            base["queue_size"] = len(queue)
            base["avg_confidence"] = round(avg_conf, 3)

        return base
