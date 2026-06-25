"""PR-S (§9.3 #32) — DEEPENING worker adoption of the orchestrator
override contract.

Closes PRQ-CSI-002 from PR-Q round-1 scrutiny.

PR-S original scope: emit `_expected_total` and `_processed_count`
keys from the DEEPENING worker so the orchestrator helper
`_apply_worker_quality_overrides` hoists them into manifest.quality.

PR-S-fixup-r1 corrections (round-1 scrutiny):
  - Extract `_compute_deepening_override_keys` module-level helper.
  - Prefer DeepeningResult.convergence (this-run native metric) over
    JSONL-derived counts. Without this the chip read 100% the moment
    ENRICHMENT completed because the cumulative jsonl already had
    every file's epistemic entry.
  - Apply empty-file filter on fallback path (matches ENRICHMENT's
    PR-Q-fixup-r1 scope so the two chips share a denominator).
  - Apply pass_number>=3 filter on fallback path (excludes
    ENRICHMENT-only entries written with pass_number=2).
  - Narrowed except clause + WARNING log + telemetry event.

This file pins BOTH the source-level wiring (regex pins on the
worker calling the helper) AND the functional behavior of the helper
itself (mock enricher + mock DeepeningResult).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────
# Source-level wiring pins.
# ─────────────────────────────────────────────────────────────────


class TestDeepeningWorkerWiresHelper:
    """The DEEPENING worker must route override-key computation through
    `_compute_deepening_override_keys` (the PR-S-fixup-r1 helper) and
    must emit the override keys into worker_result. Source-regex
    pins; functional behavior covered by TestComputeDeepeningOverrideKeys.
    """

    def _workers_body(self) -> str:
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        return src_path.read_text(encoding="utf-8")

    def _deepening_region(self) -> str:
        body = self._workers_body()
        idx = body.index("def _deepening_worker(")
        return body[idx:idx + 8000]

    def test_helper_function_exists_at_module_level(self):
        body = self._workers_body()
        assert "def _compute_deepening_override_keys(" in body, (
            "PR-S-fixup-r1 regression: the module-level helper "
            "_compute_deepening_override_keys must exist so the "
            "deepening worker AND any future skip-path fix can call "
            "the same scope+pass_number logic."
        )

    def test_deepening_worker_calls_helper(self):
        region = self._deepening_region()
        assert "_compute_deepening_override_keys(" in region, (
            "PR-S-fixup-r1 wiring regression: _deepening_worker must "
            "delegate override-key computation to "
            "_compute_deepening_override_keys (not inline). Inline "
            "computation re-introduces the FIXUP-1/FIXUP-2 bugs."
        )

    def test_deepening_worker_emits_expected_total_key(self):
        region = self._deepening_region()
        assert '"_expected_total"' in region, (
            "PR-S regression: worker_result must include "
            "_expected_total when the helper returns a positive value."
        )

    def test_deepening_worker_emits_processed_count_key(self):
        region = self._deepening_region()
        assert '"_processed_count"' in region, (
            "PR-S regression: worker_result must include "
            "_processed_count when the helper returns a value."
        )

    def test_deepening_worker_omits_keys_on_helper_failure(self):
        region = self._deepening_region()
        # Pin: the conditional `if expected_total is not None and
        # expected_total > 0` gates the assignment.
        assert "expected_total > 0" in region, (
            "PR-S regression: deepening worker must omit override "
            "keys when expected_total is 0 or computation failed."
        )

    def test_deepening_worker_logs_warning_on_helper_failure(self):
        region = self._deepening_region()
        # FIXUP-3: DEBUG → WARNING so operators see the degradation.
        assert "logger.warning(" in region, (
            "PR-S-fixup-r1 FIXUP-3 regression: failure must log at "
            "WARNING, not DEBUG. DEBUG is invisible at default INFO "
            "and the silent fallback re-introduces the §9.3 #32 bug."
        )

    def test_deepening_worker_emits_telemetry_event_on_failure(self):
        region = self._deepening_region()
        # FIXUP-3: telemetry event so the failure is introspectable
        # from the event log, not just logger output.
        assert "deepening_override_failed" in region, (
            "PR-S-fixup-r1 FIXUP-3 regression: failure must emit a "
            "telemetry event so operators can diagnose without grepping "
            "logger output."
        )

    def test_skip_path_documents_known_gap(self):
        region = self._deepening_region()
        # FIXUP-5: skip path is a known leak; must be documented inline
        # so a future reader knows the gap is intentional, not missed.
        assert "FIXUP-5" in region or "no_llm" in region, (
            "PR-S-fixup-r1 FIXUP-5 regression: skip-path gap must be "
            "documented inline. Otherwise a future reader thinks the "
            "skip path emits override keys (it does not) and won't "
            "trace down the silent JSONL-fallback bug there."
        )


# ─────────────────────────────────────────────────────────────────
# Functional pins on _compute_deepening_override_keys.
# These are NOT source-regex — they exercise real behavior.
# ─────────────────────────────────────────────────────────────────


def _make_enricher(file_nodes_with_excerpt, existing_entries):
    """Build a mock enricher whose load_trace_nodes / load_existing /
    _get_file_excerpt return the supplied fixtures.

    file_nodes_with_excerpt: list of (node_dict, excerpt_str). excerpt
        empty-string ⇒ the empty-file filter rejects the node.
    existing_entries: dict[node_id, SimpleNamespace(pass_number=N)].
    """
    enricher = MagicMock()
    enricher.load_trace_nodes.return_value = [n for n, _ in file_nodes_with_excerpt]

    def _excerpt(file_path, max_lines=150):
        for n, ex in file_nodes_with_excerpt:
            if n.get("file_path") == file_path:
                return ex
        return ""

    enricher._get_file_excerpt.side_effect = _excerpt
    enricher.load_existing.return_value = existing_entries
    return enricher


def _entry(pass_number=2):
    return SimpleNamespace(pass_number=pass_number)


class TestComputeDeepeningOverrideKeys:
    """Functional pins on the helper. Each test states a behavioral
    contract the production deepening worker depends on.
    """

    def test_prefers_convergence_when_available(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # Even with a deeply-orphaned jsonl, convergence wins.
        enricher = _make_enricher(
            file_nodes_with_excerpt=[],
            existing_entries={},
        )
        result = SimpleNamespace(convergence={"total_count": 100, "settled_count": 75})

        total, processed = _compute_deepening_override_keys(enricher, result)
        assert total == 100
        assert processed == 75
        # The scope read must NOT have been called when convergence
        # was usable (avoids unnecessary I/O).
        enricher.load_trace_nodes.assert_not_called()
        enricher.load_existing.assert_not_called()

    def test_convergence_settled_clamped_at_total(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # Invariant: processed <= total (the §9.3 #32 invariant).
        # If convergence ever reports settled > total (would be a bug
        # in DeepeningResult itself), the helper still enforces the
        # invariant.
        enricher = _make_enricher([], {})
        result = SimpleNamespace(convergence={"total_count": 100, "settled_count": 150})

        total, processed = _compute_deepening_override_keys(enricher, result)
        assert total == 100
        assert processed == 100  # clamped, NOT 150

    def test_falls_back_to_scope_read_when_convergence_none(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n2 = {"id": "file:b.py", "kind": "file", "file_path": "b.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "real content"), (n2, "real content")],
            existing_entries={
                "file:a.py": _entry(pass_number=3),  # deepened
                "file:b.py": _entry(pass_number=2),  # enriched only
            },
        )
        result = SimpleNamespace(convergence=None)

        total, processed = _compute_deepening_override_keys(enricher, result)
        assert total == 2  # both file nodes in scope
        assert processed == 1  # only a.py has pass_number >= 3

    def test_falls_back_when_deepening_result_none(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "real")],
            existing_entries={"file:a.py": _entry(pass_number=3)},
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total == 1
        assert processed == 1

    def test_empty_file_filter_excludes_empty_init(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # FIXUP-1: empty file nodes (empty __init__.py) must be
        # excluded from the denominator. Mirrors EpistemicEnricher.run
        # (epistemic_enrichment.py:1037-1045).
        n_real = {"id": "file:real.py", "kind": "file", "file_path": "real.py"}
        n_empty = {"id": "file:__init__.py", "kind": "file", "file_path": "__init__.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n_real, "content"), (n_empty, "")],
            existing_entries={"file:real.py": _entry(pass_number=3)},
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        # Denominator = 1 (only real.py — __init__.py excluded by
        # empty-file filter; matches ENRICHMENT's denominator).
        assert total == 1
        assert processed == 1

    def test_kind_filter_excludes_non_file_nodes(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        n_file = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n_sym = {"id": "sym:Foo", "kind": "symbol", "file_path": "a.py"}
        n_sec = {"id": "sec:1", "kind": "section", "file_path": "doc.md"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[
                (n_file, "content"),
                (n_sym, "content"),
                (n_sec, "content"),
            ],
            existing_entries={"file:a.py": _entry(pass_number=3)},
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        # Only kind=="file" counted.
        assert total == 1

    def test_pass_number_filter_excludes_enrichment_only_entries(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # FIXUP-2 critical: the chip must NOT read 100% just because
        # ENRICHMENT completed. Three files all enriched (pass=2),
        # one re-deepened (pass=3). Chip semantic: 1/3 (33%), not
        # 3/3 (100%).
        nodes = [
            ({"id": f"file:f{i}.py", "kind": "file", "file_path": f"f{i}.py"}, "content")
            for i in range(3)
        ]
        enricher = _make_enricher(
            file_nodes_with_excerpt=nodes,
            existing_entries={
                "file:f0.py": _entry(pass_number=2),  # enrichment only
                "file:f1.py": _entry(pass_number=2),  # enrichment only
                "file:f2.py": _entry(pass_number=3),  # deepened
            },
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total == 3
        # CRITICAL FIXUP-2 assertion: pre-fixup, processed would be 3
        # (all three counted). Post-fixup, only the pass_number>=3
        # entry counts.
        assert processed == 1, (
            "FIXUP-2 regression: numerator must filter by pass_number>=3 "
            "to measure DEEPENING work, not ENRICHMENT coverage. Without "
            "the filter the chip reads 100% the moment ENRICHMENT "
            "completes regardless of deepening."
        )

    def test_pass_number_high_passes_count(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # pass_number=4, 5, etc. (multiple deepening passes) still count.
        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        n2 = {"id": "file:b.py", "kind": "file", "file_path": "b.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "real"), (n2, "real")],
            existing_entries={
                "file:a.py": _entry(pass_number=3),
                "file:b.py": _entry(pass_number=5),
            },
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total == 2
        assert processed == 2

    def test_orphan_filter_excludes_out_of_scope_entries(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # An entry for a node that's no longer in file_nodes (deleted
        # file or L3 filter change) must NOT count toward processed.
        n_current = {"id": "file:current.py", "kind": "file", "file_path": "current.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n_current, "content")],
            existing_entries={
                "file:current.py": _entry(pass_number=3),
                "file:deleted.py": _entry(pass_number=3),  # ORPHAN
                "file:also_deleted.py": _entry(pass_number=5),  # ORPHAN
            },
        )

        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total == 1
        # Orphans excluded — only the in-scope entry counts.
        assert processed == 1

    def test_returns_none_on_oserror(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = OSError("disk full")

        total, processed = _compute_deepening_override_keys(enricher, None)
        # FIXUP-3: narrowed except still catches OSError; caller
        # logs WARNING + telemetry.
        assert total is None
        assert processed is None

    def test_returns_none_on_json_decode_error(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = json.JSONDecodeError("bad", "doc", 0)

        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total is None
        assert processed is None

    def test_propagates_programmer_errors(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # FIXUP-3: bare `except Exception` was too broad — would
        # swallow TypeError / KeyboardInterrupt / SystemExit etc.
        # The narrowed clause must let real programmer errors
        # propagate so they show up in tests / monitoring.
        enricher = MagicMock()
        enricher.load_trace_nodes.side_effect = TypeError("oops")

        # TypeError NOT caught by (OSError, json.JSONDecodeError,
        # ValueError, AttributeError). Wait — AttributeError IS caught.
        # TypeError is NOT in the tuple, so it propagates.
        import pytest as _pytest
        with _pytest.raises(TypeError):
            _compute_deepening_override_keys(enricher, None)

    def test_zero_file_nodes_returns_zero_total(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        enricher = _make_enricher(file_nodes_with_excerpt=[], existing_entries={})
        total, processed = _compute_deepening_override_keys(enricher, None)
        assert total == 0
        assert processed == 0
        # Caller's `if expected_total > 0` gate causes the worker to
        # OMIT the override keys, falling back to JSONL semantics.

    def test_convergence_with_non_int_values_falls_back(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # Corrupt convergence dict (settled is a string, total is None).
        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "content")],
            existing_entries={"file:a.py": _entry(pass_number=3)},
        )
        result = SimpleNamespace(convergence={"total_count": None, "settled_count": "bad"})

        total, processed = _compute_deepening_override_keys(enricher, result)
        # Falls through to scope read.
        assert total == 1
        assert processed == 1

    def test_convergence_with_bool_values_falls_back(self):
        from prep.services.pipeline.workers import _compute_deepening_override_keys

        # Defense against the same F1 bug class PR-Q-fixup-r1 closed.
        n1 = {"id": "file:a.py", "kind": "file", "file_path": "a.py"}
        enricher = _make_enricher(
            file_nodes_with_excerpt=[(n1, "content")],
            existing_entries={"file:a.py": _entry(pass_number=3)},
        )
        result = SimpleNamespace(convergence={"total_count": True, "settled_count": True})

        total, processed = _compute_deepening_override_keys(enricher, result)
        # Bools rejected → scope read fallback.
        assert total == 1
        assert processed == 1


# NOTE: producer-only scope.
# The consumer-side contract (orchestrator helper reading the same
# keys) is intentionally NOT pinned here because PR-S branches off
# main while the consumer (PR-Q's _apply_worker_quality_overrides)
# is on an independent branch. When both PRs merge to main, the
# producer-consumer end-to-end behavior is covered by
# test_phase145_pr_q_quality_overrides.py's
# TestPRQEndToEndProducerConsumer (which exercises the real
# enricher→helper path). Extending that test to also cover the
# deepening worker is a logical follow-up after both branches land.
#
# If PR-S is merged WITHOUT PR-Q (against the recommended sequence),
# the deepening worker emits keys that nobody reads — dormant code,
# not a regression. Safe failure mode.
