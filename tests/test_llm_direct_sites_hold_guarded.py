"""P127-F2 contract: every LLM-direct ``llm.generate`` call must be
hold-guarded.

These sites bypass SwarmOrchestrator's phase-boundary hold checks
because they call llm.generate directly (extract / summarize /
synthesize fallbacks).  Without a per-call hold check, a project
entering exclusive mid-call gets unguarded dispatch.

The contract for each enclosing function:

  1. A hold-check call (``hold_paused_for_llm`` or ``self._hold_paused``
     or ``self._raise_hold_paused``) appears as a statement at the
     function level BEFORE the first ``llm.generate`` call.

  2. If the ``llm.generate`` call sits inside a ``try`` whose handlers
     include ``except Exception`` (catch-all), there must also be an
     ``except HoldPausedError`` handler that re-raises (``raise``)
     so the pause signal isn't downgraded to a generic "LLM failed"
     warning.

The check is structural (AST), not behavioral, so the contract is
caught even when the runtime path isn't exercised by other tests.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

import pytest

import prep.core.cluster as cluster_mod
import prep.core.group_reasoning as group_reasoning_mod
import prep.core.atlas.generator as atlas_generator_mod
import prep.core.concept_seeder as concept_seeder_mod


_HOLD_CHECK_FN_NAMES = {
    "hold_paused_for_llm",
    "raise_hold_paused_for_llm",
    "_hold_paused",
    "_raise_hold_paused",
}


def _is_llm_generate_call(call: ast.Call) -> bool:
    """Return True if ``call`` is ``llm.generate(...)`` (or
    ``self.llm.generate(...)`` / ``self.worker_llm.generate(...)``).
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "generate":
        return False
    # The receiver is either a bare Name (``llm``) or an Attribute
    # whose final segment is an ``llm``-flavored field.
    receiver = func.value
    if isinstance(receiver, ast.Name) and receiver.id in {"llm", "self"}:
        return receiver.id == "llm"
    if isinstance(receiver, ast.Attribute) and receiver.attr in {
        "llm", "worker_llm", "coordinator_llm",
    }:
        return True
    return False


def _is_hold_check_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id in _HOLD_CHECK_FN_NAMES:
        return True
    if isinstance(func, ast.Attribute) and func.attr in _HOLD_CHECK_FN_NAMES:
        return True
    return False


def _iter_calls(tree: ast.AST) -> Iterable[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _enclosing_function(tree: ast.AST, lineno: int) -> ast.AST | None:
    """Return the innermost FunctionDef containing ``lineno``."""
    best: ast.AST | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                # Prefer the innermost (largest start line).
                if best is None or node.lineno > best.lineno:  # type: ignore[union-attr]
                    best = node
    return best


def _enclosing_try(tree: ast.AST, lineno: int) -> ast.Try | None:
    """Return the innermost Try containing ``lineno``, or None."""
    best: ast.Try | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                if best is None or node.lineno > best.lineno:
                    best = node
    return best


def _try_catches_generic_exception(node: ast.Try) -> bool:
    for h in node.handlers:
        if h.type is None:
            return True
        if isinstance(h.type, ast.Name) and h.type.id in {"Exception", "BaseException"}:
            return True
    return False


def _try_has_hold_pause_reraise(node: ast.Try) -> bool:
    """True if a handler catches HoldPausedError and re-raises it."""
    for h in node.handlers:
        t = h.type
        is_hold = (
            (isinstance(t, ast.Name) and t.id == "HoldPausedError")
            or (isinstance(t, ast.Attribute) and t.attr == "HoldPausedError")
        )
        if not is_hold:
            continue
        for stmt in h.body:
            if isinstance(stmt, ast.Raise) and stmt.exc is None:
                return True
        # Some carve-outs may re-raise via ``raise hpe`` — accept that too.
        for stmt in h.body:
            if isinstance(stmt, ast.Raise):
                return True
    return False


def _hold_check_reaches_call(func: ast.AST, call: ast.Call) -> bool:
    """True if a hold-check call appears in ``func`` strictly before
    the line of ``call`` AND in the same control-flow lineage (i.e.,
    same function body or any ancestor block reaching the call).

    Simplified: any hold-check whose line is below the function's
    start and above ``call.lineno`` counts.  Closures inside the
    function are not crawled — that's fine here because the hold
    check sits at the same nesting level as the generate call in
    the existing EpistemicEnricher pattern.
    """
    target_line = call.lineno
    for inner in ast.walk(func):
        if isinstance(inner, ast.Call) and _is_hold_check_call(inner):
            if inner.lineno < target_line:
                return True
    return False


# ── Catalog of every LLM-direct site (file, lineno) ────────────


F2_SITES: list[tuple[object, int]] = [
    # cluster.py — ClusterSynthesizer.  Five direct dispatch sites.
    (cluster_mod, 1301),
    (cluster_mod, 1444),
    (cluster_mod, 1479),
    (cluster_mod, 1517),
    (cluster_mod, 1846),
    # atlas/generator.py — CodebaseAtlas.  Four direct dispatch sites.
    (atlas_generator_mod, 256),
    (atlas_generator_mod, 579),
    (atlas_generator_mod, 728),
    (atlas_generator_mod, 889),
    # group_reasoning.py — GroupReasoningEngine.  Two direct dispatch sites.
    (group_reasoning_mod, 484),
    (group_reasoning_mod, 773),
    # concept_seeder.py — module-level workers + a free helper.
    (concept_seeder_mod, 217),
    (concept_seeder_mod, 809),
    (concept_seeder_mod, 1278),
]


def _id(item: tuple[object, int]) -> str:
    mod, lineno = item
    return f"{mod.__name__}:{lineno}"


@pytest.mark.parametrize("site", F2_SITES, ids=_id)
def test_llm_generate_site_is_hold_guarded(site):
    """Each catalogued ``llm.generate`` site must (a) be preceded by a
    hold check in its enclosing function and (b) if wrapped in a try
    catching Exception, re-raise HoldPausedError.

    NOTE: line numbers are pinned to the catalog above.  If a future
    refactor renumbers lines, update F2_SITES.  The structural
    invariant (hold check + carve-out) is what we're guarding — the
    catalog is the index.
    """
    mod, lineno = site
    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)

    # Find the llm.generate call AT (or nearest after) the catalogued line.
    target: ast.Call | None = None
    for c in _iter_calls(tree):
        if not _is_llm_generate_call(c):
            continue
        if c.lineno == lineno:
            target = c
            break
    assert target is not None, (
        f"{mod.__name__}:{lineno} — expected an llm.generate call at this "
        f"line; line numbers in the F2 catalog must match the source."
    )

    func = _enclosing_function(tree, lineno)
    assert func is not None, (
        f"{mod.__name__}:{lineno} — could not find enclosing function"
    )

    # (a) hold check reaches the call within the function's scope.
    assert _hold_check_reaches_call(func, target), (
        f"{mod.__name__}:{lineno} — no hold-check call "
        f"(hold_paused_for_llm / _hold_paused) found before this "
        f"llm.generate inside function {getattr(func, 'name', '<?>')}.  "
        f"Add `if hold_paused_for_llm(...): raise_hold_paused_for_llm(...)` "
        f"or equivalent immediately before the dispatch."
    )

    # (b) carve-out: if a try with `except Exception` wraps this call,
    # there must also be `except HoldPausedError: raise` so the pause
    # isn't downgraded.
    try_node = _enclosing_try(tree, lineno)
    if try_node is None:
        return
    if not _try_catches_generic_exception(try_node):
        return
    assert _try_has_hold_pause_reraise(try_node), (
        f"{mod.__name__}:{lineno} — surrounding try (line {try_node.lineno}) "
        f"catches Exception generically.  Add `except HoldPausedError: raise` "
        f"before the existing except so HoldPausedError survives."
    )
