"""PR-S (§9.3 #32) — DEEPENING worker adoption of the orchestrator
override contract.

Closes PRQ-CSI-002 from PR-Q round-1 scrutiny. The "Continuous
Deepening" UI chip leaks the §9.3 #32 inverted ratio (numerator
> denominator) because DEEPENING and ENRICHMENT share
trace_epistemic.jsonl per stages.py STAGE_OUTPUT_FILE (lines
218/222), and the JSONL row count is cumulative across both
stages — so aggregate_quality_metrics' line-count-based
denominator is meaningless for DEEPENING.

PR-Q (commit 81a19a03) shipped the orchestrator helper
`_apply_worker_quality_overrides` that hoists worker-emitted
`_expected_total` / `_processed_count` keys into manifest.quality.
PR-Q also migrated the ENRICHMENT worker to emit those keys.
PR-S extends the same contract to the DEEPENING worker.

This test file pins the DEEPENING worker's emission via source-
regex inspection — same lightweight pattern as
TestEnrichmentWorkerEmitsOverrideKeys.test_stats_dict_includes_
override_keys (which avoided LLM dependency for the same reason
the deepening test does). The full producer→consumer behavior is
exercised in test_phase145_pr_q_quality_overrides.py via the
shared helper; PR-S contributes the producer-side wiring.
"""
from __future__ import annotations

from pathlib import Path


class TestDeepeningWorkerEmitsOverrideKeys:
    """The DEEPENING worker (workers/__init__.py:_deepening_worker)
    must emit `_expected_total` and `_processed_count` so the
    orchestrator's override path fires for DEEPENING-stage runs.

    Without these keys, manifest.quality falls back to
    aggregate_quality_metrics' JSONL-line-count semantics. Because
    DEEPENING shares trace_epistemic.jsonl with ENRICHMENT, the line
    count is cumulative and the §9.3 #32 chip-inversion bug
    re-surfaces on "Continuous Deepening" exactly as it surfaced on
    "Deep Reasoning" pre-PR-Q.
    """

    def test_deepening_worker_emits_expected_total_key(self):
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        # Pin: the deepening worker function contains the override key.
        idx = body.index("def _deepening_worker(")
        body_region = body[idx:idx + 6000]
        assert '"_expected_total"' in body_region, (
            "§9.3 #32 PR-S regression: _deepening_worker must include "
            "`_expected_total` in its returned worker_result dict so "
            "the orchestrator's _apply_worker_quality_overrides fires "
            "for DEEPENING-stage runs. Without it the 'Continuous "
            "Deepening' chip leaks the cumulative-JSONL bug "
            "(PRQ-CSI-002)."
        )

    def test_deepening_worker_emits_processed_count_key(self):
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        body_region = body[idx:idx + 6000]
        assert '"_processed_count"' in body_region, (
            "§9.3 #32 PR-S regression: _deepening_worker must include "
            "`_processed_count` in its returned worker_result dict so "
            "the orchestrator's helper can override the JSONL-derived "
            "numerator. Without it the helper falls to the JSONL clamp "
            "branch which uses cumulative line counts."
        )

    def test_deepening_worker_uses_kind_filter_for_scope(self):
        """The denominator (_expected_total) must be project-wide
        file_nodes count — same scope as ENRICHMENT (PR-Q). Pins that
        the worker filters trace_nodes by kind == 'file' rather than
        passing all nodes through.
        """
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        body_region = body[idx:idx + 6000]
        # The scope filter must use kind == "file" — same as
        # EpistemicEnricher.run() (epistemic_enrichment.py around
        # line 1040). A scope drift between ENRICHMENT and DEEPENING
        # would show inconsistent denominators on adjacent chips.
        assert 'kind"' in body_region and '"file"' in body_region, (
            "§9.3 #32 PR-S regression: deepening worker's "
            "_expected_total scope must filter trace_nodes by "
            "kind=='file' to match ENRICHMENT's scope. Inconsistent "
            "scope would show diverging denominators on the 'Deep "
            "Reasoning' and 'Continuous Deepening' chips for the same "
            "project."
        )

    def test_deepening_worker_applies_orphan_filter(self):
        """The numerator (_processed_count) must be orphan-filtered
        against current file_node_ids — same pattern as PR-Q-fixup-r1
        addressed for ENRICHMENT (PRQ-1 from PR-Q round-1 scrutiny).

        Without the filter, cumulative orphans on disk (from deleted
        files / L3 policy changes) inflate the numerator and the
        chip-inversion bug returns. The orphan filter MUST be applied
        at the worker level — relying on the orchestrator's clamp
        alone masks the symptom but leaves the worker's own counts
        inconsistent.
        """
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        body_region = body[idx:idx + 6000]
        # Source-regex pin: the in-scope filter expression must
        # appear. Same shape as
        # epistemic_enrichment.py:in_scope_enriched_count
        # (PR-Q-fixup-r1).
        assert "in file_node_ids" in body_region, (
            "§9.3 #32 PR-S regression: deepening worker's "
            "_processed_count must apply the orphan filter "
            "`if nid in file_node_ids` — same pattern as PR-Q-fixup-r1 "
            "added to EpistemicEnricher.run() (PRQ-1). Without the "
            "filter, cumulative orphans on disk inflate the numerator "
            "past the project-wide file_node count and the §9.3 #32 "
            "chip-inversion bug returns."
        )

    def test_deepening_worker_omits_keys_on_zero_or_failed_scope(self):
        """When file_nodes is empty OR the scope read raises, the
        worker must OMIT the override keys (not emit 0 or None).
        Emitting `_expected_total = 0` would trigger the orchestrator
        helper's `<= 0` early-return — equivalent to omission for
        correctness — but explicit omission is cleaner and lets the
        helper's back-compat JSONL semantics kick in unambiguously.
        """
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        body_region = body[idx:idx + 6000]
        # Pin: the conditional `if expected_total is not None and
        # expected_total > 0` gates the assignment.
        assert "expected_total > 0" in body_region, (
            "§9.3 #32 PR-S regression: deepening worker must omit "
            "the override keys when expected_total is 0 or computation "
            "failed, rather than emitting them as 0/None. The "
            "conditional ensures the orchestrator's back-compat JSONL "
            "semantics activate for degenerate scope cases."
        )

    def test_deepening_worker_has_try_except_for_scope_read(self):
        """Scope-computation failures (corrupt jsonl, missing files)
        must NOT crash the deepening worker — at this point the
        deepening loop has already completed successfully and a
        manifest-quality-accounting error should degrade silently to
        JSONL semantics.
        """
        src_path = (
            Path(__file__).parent.parent / "src" / "prep" /
            "services" / "pipeline" / "workers" / "__init__.py"
        )
        body = src_path.read_text(encoding="utf-8")
        idx = body.index("def _deepening_worker(")
        # Take a tight window around the PR-S addition.
        body_region = body[idx:idx + 6000]
        # Pin: the override-key computation is wrapped in try/except.
        # The exact phrasing isn't load-bearing, but presence of
        # try + load_trace_nodes call must coexist.
        assert "load_trace_nodes" in body_region
        assert "try:" in body_region
        # Pin: the except branch falls back without crashing.
        assert "except Exception:" in body_region


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
