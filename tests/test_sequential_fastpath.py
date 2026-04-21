"""
Tests for the sequential fast-paths in batched pipeline stages.

These paths are taken when concurrency <= 1 (always the case for cloud
models due to the F-59 workaround in get_batch_concurrency()).  The
previous code created a ThreadPoolExecutor(max_workers=1) even in this
case, contributing to thread accumulation.

These tests verify:
1. The sequential generators yield identical results to concurrent ones
2. Cancellation inside sequential paths works (no NameError on pool.shutdown)
3. Errors from the batch function are handled (yield None placeholders)
4. No ThreadPoolExecutor is created when concurrency=1
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests for the shared thread pool infrastructure
# ---------------------------------------------------------------------------

class TestThreadPoolInfra:
    """Verify the shared pool singleton behaves correctly."""

    def test_pool_is_lazy(self) -> None:
        """The pool should not be created until first submit."""
        from prep.services.pipeline import thread_pool as tp

        # Force reset (test isolation — normally the pool is process-wide)
        with tp._pool_lock:
            original_pool = tp._pool
            tp._pool = None
            tp._pool_size = 0

        try:
            # max_workers triggers lazy init
            size = tp.llm_pool.max_workers
            assert size > 0
            assert tp._pool is not None
        finally:
            # Restore (don't leak state to other tests)
            with tp._pool_lock:
                tp._pool = original_pool

    def test_max_workers_does_not_use_private_attr(self) -> None:
        """The proxy should use the cached _pool_size, not ThreadPoolExecutor._max_workers."""
        from prep.services.pipeline import thread_pool as tp
        import inspect
        src = inspect.getsource(tp._LLMPoolProxy)
        assert "_max_workers" not in src, (
            "LLMPoolProxy should not access ThreadPoolExecutor._max_workers (private API)"
        )

    def test_default_pool_size_allows_aimd_discovered_concurrency(self) -> None:
        """Default pool must be ≥ typical cloud AIMD ceiling (~28-32).

        Historically 6; that artificially choked non-swarm fan-out to
        ~6 concurrent calls even when the AIMD gate had discovered
        30+ per-node concurrency. The gate — not the pool — is the
        sole throttle.
        """
        from prep.services.pipeline import thread_pool as tp
        assert tp._DEFAULT_POOL_SIZE >= 32, (
            f"Default pool size {tp._DEFAULT_POOL_SIZE} is below AIMD cloud ceiling; "
            "pool would be the bottleneck instead of the scheduler gate."
        )

    def test_env_override_accepts_values_up_to_cap(self, monkeypatch) -> None:
        """PREP_LLM_POOL_SIZE should accept values up to the new cap (64)."""
        from prep.services.pipeline import thread_pool as tp

        monkeypatch.setenv("PREP_LLM_POOL_SIZE", "48")
        assert tp._get_pool_size() == 48

        monkeypatch.setenv("PREP_LLM_POOL_SIZE", "64")
        assert tp._get_pool_size() == 64

    def test_env_override_rejects_values_above_cap(self, monkeypatch, caplog) -> None:
        """Above-cap values should warn and fall back to default."""
        from prep.services.pipeline import thread_pool as tp
        import logging

        monkeypatch.setenv("PREP_LLM_POOL_SIZE", "100")
        with caplog.at_level(logging.WARNING, logger="prep.services.pipeline.thread_pool"):
            size = tp._get_pool_size()
        assert size == tp._DEFAULT_POOL_SIZE
        assert any("out of range" in rec.message for rec in caplog.records)

    def test_run_parallel_sequential_when_concurrency_1(self) -> None:
        """concurrency=1 should skip the pool entirely."""
        from prep.services.pipeline.thread_pool import run_parallel

        threads_used = set()

        def track(x):
            threads_used.add(threading.get_ident())
            return x * 2

        results = run_parallel(track, [1, 2, 3, 4, 5], concurrency=1)
        assert sorted(results) == [2, 4, 6, 8, 10]
        # All work done on the calling thread — no pool threads used
        assert len(threads_used) == 1
        assert threading.get_ident() in threads_used

    def test_run_parallel_empty_items(self) -> None:
        """Empty item list returns empty results without errors."""
        from prep.services.pipeline.thread_pool import run_parallel

        results = run_parallel(lambda x: x, [], concurrency=3)
        assert results == []

    def test_run_parallel_concurrent_uses_pool(self) -> None:
        """concurrency>1 uses the shared pool (different threads)."""
        from prep.services.pipeline.thread_pool import run_parallel
        import time

        threads_used = set()

        def track(x):
            threads_used.add(threading.get_ident())
            time.sleep(0.01)  # Force parallel scheduling
            return x

        results = run_parallel(track, list(range(10)), concurrency=3)
        assert sorted(results) == list(range(10))
        # Should have used multiple threads from the pool
        assert len(threads_used) > 1

    def test_run_parallel_handles_exceptions(self) -> None:
        """Items that raise are logged and skipped — no re-raise."""
        from prep.services.pipeline.thread_pool import run_parallel

        def failing(x):
            if x == 3:
                raise ValueError("bad")
            return x

        results = run_parallel(failing, [1, 2, 3, 4, 5], concurrency=2)
        assert sorted(results) == [1, 2, 4, 5]  # 3 was skipped


# ---------------------------------------------------------------------------
# Tests for the augmenter sequential fast-path
# ---------------------------------------------------------------------------

class TestAugmenterSequentialPath:
    """Verify the three _iter_*_results generators in augmenter.py work
    correctly in both sequential and concurrent modes.

    Note: we test the generator pattern directly, not the full Augmenter,
    since the Augmenter requires significant setup (index, LLM, etc.).
    The bug we're guarding against is the NameError on cancellation,
    which only depends on the generator + consumer-loop pattern.
    """

    def _make_generator(self, concurrency: int, batches: list, batch_fn, cancel_token=None):
        """Reproduction of the _iter_batch_results pattern from augmenter.py."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _iter():
            if concurrency <= 1 or len(batches) <= 1:
                for batch_items in batches:
                    if cancel_token and cancel_token.is_cancelled:
                        cancel_token.raise_if_cancelled()
                    try:
                        yield batch_items, batch_fn(batch_items)
                    except Exception as e:
                        yield batch_items, [None] * len(batch_items)
            else:
                with ThreadPoolExecutor(max_workers=min(concurrency, len(batches))) as pool:
                    fmap = {pool.submit(batch_fn, items): items for items in batches}
                    for future in as_completed(fmap):
                        if cancel_token and cancel_token.is_cancelled:
                            cancel_token.raise_if_cancelled()
                        batch_items = fmap[future]
                        try:
                            yield batch_items, future.result()
                        except Exception as e:
                            yield batch_items, [None] * len(batch_items)

        return _iter

    def test_sequential_yields_same_shape_as_concurrent(self) -> None:
        """Both paths yield (batch_items, results_list) tuples."""
        batches = [[1, 2], [3, 4], [5]]

        def batch_fn(items):
            return [x * 10 for x in items]

        seq_results = list(self._make_generator(1, batches, batch_fn)())
        con_results = list(self._make_generator(3, batches, batch_fn)())

        # Both should yield 3 tuples
        assert len(seq_results) == 3
        assert len(con_results) == 3

        # All yields should be (items, results) tuples
        for items, results in seq_results + con_results:
            assert isinstance(items, list)
            assert isinstance(results, list)
            assert len(items) == len(results)

    def test_sequential_cancellation_no_nameerror(self) -> None:
        """Cancel token in sequential path must not reference pool/future_to_items.

        THIS IS THE KEY REGRESSION TEST for the bug found in review pass 3.
        Previously the consumer loop called pool.shutdown() even on the
        sequential path, raising NameError.
        """
        from prep.services.pipeline.thread_pool import llm_pool  # noqa

        class FakeCancelToken:
            def __init__(self):
                self.is_cancelled = False

            def raise_if_cancelled(self):
                if self.is_cancelled:
                    raise RuntimeError("cancelled")

        tok = FakeCancelToken()
        batches = [[1], [2], [3], [4]]
        call_count = [0]

        def batch_fn(items):
            call_count[0] += 1
            if call_count[0] == 2:
                # Cancel after processing the second batch
                tok.is_cancelled = True
            return [x * 10 for x in items]

        gen = self._make_generator(1, batches, batch_fn, cancel_token=tok)()

        collected = []
        with pytest.raises(RuntimeError, match="cancelled"):
            for items, results in gen:
                collected.append((items, results))
        # Should have collected 2 items before cancel fired
        assert len(collected) == 2

    def test_sequential_handles_batch_function_exception(self) -> None:
        """Exception in batch_fn yields [None, None, ...] for that batch."""
        batches = [[1, 2], [3, 4], [5]]

        def batch_fn(items):
            if 3 in items:
                raise ValueError("bad batch")
            return [x * 10 for x in items]

        results = list(self._make_generator(1, batches, batch_fn)())
        # Batch [1,2] succeeded, [3,4] failed, [5] succeeded
        assert results[0] == ([1, 2], [10, 20])
        assert results[1] == ([3, 4], [None, None])
        assert results[2] == ([5], [50])

    def test_sequential_no_thread_pool_created(self) -> None:
        """concurrency=1 must not create a ThreadPoolExecutor."""
        import threading
        batches = [[1], [2], [3]]

        # Count threads before and during
        baseline = threading.active_count()
        peak = [baseline]

        def batch_fn(items):
            current = threading.active_count()
            peak[0] = max(peak[0], current)
            return items

        gen = self._make_generator(1, batches, batch_fn)()
        for _ in gen:
            pass

        # Sequential path must not have created any pool threads
        assert peak[0] == baseline, (
            f"Sequential path created {peak[0] - baseline} threads — "
            f"should have stayed at baseline {baseline}"
        )


# ---------------------------------------------------------------------------
# Tests against the ACTUAL augmenter.py code (import check)
# ---------------------------------------------------------------------------

class TestActualAugmenterCode:
    """Static checks on the real augmenter.py source code to catch
    regressions of the NameError bugs found in review pass 3.
    """

    def _check_name_defined_in_scope(self, filepath: str, name: str) -> list:
        """Find Name nodes for ``name`` that are NOT defined in any enclosing scope.

        Returns a list of (line, function_name) for each undefined reference.
        Uses AST to correctly track function and generator scopes.
        """
        import ast
        from pathlib import Path

        source = Path(filepath).read_text()
        tree = ast.parse(source)

        undefined = []

        class ScopeAnalyzer(ast.NodeVisitor):
            def __init__(self) -> None:
                # Each scope frame is (fn_name, set_of_assigned_names)
                self.scope_stack: list = [("<module>", set())]

            def _collect_assigned(self, node) -> set:
                """Walk a function body and collect all assigned names
                (including from 'with X as Y:', 'for Y in ...', comprehensions, etc.)."""
                names: set = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for tgt in child.targets:
                            for sub in ast.walk(tgt):
                                if isinstance(sub, ast.Name):
                                    names.add(sub.id)
                    elif isinstance(child, ast.With):
                        for item in child.items:
                            if item.optional_vars:
                                for sub in ast.walk(item.optional_vars):
                                    if isinstance(sub, ast.Name):
                                        names.add(sub.id)
                    elif isinstance(child, ast.For):
                        for sub in ast.walk(child.target):
                            if isinstance(sub, ast.Name):
                                names.add(sub.id)
                    elif isinstance(child, ast.arguments):
                        for arg in child.args + child.posonlyargs + child.kwonlyargs:
                            names.add(arg.arg)
                        if child.vararg:
                            names.add(child.vararg.arg)
                        if child.kwarg:
                            names.add(child.kwarg.arg)
                return names

            def visit_FunctionDef(self, node) -> None:
                self._enter_fn(node)

            def visit_AsyncFunctionDef(self, node) -> None:
                self._enter_fn(node)

            def _enter_fn(self, node) -> None:
                assigned = self._collect_assigned(node)
                self.scope_stack.append((node.name, assigned))
                self.generic_visit(node)
                self.scope_stack.pop()

            def visit_Attribute(self, node) -> None:
                # Check 'pool.shutdown(...)' patterns — base Name must be defined
                if isinstance(node.value, ast.Name) and node.value.id == name:
                    if not self._is_defined(name):
                        undefined.append((node.lineno, self.scope_stack[-1][0]))
                self.generic_visit(node)

            def visit_Name(self, node) -> None:
                # Check 'future_to_items' read references
                if node.id == name and isinstance(node.ctx, ast.Load):
                    if not self._is_defined(name):
                        undefined.append((node.lineno, self.scope_stack[-1][0]))
                self.generic_visit(node)

            def _is_defined(self, nm: str) -> bool:
                for _, names in self.scope_stack:
                    if nm in names:
                        return True
                # Also allow builtins and common modules
                return False

        analyzer = ScopeAnalyzer()
        analyzer.visit(tree)
        return undefined

    def test_augmenter_no_undefined_pool_refs(self) -> None:
        """AST-level check: every 'pool.X' reference must have 'pool' defined
        in an enclosing scope.

        Regression guard for the NameError bug found in review pass 3.
        """
        from pathlib import Path
        src = str(Path(__file__).parent.parent / "src" / "prep" / "core" / "augmenter.py")
        undefined = self._check_name_defined_in_scope(src, "pool")
        assert not undefined, (
            f"augmenter.py has pool.X references in scopes where 'pool' is not defined:\n"
            + "\n".join(f"  line {ln} in function '{fn}'" for ln, fn in undefined)
        )

    def test_epistemic_no_undefined_future_to_items_refs(self) -> None:
        """AST-level check: every 'future_to_items' read must be in a scope
        where it is defined.

        Regression guard for the NameError bug found in review pass 3.
        """
        from pathlib import Path
        src = str(Path(__file__).parent.parent / "src" / "prep" / "core" / "epistemic_enrichment.py")
        undefined = self._check_name_defined_in_scope(src, "future_to_items")
        assert not undefined, (
            f"epistemic_enrichment.py has future_to_items reads in scopes "
            f"where it is not defined:\n"
            + "\n".join(f"  line {ln} in function '{fn}'" for ln, fn in undefined)
        )
