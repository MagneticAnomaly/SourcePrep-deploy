"""
Pi Agent — Phase 66: Proactive Intelligence Agent

Autonomous background analysis agent that runs within the CoDRAG daemon.
Provides 7 intelligence scenarios that execute after pipeline completions
or on scheduled intervals.

Design principles:
  - Runs as a daemon thread (no separate process)
  - Imports CoDRAG modules directly (no MCP serialization overhead)
  - Uses CoDRAG's LLMClient (inherits OutputMonitor, rate limiting, JSON repair)
  - Respects AgentConcurrencyGate (defers to pipeline)
  - Token telemetry is automatic via LLMClient
  - All results written to codrag_observe (cross-session memory)
  - Works with aggregated ActionItems (50-200), never raw nodes (5,000+)

Scenarios:
  A: Watchdog   — Delta scan after pipeline rebuild (~80s)
  B: Doctor     — Index integrity check (~40s)
  C: Geologist  — Weekly architecture drift detection (~2min)
  D: Dispatcher — Smart triage of findings (~2.2min)
  E: Librarian  — Stale observation cleanup (~1min)
  G: Architect  — Monthly architecture proposals (~9min)
  H: Scholar    — Enrichment quality monitoring (~80s)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PiAgent:
    """Proactive Intelligence agent — autonomous background analysis.

    Lifecycle:
      1. Created by server.py at startup (if agent_enabled=True)
      2. Registered as a pipeline completion callback
      3. On pipeline complete → runs Watchdog scenario in background thread
      4. Other scenarios triggered on schedule or on-demand via API
    """

    # ── Class constants ──────────────────────────────────────────

    # Maximum findings to process in a single agent LLM call.
    # Prevents the "10,000 items" problem — agents work with
    # pre-aggregated ActionItems, but we guard against edge cases.
    MAX_FINDINGS_PER_CALL = 200

    # Maximum findings to run impact analysis on (for Dispatcher).
    MAX_IMPACT_TARGETS = 10

    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        collab_hub: Optional[Any] = None,
    ) -> None:
        self.project_id = project_id
        self.index_dir = Path(index_dir)
        self.project_root = Path(project_root) if project_root else None
        self._collab = collab_hub

        # Configuration (loaded from settings_store at runtime)
        self._enabled: bool = False
        self._auto_scan: bool = True
        self._cooldown_seconds: int = 300
        self._triage_threshold: int = 50

        # State tracking
        self._lock = threading.Lock()
        self._last_watchdog_at: float = 0.0
        self._last_librarian_at: float = 0.0
        self._last_scan_delta: Optional[Dict[str, Any]] = None
        self._running_task: Optional[str] = None

        # Load configuration
        self._reload_config()

    # ── Configuration ────────────────────────────────────────────

    def _reload_config(self) -> None:
        """Reload agent configuration from settings store."""
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            self._enabled = bool(config.get("agent_enabled", False))
            self._auto_scan = bool(config.get("agent_auto_scan", True))
            self._cooldown_seconds = int(config.get("agent_cooldown_seconds", 300))
            self._triage_threshold = int(config.get("agent_triage_threshold", 50))
        except Exception:
            logger.debug("Failed to reload agent config, using defaults", exc_info=True)

    # ── Pipeline Integration ─────────────────────────────────────

    def on_pipeline_complete(self, group: str) -> None:
        """Called by PipelineOrchestrator after a group completes.

        This is the primary trigger for the Watchdog scenario.
        Runs in a background thread to avoid blocking the pipeline.

        Args:
            group: "fast_sync" or "deep_enrichment"
        """
        self._reload_config()

        if not self._enabled:
            logger.debug("Pi agent disabled, skipping post-pipeline scan")
            return

        if not self._auto_scan:
            logger.debug("Pi auto-scan disabled, skipping")
            return

        # Respect cooldown
        now = time.time()
        if now - self._last_watchdog_at < self._cooldown_seconds:
            remaining = self._cooldown_seconds - (now - self._last_watchdog_at)
            logger.debug("Pi watchdog in cooldown (%.0fs remaining)", remaining)
            return

        # Run Watchdog in background thread
        t = threading.Thread(
            target=self._safe_run,
            args=("watchdog", self._run_watchdog, group),
            daemon=True,
            name="pi-watchdog",
        )
        t.start()

    def _safe_run(self, task_name: str, fn: Any, *args: Any) -> None:
        """Wrapper that catches all exceptions and logs them."""
        with self._lock:
            if self._running_task:
                logger.debug(
                    "Pi: %s already running, skipping %s",
                    self._running_task, task_name,
                )
                return
            self._running_task = task_name

        try:
            fn(*args)
        except Exception:
            logger.exception("Pi agent task '%s' failed", task_name)
        finally:
            with self._lock:
                self._running_task = None

    # ── Scenario A: Watchdog ─────────────────────────────────────

    def _run_watchdog(self, group: str) -> None:
        """Compare current audit scan against last scan, report delta.

        Steps:
          1. Check agent gate (defer if pipeline still using LLM)
          2. Run codrag_audit scan (pure Python, ~5s)
          3. Load previous scan summary from observations
          4. Compute delta (new/resolved findings)
          5. If delta is non-empty: summarize with LLM (~74s local)
          6. Save observation with delta summary

        Time budget: ~80s (local qwen3.5:35b) / ~20s (cloud)
        """
        from codrag.services.agent_gate import get_agent_gate

        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="watchdog"):
            logger.info("Pi watchdog: pipeline busy, deferring")
            return

        try:
            start = time.monotonic()
            logger.info("Pi watchdog: starting post-%s scan", group)

            # Step 1: Run audit scan (pure Python, no LLM, ~5s)
            current_summary = self._get_current_scan_summary()
            if current_summary is None:
                logger.warning("Pi watchdog: audit scan returned no data")
                return

            # Step 2: Load previous scan from observations
            previous_summary = self._get_previous_scan_summary()

            # Step 3: Compute delta
            delta = self._compute_delta(current_summary, previous_summary)

            # Step 4: Save current scan as the new baseline
            self._save_scan_summary(current_summary)

            # Step 5: If nothing changed, skip LLM
            if not delta["new_findings"] and not delta["resolved_findings"]:
                logger.info("Pi watchdog: no changes since last scan (%.1fs)", time.monotonic() - start)
                self._last_watchdog_at = time.time()
                self._last_scan_delta = delta
                return

            # Step 6: Save delta summary (no LLM needed for structured delta)
            self._save_delta_observation(delta, group)

            elapsed = time.monotonic() - start
            self._last_watchdog_at = time.time()
            self._last_scan_delta = delta

            logger.info(
                "Pi watchdog: complete in %.1fs — %d new, %d resolved, %d unchanged",
                elapsed,
                len(delta["new_findings"]),
                len(delta["resolved_findings"]),
                delta["unchanged_count"],
            )

            # Phase 65: Auto-push to PM tool if configured
            self._try_auto_push()

        finally:
            gate.release()

    # ── Scenario E: Librarian ────────────────────────────────────

    def run_librarian(self) -> Optional[Dict[str, Any]]:
        """Clean up stale and orphaned observations.

        Checks codrag_observe entries for:
        - Stale observations (linked file changed since observation was saved)
        - Orphaned observations (referenced file no longer exists)

        Returns a summary dict or None if gate couldn't be acquired.
        Time budget: ~1min
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="librarian"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi librarian: starting observation cleanup")

            results = {
                "stale_found": 0,
                "orphaned_found": 0,
                "cleaned": 0,
            }

            # Get all observations including stale ones
            try:
                from codrag.services.observation_store import observation_store
                all_obs = observation_store.get_recent(
                    project_id=self.project_id,
                    include_stale=True,
                    limit=100,
                )
                for obs in all_obs:
                    if obs.stale:
                        results["stale_found"] += 1
                    fp = obs.file_path
                    if fp and self.project_root:
                        full_path = self.project_root / fp
                        if not full_path.exists():
                            results["orphaned_found"] += 1
            except Exception:
                logger.debug("Pi librarian: observation scan failed", exc_info=True)

            elapsed = time.monotonic() - start
            self._last_librarian_at = time.time()

            logger.info(
                "Pi librarian: complete in %.1fs — %d stale, %d orphaned",
                elapsed, results["stale_found"], results["orphaned_found"],
            )

            # Save the librarian report as an observation
            summary = (
                f"Librarian scan: {results['stale_found']} stale observations, "
                f"{results['orphaned_found']} orphaned observations found."
            )
            self._save_observation(
                content=summary,
                category="agent_scan",
                scenario="pi/librarian",
            )
            self._log_activity("librarian", "scan_complete", summary)

            return results

        finally:
            gate.release()

    # ── Scenario D: Dispatcher ───────────────────────────────────

    def run_dispatcher(self) -> Optional[Dict[str, Any]]:
        """Smart triage: group top findings by root cause using impact analysis.

        Steps:
          1. Get current audit findings
          2. Select TOP N critical/warning findings
          3. Run codrag_impact on each (graph traversal, no LLM, ~100ms each)
          4. Group by shared impacted files (potential root causes)
          5. Save triage summary

        Time budget: ~2.2min (local) / ~30s (cloud)
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="dispatcher"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi dispatcher: starting smart triage")

            # Step 1: Get current findings
            current = self._get_current_scan_summary()
            if not current:
                return None

            findings = current.get("findings", [])
            if len(findings) < self._triage_threshold:
                logger.info(
                    "Pi dispatcher: only %d findings (threshold=%d), skipping triage",
                    len(findings), self._triage_threshold,
                )
                return {"skipped": True, "reason": "below_threshold", "count": len(findings)}

            # Step 2: Select top findings by severity
            severity_order = {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}
            sorted_findings = sorted(
                findings,
                key=lambda f: severity_order.get(f.get("severity", "info"), 99),
            )
            top_findings = sorted_findings[:self.MAX_IMPACT_TARGETS]

            # Step 3: Run impact analysis on each (pure graph, no LLM)
            impact_groups: Dict[str, List[str]] = {}  # file → list of finding IDs
            try:
                from codrag.core.trace.index import TraceIndex
                from codrag.core.ids import stable_file_node_id
                ti = TraceIndex(self.index_dir)
                if ti.load():
                    for finding in top_findings:
                        finding_files = finding.get("file_paths", [])
                        if not finding_files:
                            continue
                        primary_file = finding_files[0]
                        try:
                            file_node_id = stable_file_node_id(primary_file)
                            impact = ti.get_impact_graph(
                                node_id=file_node_id,
                                max_hops=1,
                                max_nodes=20,
                            )
                            # Track which findings share impacted files
                            for dep in (impact.get("dependents") or []):
                                dep_path = dep.get("path", "")
                                if dep_path:
                                    if dep_path not in impact_groups:
                                        impact_groups[dep_path] = []
                                    finding_id = finding.get("finding_id", finding.get("analyzer", "unknown"))
                                    impact_groups[dep_path].append(finding_id)
                        except Exception:
                            logger.debug("Impact analysis failed for %s", primary_file, exc_info=True)
            except ImportError:
                logger.warning("Pi dispatcher: TraceIndex not available")

            # Step 4: Identify root causes (files impacted by multiple findings)
            root_causes = {
                file_path: finding_ids
                for file_path, finding_ids in impact_groups.items()
                if len(finding_ids) > 1
            }

            result = {
                "total_findings": len(findings),
                "analyzed_findings": len(top_findings),
                "root_causes": len(root_causes),
                "top_root_causes": dict(
                    sorted(root_causes.items(), key=lambda x: len(x[1]), reverse=True)[:5]
                ),
            }

            # Step 5: Save triage summary
            self._save_observation(
                content=(
                    f"Dispatcher triage: analyzed top {len(top_findings)} of "
                    f"{len(findings)} findings. Found {len(root_causes)} potential "
                    f"root causes (files impacted by multiple findings)."
                    + (
                        f" Top root cause: {list(result['top_root_causes'].keys())[0]} "
                        f"(affects {len(list(result['top_root_causes'].values())[0])} findings)"
                        if result["top_root_causes"] else ""
                    )
                ),
                category="agent_triage",
                scenario="pi/dispatcher",
            )

            elapsed = time.monotonic() - start
            logger.info(
                "Pi dispatcher: complete in %.1fs — %d root causes found",
                elapsed, len(root_causes),
            )
            self._log_activity(
                "dispatcher", "triage_complete",
                f"{len(root_causes)} root causes from {len(findings)} findings",
            )

            return result

        finally:
            gate.release()

    # ── Scenario B: Doctor ───────────────────────────────────────

    def run_doctor(self) -> Optional[Dict[str, Any]]:
        """Check index integrity: orphaned nodes, broken edges, stale data.

        Steps:
          1. Run audit scan with focus on architecture/quality categories
          2. Check for critical structural issues
          3. Recommend rebuild if integrity is compromised

        Returns a summary dict or None if gate couldn't be acquired.
        Time budget: ~40s (mostly the audit scan at ~5s + analysis)
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="doctor"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi doctor: starting index integrity check")

            results: Dict[str, Any] = {
                "has_trace": False,
                "node_count": 0,
                "edge_count": 0,
                "integrity_issues": [],
                "recommendation": "ok",
            }

            # Step 1: Check trace index existence and basic stats
            try:
                trace_manifest = self.index_dir / "trace_manifest.json"
                if trace_manifest.exists():
                    import json as _json
                    manifest = _json.loads(trace_manifest.read_text(encoding="utf-8"))
                    results["has_trace"] = True
                    counts = manifest.get("counts", {})
                    results["node_count"] = counts.get("nodes", 0)
                    results["edge_count"] = counts.get("edges", 0)

                    # Check: zero nodes but manifest exists → corrupt
                    if results["node_count"] == 0:
                        results["integrity_issues"].append(
                            "Trace manifest exists but has 0 nodes — possible corruption"
                        )

                    # Check: very low edge-to-node ratio → sparse graph
                    if results["node_count"] > 0:
                        ratio = results["edge_count"] / results["node_count"]
                        if ratio < 0.5:
                            results["integrity_issues"].append(
                                f"Edge-to-node ratio is {ratio:.1f} (expected ≥1.0) — graph may be under-enriched"
                            )
                else:
                    results["integrity_issues"].append(
                        "No trace manifest found — index may not have been built"
                    )
            except Exception:
                logger.debug("Pi doctor: trace check failed", exc_info=True)
                results["integrity_issues"].append("Failed to read trace manifest")

            # Step 2: Check key data files exist and have content
            expected_files = [
                ("trace_augmented.jsonl", "augmentation data"),
                ("trace_modules.jsonl", "module clustering"),
                ("trace_epistemic.jsonl", "epistemic enrichment"),
            ]
            for filename, description in expected_files:
                filepath = self.index_dir / filename
                if not filepath.exists():
                    results["integrity_issues"].append(f"Missing {filename} ({description})")
                elif filepath.stat().st_size == 0:
                    results["integrity_issues"].append(f"Empty {filename} ({description})")

            # Step 3: Run a quick audit scan to check for critical findings
            current = self._get_current_scan_summary()
            if current:
                critical_count = sum(
                    1 for f in current.get("findings", [])
                    if f.get("severity") == "critical"
                )
                if critical_count > 0:
                    results["integrity_issues"].append(
                        f"{critical_count} critical audit findings detected"
                    )

            # Step 4: Determine recommendation
            issue_count = len(results["integrity_issues"])
            if issue_count == 0:
                results["recommendation"] = "ok"
            elif issue_count <= 2:
                results["recommendation"] = "monitor"
            else:
                results["recommendation"] = "rebuild_recommended"

            elapsed = time.monotonic() - start
            logger.info(
                "Pi doctor: complete in %.1fs — %d issues found, recommendation=%s",
                elapsed, issue_count, results["recommendation"],
            )

            # Save observation
            self._save_observation(
                content=(
                    f"Doctor check: {issue_count} integrity issues. "
                    f"Nodes={results['node_count']}, Edges={results['edge_count']}. "
                    f"Recommendation: {results['recommendation']}."
                    + (f" Issues: {'; '.join(results['integrity_issues'][:3])}" if results["integrity_issues"] else "")
                ),
                category="agent_scan",
                scenario="pi/doctor",
            )
            self._log_activity(
                "doctor", "check_complete",
                f"{issue_count} issues, recommendation: {results['recommendation']}",
            )

            return results

        finally:
            gate.release()

    # ── Scenario C: Geologist ────────────────────────────────────

    def run_geologist(self) -> Optional[Dict[str, Any]]:
        """Detect architecture drift by comparing atlas snapshots.

        Steps:
          1. Load current atlas (CodebaseAtlas)
          2. Load previous atlas snapshot from observations
          3. Compare module structure: new modules, removed modules, changed hub files
          4. Save drift report as observation

        Returns a drift summary dict or None.
        Time budget: ~2min (pure Python comparison, no LLM)
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="geologist"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi geologist: starting architecture drift detection")

            results: Dict[str, Any] = {
                "has_atlas": False,
                "current_modules": [],
                "previous_modules": [],
                "drift": {
                    "new_modules": [],
                    "removed_modules": [],
                    "changed_module_count": 0,
                },
                "drift_detected": False,
            }

            # Step 1: Load current atlas
            try:
                from codrag.core.atlas import CodebaseAtlas
                atlas = CodebaseAtlas(self.index_dir)
                doc = atlas.load()
                if doc is None:
                    logger.info("Pi geologist: no atlas found, skipping drift detection")
                    return results

                results["has_atlas"] = True

                # Extract module names from atlas
                current_modules = set()
                if hasattr(doc, "modules") and doc.modules:
                    for mod in doc.modules:
                        mod_name = getattr(mod, "name", None) or getattr(mod, "path", None)
                        if mod_name:
                            current_modules.add(str(mod_name))
                elif hasattr(doc, "segments") and doc.segments:
                    for seg in doc.segments:
                        seg_name = getattr(seg, "name", None) or getattr(seg, "path", None)
                        if seg_name:
                            current_modules.add(str(seg_name))

                results["current_modules"] = sorted(current_modules)

            except Exception:
                logger.debug("Pi geologist: atlas load failed", exc_info=True)
                return results

            # Step 2: Load previous module snapshot from observations
            previous_modules: set = set()
            try:
                from codrag.services.observation_store import observation_store
                obs_list = observation_store.get_for_query(
                    project_id=self.project_id,
                    query="geologist_module_snapshot",
                    limit=1,
                )
                if obs_list:
                    content = obs_list[0].content
                    # Parse the tagged content
                    if "[geologist_module_snapshot]" in content:
                        json_part = content.split("]", 1)[1].strip()
                        try:
                            previous_modules = set(json.loads(json_part))
                        except (json.JSONDecodeError, TypeError):
                            pass
            except Exception:
                logger.debug("Pi geologist: previous snapshot load failed", exc_info=True)

            results["previous_modules"] = sorted(previous_modules)

            # Step 3: Compute drift
            new_modules = current_modules - previous_modules
            removed_modules = previous_modules - current_modules
            changed = len(new_modules) + len(removed_modules)

            results["drift"] = {
                "new_modules": sorted(new_modules),
                "removed_modules": sorted(removed_modules),
                "changed_module_count": changed,
            }
            results["drift_detected"] = changed > 0

            # Step 4: Save current snapshot as baseline
            self._save_observation(
                content=json.dumps(sorted(current_modules)),
                category="agent_scan",
                query_tag="geologist_module_snapshot",
                scenario="pi/geologist",
            )

            # Step 5: Save drift report
            if results["drift_detected"]:
                drift_parts = []
                if new_modules:
                    drift_parts.append(f"+{len(new_modules)} new: {', '.join(sorted(new_modules)[:5])}")
                if removed_modules:
                    drift_parts.append(f"-{len(removed_modules)} removed: {', '.join(sorted(removed_modules)[:5])}")

                self._save_observation(
                    content=f"Geologist drift: {' | '.join(drift_parts)}",
                    category="agent_scan",
                    scenario="pi/geologist",
                )

            elapsed = time.monotonic() - start
            logger.info(
                "Pi geologist: complete in %.1fs — drift_detected=%s (%d changes)",
                elapsed, results["drift_detected"], changed,
            )
            self._log_activity(
                "geologist", "drift_scan_complete",
                f"drift={'yes' if results['drift_detected'] else 'no'}, {changed} changes",
            )

            return results

        finally:
            gate.release()

    # ── Scenario G: Architect ────────────────────────────────────

    def run_architect(self) -> Optional[Dict[str, Any]]:
        """Analyze codebase structure and propose architectural improvements.

        Steps:
          1. Load atlas (module structure, hub files, cross-cutting concerns)
          2. Run audit scan for architecture-category findings
          3. Combine into an architecture assessment
          4. Save assessment as observation

        Returns assessment dict or None.
        Time budget: ~10s (pure Python analysis — LLM synthesis deferred)
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="architect"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi architect: starting architecture assessment")

            results: Dict[str, Any] = {
                "module_count": 0,
                "hub_files": [],
                "arch_findings": [],
                "assessment": "unknown",
            }

            # Step 1: Load atlas for module structure
            try:
                from codrag.core.atlas import CodebaseAtlas
                atlas = CodebaseAtlas(self.index_dir)
                doc = atlas.load()
                if doc:
                    results["module_count"] = getattr(doc, "module_count", 0) or 0
                    # Extract hub files from atlas
                    if hasattr(doc, "hub_files"):
                        for hf in (doc.hub_files or [])[:10]:
                            if isinstance(hf, str):
                                results["hub_files"].append(hf)
                            elif hasattr(hf, "path"):
                                results["hub_files"].append(str(hf.path))
            except Exception:
                logger.debug("Pi architect: atlas load failed", exc_info=True)

            # Step 2: Get architecture-specific audit findings
            current = self._get_current_scan_summary()
            if current:
                arch_findings = [
                    f for f in current.get("findings", [])
                    if f.get("category") in ("architecture", "quality")
                ]
                results["arch_findings"] = arch_findings[:20]  # Cap at 20

            # Step 3: Simple heuristic assessment
            arch_count = len(results["arch_findings"])
            module_count = results["module_count"]

            if arch_count == 0:
                results["assessment"] = "healthy"
            elif arch_count <= 5:
                results["assessment"] = "minor_concerns"
            elif arch_count <= 15:
                results["assessment"] = "needs_attention"
            else:
                results["assessment"] = "significant_issues"

            # Add module health context
            if module_count > 0:
                results["findings_per_module"] = round(arch_count / module_count, 1)

            elapsed = time.monotonic() - start
            logger.info(
                "Pi architect: complete in %.1fs — %d modules, %d arch findings, assessment=%s",
                elapsed, module_count, arch_count, results["assessment"],
            )

            # Save assessment observation
            self._save_observation(
                content=(
                    f"Architect assessment: {results['assessment']}. "
                    f"{module_count} modules, {arch_count} architecture findings. "
                    f"Hub files: {', '.join(results['hub_files'][:5]) or 'none detected'}."
                ),
                category="agent_scan",
                scenario="pi/architect",
            )
            self._log_activity(
                "architect", "assessment_complete",
                f"{results['assessment']}: {module_count} modules, {arch_count} findings",
            )

            return results

        finally:
            gate.release()

    # ── Scenario H: Scholar ──────────────────────────────────────

    def run_scholar(self) -> Optional[Dict[str, Any]]:
        """Monitor enrichment quality: check for gaps in deep enrichment data.

        Steps:
          1. Check enrichment data files for completeness
          2. Compare enriched node count vs total node count
          3. Check for enrichment-specific audit findings
          4. Save quality report as observation

        Returns quality report dict or None.
        Time budget: ~10s (pure Python file inspection)
        """
        self._reload_config()
        if not self._enabled:
            return None

        from codrag.services.agent_gate import get_agent_gate
        gate = get_agent_gate()
        if not gate.can_run(self.project_id, task_name="scholar"):
            return None

        try:
            start = time.monotonic()
            logger.info("Pi scholar: starting enrichment quality check")

            results: Dict[str, Any] = {
                "total_nodes": 0,
                "augmented_nodes": 0,
                "epistemic_nodes": 0,
                "clustered_modules": 0,
                "coverage": {},
                "quality_issues": [],
            }

            # Step 1: Count nodes in trace manifest
            try:
                trace_manifest = self.index_dir / "trace_manifest.json"
                if trace_manifest.exists():
                    manifest = json.loads(trace_manifest.read_text(encoding="utf-8"))
                    results["total_nodes"] = manifest.get("counts", {}).get("nodes", 0)
            except Exception:
                pass

            # Step 2: Count entries in enrichment data files
            enrichment_files = {
                "augmented_nodes": "trace_augmented.jsonl",
                "epistemic_nodes": "trace_epistemic.jsonl",
                "clustered_modules": "trace_modules.jsonl",
            }
            for key, filename in enrichment_files.items():
                filepath = self.index_dir / filename
                if filepath.exists():
                    try:
                        count = 0
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    count += 1
                        results[key] = count
                    except Exception:
                        pass

            # Step 3: Compute coverage percentages
            total = results["total_nodes"]
            if total > 0:
                results["coverage"] = {
                    "augmentation": round(results["augmented_nodes"] / total * 100, 1),
                    "epistemic": round(results["epistemic_nodes"] / total * 100, 1),
                }

                # Check for coverage gaps
                aug_pct = results["coverage"]["augmentation"]
                epi_pct = results["coverage"]["epistemic"]

                if aug_pct < 50:
                    results["quality_issues"].append(
                        f"Augmentation coverage low ({aug_pct}%) — many files lack descriptions"
                    )
                if epi_pct < 30:
                    results["quality_issues"].append(
                        f"Epistemic coverage low ({epi_pct}%) — deep enrichment may not have run"
                    )
                if results["clustered_modules"] == 0 and total > 50:
                    results["quality_issues"].append(
                        "No module clustering data — clustering stage has not run"
                    )

            # Step 4: Check for enrichment-related audit findings
            current = self._get_current_scan_summary()
            if current:
                coverage_findings = [
                    f for f in current.get("findings", [])
                    if f.get("category") == "coverage"
                ]
                if coverage_findings:
                    results["quality_issues"].append(
                        f"{len(coverage_findings)} coverage-related audit findings"
                    )

            elapsed = time.monotonic() - start
            issue_count = len(results["quality_issues"])
            logger.info(
                "Pi scholar: complete in %.1fs — %d nodes, aug=%.0f%%, epi=%.0f%%, %d quality issues",
                elapsed,
                total,
                results["coverage"].get("augmentation", 0),
                results["coverage"].get("epistemic", 0),
                issue_count,
            )

            # Save quality report observation
            self._save_observation(
                content=(
                    f"Scholar quality report: {total} total nodes. "
                    f"Augmentation: {results['coverage'].get('augmentation', 0)}%, "
                    f"Epistemic: {results['coverage'].get('epistemic', 0)}%, "
                    f"Modules: {results['clustered_modules']}. "
                    + (f"Issues: {'; '.join(results['quality_issues'][:3])}" if results["quality_issues"] else "No issues.")
                ),
                category="agent_scan",
                scenario="pi/scholar",
            )
            self._log_activity(
                "scholar", "quality_report_complete",
                f"{issue_count} issues, aug={results['coverage'].get('augmentation', 0)}%",
            )

            return results

        finally:
            gate.release()

    # ── Phase 65: PM Auto-Push ───────────────────────────────────

    def _try_auto_push(self) -> None:
        """Push consolidated findings to PM tool if auto-push is configured.

        Called after Watchdog detects changes. Only runs when:
          1. pm_push.enabled is True
          2. pm_push.auto_push is True
          3. pm_push.push_cadence is "on_scan"

        Errors are caught and logged — they never block the watchdog.
        """
        try:
            from codrag.services.settings_store import settings
            pm_config = settings.get("pm_push")
            if not pm_config or not isinstance(pm_config, dict):
                return

            if not pm_config.get("enabled") or not pm_config.get("auto_push"):
                return

            if pm_config.get("push_cadence") != "on_scan":
                return

            logger.info("Pi watchdog: auto-push triggered (cadence=on_scan)")

            # Load current opportunities
            from codrag.core.audit.opportunity_manager import OpportunityManager
            mgr = OpportunityManager(self.index_dir)
            items = mgr.get_opportunities()

            if not items:
                logger.info("Pi watchdog: no items to push")
                return

            # Create push engine and push
            from codrag.adapters.pm_models import PMPushConfig
            from codrag.adapters.push_engine import PushEngine, create_push_engine

            config = PMPushConfig.from_dict(pm_config)
            engine = create_push_engine(config)

            result = engine.push(
                items,
                codrag_project_id=self.project_id,
                strategy=config.consolidation_strategy,
                min_priority=config.min_priority,
                exclude_categories=config.exclude_categories or None,
                project_root=str(self.project_root) if self.project_root else "",
            )

            # Record push history
            PushEngine.record_push(self.index_dir, result, provider=config.provider)

            logger.info(
                "Pi watchdog: auto-push complete — %d issues created, %d updated, %d errors",
                result.issues_created,
                result.issues_updated,
                len(result.errors),
            )

        except Exception:
            logger.warning("Pi watchdog: auto-push failed (non-fatal)", exc_info=True)

    # ── Status & API ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return agent status for API/dashboard."""
        self._reload_config()
        with self._lock:
            running_task = self._running_task
        return {
            "enabled": self._enabled,
            "auto_scan": self._auto_scan,
            "cooldown_seconds": self._cooldown_seconds,
            "running_task": running_task,
            "last_scan_at": (
                datetime.fromtimestamp(self._last_watchdog_at, tz=timezone.utc).isoformat()
                if self._last_watchdog_at > 0 else None
            ),
            "last_scan_delta": self._last_scan_delta,
        }

    # ── Internal Helpers ─────────────────────────────────────────

    def _get_current_scan_summary(self) -> Optional[Dict[str, Any]]:
        """Run audit scan and return a summary dict.

        Uses the same audit runner as codrag_audit(action="scan").
        Pure Python, no LLM, takes ~2-5 seconds.
        """
        try:
            from codrag.core.audit.runner import run_audit
            result = run_audit(
                index_dir=self.index_dir,
                project_root=self.project_root,
            )

            # Guard: never process more than MAX_FINDINGS_PER_CALL
            findings_list = []
            for f in result.findings[:self.MAX_FINDINGS_PER_CALL]:
                findings_list.append({
                    "finding_id": getattr(f, "finding_id", None) or f"{getattr(f, 'analyzer', 'unknown')}_{len(findings_list)}",
                    "analyzer": getattr(f, "analyzer", "unknown"),
                    "severity": getattr(f, "severity", "info"),
                    "title": getattr(f, "title", ""),
                    "file_paths": getattr(f, "file_paths", [])[:3],  # Cap file list
                    "category": getattr(f, "category", ""),
                })

            return {
                "total_findings": len(result.findings),
                "findings": findings_list,
                "errors": result.errors[:5],  # Cap error list
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            logger.exception("Pi: audit scan failed")
            return None

    def _get_previous_scan_summary(self) -> Optional[Dict[str, Any]]:
        """Load the previous scan summary from observations."""
        try:
            from codrag.services.observation_store import observation_store
            obs_list = observation_store.get_for_query(
                project_id=self.project_id,
                query="pi_scan_baseline",
                limit=1,
            )
            if obs_list:
                content = obs_list[0].content
                # Strip the [pi_scan_baseline] tag prefix
                if content.startswith("["):
                    content = content.split("]", 1)[1].strip()
                try:
                    return json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    return None
            return None
        except Exception:
            return None

    def _compute_delta(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute the diff between current and previous scan summaries."""
        if not previous:
            # First scan ever — everything is "new"
            return {
                "new_findings": current.get("findings", []),
                "resolved_findings": [],
                "unchanged_count": 0,
                "is_first_scan": True,
            }

        # Build lookup by (analyzer, title) for stable comparison
        current_keys = {
            (f["analyzer"], f.get("title", "")): f
            for f in current.get("findings", [])
        }
        previous_keys = {
            (f.get("analyzer", ""), f.get("title", "")): f
            for f in previous.get("findings", [])
        }

        new_findings = [
            f for key, f in current_keys.items()
            if key not in previous_keys
        ]
        resolved_findings = [
            f for key, f in previous_keys.items()
            if key not in current_keys
        ]
        unchanged_count = len(current_keys) - len(new_findings)

        return {
            "new_findings": new_findings,
            "resolved_findings": resolved_findings,
            "unchanged_count": max(0, unchanged_count),
            "is_first_scan": False,
        }

    def _save_scan_summary(self, summary: Dict[str, Any]) -> None:
        """Save the current scan summary as the baseline for next comparison."""
        self._save_observation(
            content=json.dumps(summary, default=str),
            category="agent_scan",
            query_tag="pi_scan_baseline",
            scenario="pi/watchdog",
        )

    def _save_delta_observation(self, delta: Dict[str, Any], group: str) -> None:
        """Save a human-readable delta observation."""
        new_count = len(delta["new_findings"])
        resolved_count = len(delta["resolved_findings"])

        parts = []
        if new_count:
            top_new = delta["new_findings"][:5]
            new_titles = [f.get("title", f.get("analyzer", "?")) for f in top_new]
            parts.append(f"+{new_count} new: {', '.join(new_titles)}")
        if resolved_count:
            top_resolved = delta["resolved_findings"][:5]
            resolved_titles = [f.get("title", f.get("analyzer", "?")) for f in top_resolved]
            parts.append(f"-{resolved_count} resolved: {', '.join(resolved_titles)}")

        content = (
            f"Watchdog delta (post-{group}): "
            + " | ".join(parts)
            + f" | {delta['unchanged_count']} unchanged"
        )

        self._save_observation(
            content=content, category="agent_scan",
            scenario="pi/watchdog",
        )
        self._log_activity("watchdog", "delta_scan_complete", content)
        self._capture_graph_snapshot()

    def _capture_graph_snapshot(self) -> None:
        """Capture current graph state for structural delta computation."""
        if not self._collab:
            return
        try:
            from codrag.core.trace import TraceIndex
            trace_path = self.index_dir / "trace_index.json"
            if not trace_path.exists():
                return
            ti = TraceIndex(self.index_dir)
            ti.load()
            # Extract hub files
            hub_data = ti.hub_files(k=15)
            hubs = [
                {
                    "path": h.get("path", ""),
                    "dependents_count": h.get("in_degree", 0),
                    "rank": i + 1,
                }
                for i, h in enumerate(hub_data)
                if isinstance(h, dict) and h.get("path")
            ]
            # Extract modules from clusters
            modules = []
            if hasattr(ti, "get_clusters"):
                for cluster in (ti.get_clusters() or []):
                    if isinstance(cluster, dict):
                        modules.append({
                            "name": cluster.get("name", ""),
                            "file_count": len(
                                cluster.get("member_files", [])
                            ),
                        })
            self._collab.snapshots.capture(
                self.project_id, hubs=hubs, modules=modules,
            )
        except Exception:
            logger.debug(
                "Pi: graph snapshot capture failed (non-fatal)",
                exc_info=True,
            )

    def _save_observation(
        self,
        content: str,
        category: str = "note",
        query_tag: Optional[str] = None,
        scenario: Optional[str] = None,
    ) -> None:
        """Save an observation via the observation store.

        Category must be one of: note, decision, bug, pattern, assumption.
        Agent observations use 'note' category with content-level tagging.
        """
        try:
            from codrag.services.observation_store import observation_store
            # Tag with query_tag in the content for later retrieval
            if query_tag:
                tagged = f"[{query_tag}] {content}"
            else:
                tagged = content

            observation_store.save(
                self.project_id,
                tagged,
                category="note",
                created_by=scenario or "pi",
            )
        except Exception:
            logger.debug("Pi: failed to save observation", exc_info=True)

    def _log_activity(
        self, scenario: str, action: str, summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an activity entry if collaboration hub is available."""
        if self._collab:
            try:
                self._collab.activity.log(
                    self.project_id, f"pi/{scenario}",
                    action, summary, details=details,
                )
            except Exception:
                logger.debug("Pi: failed to log activity", exc_info=True)


# ── Module-level singleton ───────────────────────────────────────
_pi_agent: Optional[PiAgent] = None


def get_pi_agent() -> Optional[PiAgent]:
    """Return the Pi agent singleton, or None if not initialized."""
    return _pi_agent


def init_pi_agent(
    project_id: str,
    index_dir: Path,
    project_root: Optional[Path] = None,
    collab_hub: Optional[Any] = None,
) -> PiAgent:
    """Initialize the Pi agent singleton."""
    global _pi_agent
    _pi_agent = PiAgent(
        project_id=project_id,
        index_dir=index_dir,
        project_root=project_root,
        collab_hub=collab_hub,
    )
    logger.info("Pi agent initialized for project %s (enabled=%s)", project_id, _pi_agent._enabled)
    return _pi_agent
