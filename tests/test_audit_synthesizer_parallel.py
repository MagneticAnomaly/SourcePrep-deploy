"""Phase 96F.2: Tests for audit Tier 2 parallel synthesis.

Verifies that AuditSynthesizer.synthesize_all routes to parallel
execution when concurrency > 1, and that document order is preserved
regardless of completion order.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from prep.core.audit.models import (
    AuditContext, AuditDocument, AuditResult, Finding,
)
from prep.core.audit.synthesizer import AuditSynthesizer


# ── Helpers ──────────────────────────────────────────────────────


def _empty_context() -> AuditContext:
    """Build a minimal AuditContext for testing.

    All fields are factory-defaulted; we just need an instance the
    generators can be passed.  Tests mock the generators so they never
    actually inspect the context.
    """
    return AuditContext()


def _empty_result() -> AuditResult:
    return AuditResult(findings=[], errors=[], duration_ms=0.0)


# ── Sequential vs parallel routing ───────────────────────────────


class TestSynthesisRouting:
    """synthesize_all should route to parallel when concurrency > 1."""

    def test_concurrency_none_uses_sequential(self):
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")
        synth._synthesize_sequential = MagicMock(return_value=[])
        synth._synthesize_parallel = MagicMock(return_value=[])

        synth.synthesize_all(_empty_result(), _empty_context())

        synth._synthesize_sequential.assert_called_once()
        synth._synthesize_parallel.assert_not_called()

    def test_concurrency_one_uses_sequential(self):
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")
        synth._synthesize_sequential = MagicMock(return_value=[])
        synth._synthesize_parallel = MagicMock(return_value=[])

        synth.synthesize_all(_empty_result(), _empty_context(), concurrency=1)

        synth._synthesize_sequential.assert_called_once()
        synth._synthesize_parallel.assert_not_called()

    def test_concurrency_gt_one_uses_parallel(self):
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")
        synth._synthesize_sequential = MagicMock(return_value=[])
        synth._synthesize_parallel = MagicMock(return_value=[])

        synth.synthesize_all(_empty_result(), _empty_context(), concurrency=5)

        synth._synthesize_parallel.assert_called_once()
        synth._synthesize_sequential.assert_not_called()


# ── Parallel synthesis correctness ───────────────────────────────


class TestParallelSynthesis:
    """Verify _synthesize_parallel preserves order and runs in parallel."""

    def test_parallel_preserves_document_order(self):
        """Documents must come back in the same order as the generators
        list, regardless of completion order."""
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")

        # Patch _run_generator to return documents tagged with the name
        def fake_run_generator(name, title, gen_fn, result, ctx):
            # Slow down later generators so they finish out of order
            order_map = {
                "AUDIT_SUMMARY": 0.05,
                "ARCHITECTURE_ANALYSIS": 0.01,
                "GAP_ANALYSIS": 0.04,
                "COMPONENT_INVENTORY": 0.02,
                "TECH_DEBT_REPORT": 0.03,
            }
            time.sleep(order_map.get(name, 0))
            return AuditDocument(
                name=name,
                title=title,
                content=f"content for {name}",
                generated_at="2026-04-11T00:00:00",
                finding_count=0,
                char_count=20,
            )

        synth._run_generator = fake_run_generator

        docs = synth.synthesize_all(
            _empty_result(), _empty_context(), concurrency=5,
        )

        assert len(docs) == 5
        # Order must match the generators list, not completion order
        expected = [
            "AUDIT_SUMMARY",
            "ARCHITECTURE_ANALYSIS",
            "GAP_ANALYSIS",
            "COMPONENT_INVENTORY",
            "TECH_DEBT_REPORT",
        ]
        assert [d.name for d in docs] == expected

    def test_parallel_speedup_vs_sequential(self):
        """Parallel execution should be substantially faster than
        sequential when each generator has nontrivial latency."""
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")

        def slow_run_generator(name, title, gen_fn, result, ctx):
            time.sleep(0.05)  # 50ms per generator
            return AuditDocument(
                name=name, title=title, content="x",
                generated_at="t", finding_count=0, char_count=1,
            )

        synth._run_generator = slow_run_generator

        # Sequential: 5 × 50ms = ~250ms
        t0 = time.monotonic()
        synth.synthesize_all(_empty_result(), _empty_context(), concurrency=1)
        seq_time = time.monotonic() - t0

        # Parallel: max(50ms × 5/5) = ~50ms (plus overhead)
        t0 = time.monotonic()
        synth.synthesize_all(_empty_result(), _empty_context(), concurrency=5)
        par_time = time.monotonic() - t0

        # Parallel should be at least 2.5x faster (allowing overhead)
        assert par_time < seq_time / 2.5, (
            f"Parallel ({par_time:.3f}s) not faster than sequential "
            f"({seq_time:.3f}s) by 2.5x"
        )

    def test_parallel_handles_generator_failure_with_fallback(self):
        """If one generator raises, the others still complete and the
        failing one returns a structural fallback document."""
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")

        # Mock _structural_fallback so we can detect its use
        fallback_doc = AuditDocument(
            name="GAP_ANALYSIS", title="Gap Analysis",
            content="FALLBACK", generated_at="t",
            finding_count=0, char_count=8,
        )
        synth._structural_fallback = MagicMock(return_value=fallback_doc)

        # Patch the actual generator methods so _run_generator catches
        # the exception and uses the fallback path
        def fake_gen_summary(result, ctx):
            return "summary content"
        def fake_gen_architecture(result, ctx):
            return "arch content"
        def fake_gen_gaps(result, ctx):
            raise RuntimeError("gap synth failed")
        def fake_gen_inventory(result, ctx):
            return "inv content"
        def fake_gen_tech_debt(result, ctx):
            return "tech debt content"

        synth._gen_summary = fake_gen_summary
        synth._gen_architecture = fake_gen_architecture
        synth._gen_gaps = fake_gen_gaps
        synth._gen_inventory = fake_gen_inventory
        synth._gen_tech_debt = fake_gen_tech_debt

        docs = synth.synthesize_all(
            _empty_result(), _empty_context(), concurrency=5,
        )

        # All 5 documents should be returned
        assert len(docs) == 5
        # The failing generator's slot should contain the fallback
        gap_doc = next(d for d in docs if d.name == "GAP_ANALYSIS")
        assert gap_doc.content == "FALLBACK"
        # The other 4 should be normal
        normal_docs = [d for d in docs if d.name != "GAP_ANALYSIS"]
        assert len(normal_docs) == 4
        for d in normal_docs:
            assert d.content != "FALLBACK"

    def test_parallel_respects_concurrency_cap(self):
        """When concurrency > generator count, max_workers caps at len."""
        synth = AuditSynthesizer(llm_client=MagicMock(), project_name="P")

        executor_max_workers = []

        original_pool = None
        from concurrent.futures import ThreadPoolExecutor as RealPool

        class TrackingPool(RealPool):
            def __init__(self, max_workers=None, **kwargs):
                executor_max_workers.append(max_workers)
                super().__init__(max_workers=max_workers, **kwargs)

        synth._run_generator = lambda *a, **k: AuditDocument(
            name="X", title="X", content="x",
            generated_at="t", finding_count=0, char_count=1,
        )

        import prep.core.audit.synthesizer as syn_module
        # Patch ThreadPoolExecutor in the function-local import scope
        from unittest.mock import patch
        with patch("concurrent.futures.ThreadPoolExecutor", TrackingPool):
            synth.synthesize_all(
                _empty_result(), _empty_context(), concurrency=100,
            )

        # 5 generators, concurrency=100 → max_workers should be 5
        assert executor_max_workers and executor_max_workers[0] == 5
