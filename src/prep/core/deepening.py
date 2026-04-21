"""
Continuous Deepening Loop for Prep (Pass 4+).

Orchestrates iterative refinement of epistemic enrichment until convergence.
Detects drift (stale nodes from source changes), manages a priority queue
for re-enrichment, and tracks convergence across iterations.

Components:
  - EnrichmentQueue: priority queue ordering nodes by epistemic score residual
  - DriftDetector: identifies stale nodes and propagates decay
  - ConvergenceTracker: detects when the graph has stabilized
  - DeepeningLoop: orchestrator that runs passes until convergence or budget

See docs/Phase22_trace-epistomology/PATH_FORWARD.md Sprint 6.
"""
from __future__ import annotations

import heapq
import json
import logging
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .llm_client import _get_llm_concurrency
from prep.services.pipeline.thread_pool import llm_pool
from .epistemic_score import (
    EpistemicEntry,
    EpistemicScore,
    apply_decay,
    compute_epistemic_score,
)

logger = logging.getLogger(__name__)

# ── Enrichment Queue ─────────────────────────────────────────────────

@dataclass(order=True)
class _QueueItem:
    """Priority queue item. Lower score = higher priority."""
    priority: float
    node_id: str = field(compare=False)
    reason: str = field(compare=False, default="")


class EnrichmentQueue:
    """Priority queue for nodes needing (re-)enrichment.

    Nodes are ordered by epistemic score (ascending) so the least-understood
    nodes are processed first. This is inspired by belief-propagation's
    residual scheduling — nodes with the largest "knowledge gap" get priority.
    """

    def __init__(self):
        self._heap: List[_QueueItem] = []
        self._in_queue: Set[str] = set()

    def add(self, node_id: str, score: float, reason: str = "") -> None:
        """Add a node to the queue. Lower score = higher priority."""
        if node_id in self._in_queue:
            return  # avoid duplicates
        heapq.heappush(self._heap, _QueueItem(priority=score, node_id=node_id, reason=reason))
        self._in_queue.add(node_id)

    def next_batch(self, max_nodes: int) -> List[Tuple[str, float, str]]:
        """Pop the highest-priority nodes (lowest scores).

        Returns list of (node_id, score, reason) tuples.
        """
        batch: List[Tuple[str, float, str]] = []
        while self._heap and len(batch) < max_nodes:
            item = heapq.heappop(self._heap)
            self._in_queue.discard(item.node_id)
            batch.append((item.node_id, item.priority, item.reason))
        return batch

    def __len__(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return len(self._heap) == 0


# ── Drift Detector ───────────────────────────────────────────────────

@dataclass
class DriftReport:
    """Report from a drift detection pass."""
    stale_nodes: List[str]           # nodes whose source hash changed
    missing_references: List[Tuple[str, str]]  # (doc_node_id, missing_file_path)
    decayed_nodes: Dict[str, float]  # node_id → new score after decay
    total_checked: int = 0


class DriftDetector:
    """Detects stale nodes and propagates epistemic decay.

    Checks:
    1. Source hash mismatch → node is stale (score → 0.0)
    2. Neighbor of stale node → mild decay (score × 0.95)
    3. Doc references to non-existent files → flagged as missing
    """

    def __init__(self, max_propagation_hops: int = 3):
        self.max_hops = max_propagation_hops

    def detect(
        self,
        scores: Dict[str, EpistemicScore],
        augmentations: Dict[str, Dict[str, Any]],
        current_file_hashes: Dict[str, str],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> DriftReport:
        """Run drift detection across all scored nodes.

        Returns a DriftReport with stale nodes, missing references,
        and decayed scores.
        """
        report = DriftReport(
            stale_nodes=[],
            missing_references=[],
            decayed_nodes={},
            total_checked=len(scores),
        )

        # Build adjacency
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in scores and tgt in scores:
                adjacency[src].add(tgt)
                adjacency[tgt].add(src)

        # Step 1: Find stale nodes (hash mismatch)
        stale_set: Set[str] = set()
        for node_id, score in scores.items():
            aug = augmentations.get(node_id)
            if not aug:
                continue
            file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
            aug_hash = aug.get("file_hash")
            current_hash = current_file_hashes.get(file_path)
            if aug_hash and current_hash and aug_hash != current_hash:
                stale_set.add(node_id)
                report.stale_nodes.append(node_id)
                report.decayed_nodes[node_id] = 0.0

        # Step 2: Propagate decay to neighbors (BFS, limited hops)
        frontier = set(stale_set)
        for hop in range(self.max_hops):
            if not frontier:
                break
            next_frontier: Set[str] = set()
            event = "neighbor_enriched" if hop == 0 else "neighbor_enriched"
            for node_id in frontier:
                for neighbor in adjacency.get(node_id, set()):
                    if neighbor in stale_set:
                        continue  # already at 0
                    if neighbor not in report.decayed_nodes:
                        old_score = scores[neighbor].composite if neighbor in scores else 0.5
                        new_score = apply_decay(old_score, "neighbor_enriched")
                        report.decayed_nodes[neighbor] = new_score
                        next_frontier.add(neighbor)
            frontier = next_frontier

        # Step 3: Check for missing references in doc nodes
        for e in edges:
            if e.get("kind") in ("references", "links_to"):
                target_id = e.get("target", "")
                if target_id and target_id not in nodes_by_id:
                    source_id = e.get("source", "")
                    target_path = target_id.replace("file:", "", 1)
                    report.missing_references.append((source_id, target_path))

        return report


# ── Convergence Tracker ──────────────────────────────────────────────

@dataclass
class ConvergenceState:
    """Tracks convergence across iterations."""
    iteration: int = 0
    settled_count: int = 0           # nodes with score >= threshold
    total_count: int = 0
    settled_ratio: float = 0.0
    avg_score: float = 0.0
    max_residual: float = 0.0       # largest score change from last iteration
    converged: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "settled_count": self.settled_count,
            "total_count": self.total_count,
            "settled_ratio": round(self.settled_ratio, 3),
            "avg_score": round(self.avg_score, 3),
            "max_residual": round(self.max_residual, 4),
            "converged": self.converged,
            "reason": self.reason,
        }


class ConvergenceTracker:
    """Detects when epistemic scores have stabilized.

    Convergence criteria (any of):
    1. All nodes have score >= settled_threshold → "all_settled"
    2. No node's score changed by more than residual_threshold → "no_change"
    3. Max iterations reached → "budget_exhausted"
    """

    def __init__(
        self,
        settled_threshold: float = 0.95,
        residual_threshold: float = 0.01,
        max_iterations: int = 10,
    ):
        self.settled_threshold = settled_threshold
        self.residual_threshold = residual_threshold
        self.max_iterations = max_iterations
        self._previous_scores: Dict[str, float] = {}
        self._iteration = 0

    def check(self, scores: Dict[str, EpistemicScore]) -> ConvergenceState:
        """Check convergence given current scores.

        Call this after each enrichment iteration.
        """
        self._iteration += 1

        if not scores:
            return ConvergenceState(
                iteration=self._iteration,
                converged=True,
                reason="no_nodes",
            )

        composites = {nid: s.composite for nid, s in scores.items()}
        settled = sum(1 for s in composites.values() if s >= self.settled_threshold)
        avg = sum(composites.values()) / len(composites)

        # Compute max residual (largest change from last iteration)
        max_residual = 0.0
        if self._previous_scores:
            for nid, score in composites.items():
                prev = self._previous_scores.get(nid, 0.0)
                residual = abs(score - prev)
                max_residual = max(max_residual, residual)

        self._previous_scores = dict(composites)

        state = ConvergenceState(
            iteration=self._iteration,
            settled_count=settled,
            total_count=len(composites),
            settled_ratio=settled / len(composites),
            avg_score=avg,
            max_residual=max_residual,
        )

        # Check convergence criteria
        if settled == len(composites):
            state.converged = True
            state.reason = "all_settled"
        elif self._iteration > 1 and max_residual < self.residual_threshold:
            state.converged = True
            state.reason = "no_change"
        elif self._iteration >= self.max_iterations:
            state.converged = True
            state.reason = "budget_exhausted"

        return state

    def reset(self) -> None:
        """Reset tracker for a new deepening run."""
        self._previous_scores.clear()
        self._iteration = 0


# ── Deepening Loop Orchestrator ──────────────────────────────────────

@dataclass
class DeepeningResult:
    """Result of a full deepening run."""
    iterations: int = 0
    total_enriched: int = 0
    total_re_enriched: int = 0
    drift_stale: int = 0
    drift_missing_refs: int = 0
    convergence: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "total_enriched": self.total_enriched,
            "total_re_enriched": self.total_re_enriched,
            "drift_stale": self.drift_stale,
            "drift_missing_refs": self.drift_missing_refs,
            "convergence": self.convergence,
            "duration_ms": round(self.duration_ms, 1),
        }


class DeepeningLoop:
    """Orchestrates iterative epistemic enrichment until convergence.

    Each iteration:
    1. Compute epistemic scores for all nodes.
    2. Run drift detection → identify stale nodes.
    3. Fill enrichment queue with nodes below threshold.
    4. Process batch from queue (re-enrich via deep reasoning model).
    5. Check convergence.
    6. Repeat until converged or budget exhausted.
    """

    def __init__(
        self,
        enricher: Any,  # EpistemicEnricher
        index_dir: Path,
        max_iterations: int = 10,
        batch_size: int = 20,
        settled_threshold: float = 0.60,
        residual_threshold: float = 0.01,
    ):
        self.enricher = enricher
        self.index_dir = index_dir
        self.max_iterations = max_iterations
        self.batch_size = batch_size
        self.convergence_tracker = ConvergenceTracker(
            settled_threshold=settled_threshold,
            residual_threshold=residual_threshold,
            max_iterations=max_iterations,
        )
        self.drift_detector = DriftDetector()

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> DeepeningResult:
        """Run the deepening loop until convergence or budget exhaustion."""
        start = time.monotonic()
        result = DeepeningResult()
        self.convergence_tracker.reset()

        for iteration in range(self.max_iterations):
            logger.info("Deepening iteration %d/%d", iteration + 1, self.max_iterations)

            if progress_callback:
                progress_callback("deepening_iteration", iteration, self.max_iterations)

            # 1. Compute scores
            scores = self.enricher.compute_all_scores()
            if not scores:
                logger.info("No scored nodes, stopping")
                break

            # 2. Drift detection
            augmentations = self.enricher.load_augmentations()
            edges = self.enricher.load_trace_edges()
            nodes = self.enricher.load_trace_nodes()
            nodes_by_id = {n["id"]: n for n in nodes}

            file_hashes = self._load_file_hashes()

            drift = self.drift_detector.detect(
                scores, augmentations, file_hashes, edges, nodes_by_id
            )
            result.drift_stale += len(drift.stale_nodes)
            result.drift_missing_refs += len(drift.missing_references)

            if drift.stale_nodes:
                logger.info(
                    "Drift: %d stale nodes, %d missing refs",
                    len(drift.stale_nodes), len(drift.missing_references),
                )

            # 3. Build enrichment queue
            queue = EnrichmentQueue()

            # Add stale nodes (highest priority)
            for nid in drift.stale_nodes:
                queue.add(nid, 0.0, reason="stale")

            # Add nodes below threshold
            for nid, score in scores.items():
                if score.composite < self.convergence_tracker.settled_threshold:
                    queue.add(nid, score.composite, reason="below_threshold")

            if queue.is_empty:
                logger.info("Queue empty — all nodes settled")

            # 4. Process batch
            batch = queue.next_batch(self.batch_size)
            if not batch:
                # Check convergence with current scores
                conv = self.convergence_tracker.check(scores)
                result.convergence = conv.to_dict()
                result.iterations = iteration + 1
                if conv.converged:
                    logger.info("Converged: %s (iteration %d)", conv.reason, conv.iteration)
                    break
                continue

            enriched_this_iter = 0
            re_enriched_this_iter = 0
            existing_epistemic = self.enricher.load_existing()

            concurrency = _get_llm_concurrency("deep")

            if concurrency <= 1:
                # Sequential: one node at a time
                for node_id, priority, reason in batch:
                    node = nodes_by_id.get(node_id)
                    if not node:
                        continue

                    is_re_enrichment = node_id in existing_epistemic
                    entry = self.enricher.enrich_node(
                        node, edges, nodes_by_id, augmentations, existing_epistemic
                    )
                    if entry:
                        entry.pass_number = existing_epistemic[node_id].pass_number + 1 if is_re_enrichment else 2
                        existing_epistemic[node_id] = entry
                        enriched_this_iter += 1
                        if is_re_enrichment:
                            re_enriched_this_iter += 1
            else:
                # Concurrent enrichment within the batch.
                #
                # Wall-clock timeout guard: a stuck LLM call (network hang, proxy
                # buffer, subprocess never returns) would otherwise leave
                # as_completed() blocked forever because future.result() has no
                # timeout. The 2026-04-18 crash (run-6e6eb4553626) froze in
                # iteration 7 with the worker alive but no forward progress for
                # 2h24m. Batch-level timeout surfaces the stuck future, cancels
                # peers, and lets the iteration finish with whatever completed.
                lock = threading.Lock()
                items = [(node_id, nodes_by_id.get(node_id), node_id in existing_epistemic)
                         for node_id, priority, reason in batch
                         if nodes_by_id.get(node_id) is not None]

                batch_timeout_sec = float(
                    os.environ.get("PREP_DEEPENING_BATCH_TIMEOUT", "600")
                )
                # Phase 82 follow-up: use the shared bounded pool.
                # ``concurrency`` now only selects the sequential (==1) vs
                # parallel (>1) execution path — it is NOT a cap on
                # in-flight requests. The AIMD gate in
                # LLMClient.generate (PipelineScheduler.acquire_request)
                # is the real throttle; submitting the full batch is fine
                # because surplus submits simply block at the gate.
                pool = llm_pool
                futures = {
                    pool.submit(
                        self.enricher.enrich_node, node, edges, nodes_by_id, augmentations, existing_epistemic
                    ): (node_id, is_re)
                    for node_id, node, is_re in items
                }
                try:
                    for future in as_completed(futures, timeout=batch_timeout_sec):
                        node_id, is_re = futures[future]
                        try:
                            entry = future.result()
                        except Exception as e:
                            logger.warning("Deepening enrichment failed for %s: %s", node_id, e)
                            entry = None
                        with lock:
                            if entry:
                                entry.pass_number = existing_epistemic[node_id].pass_number + 1 if is_re else 2
                                existing_epistemic[node_id] = entry
                                enriched_this_iter += 1
                                if is_re:
                                    re_enriched_this_iter += 1
                except FutureTimeoutError:
                    pending = [
                        futures[f] for f in futures if not f.done()
                    ]
                    logger.error(
                        "Deepening batch timed out after %.0fs (iteration %d): "
                        "%d/%d futures pending, cancelling and continuing. "
                        "Pending nodes: %s",
                        batch_timeout_sec,
                        iteration + 1,
                        len(pending),
                        len(futures),
                        [nid for nid, _ in pending[:5]],
                    )
                finally:
                    # Cancel any futures still pending on the shared pool so
                    # that an unhandled exception (OOM, KeyboardInterrupt,
                    # bubbled bug) does not orphan worker slots used by other
                    # pipeline stages. The except branch above already logged
                    # the timeout case; this just ensures cleanup on ALL paths.
                    for f in futures:
                        if not f.done():
                            f.cancel()
                # Shared pool — do NOT shut it down.

            result.total_enriched += enriched_this_iter
            result.total_re_enriched += re_enriched_this_iter

            # Write updated epistemic entries
            self.enricher._write_epistemic(existing_epistemic)

            # 5. Check convergence
            updated_scores = self.enricher.compute_all_scores()
            conv = self.convergence_tracker.check(updated_scores)
            result.convergence = conv.to_dict()
            result.iterations = iteration + 1

            logger.info(
                "Iteration %d: enriched=%d, re-enriched=%d, settled=%d/%d (%.1f%%), residual=%.4f",
                iteration + 1, enriched_this_iter, re_enriched_this_iter,
                conv.settled_count, conv.total_count,
                conv.settled_ratio * 100, conv.max_residual,
            )

            if conv.converged:
                logger.info("Converged: %s (iteration %d)", conv.reason, conv.iteration)
                break

        result.duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("deepening_complete", result.iterations, self.max_iterations)

        logger.info(
            "Deepening complete: %d iterations, %d enriched, %d re-enriched in %.1fs",
            result.iterations, result.total_enriched, result.total_re_enriched,
            result.duration_ms / 1000,
        )

        return result

    def _load_file_hashes(self) -> Dict[str, str]:
        """Load current file hashes from trace manifest."""
        manifest_path = self.index_dir / "trace_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                return manifest.get("file_hashes", {})
            except Exception:
                pass
        return {}
