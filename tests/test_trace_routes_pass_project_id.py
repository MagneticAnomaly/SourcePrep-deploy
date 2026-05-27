"""P127-F3 regression: trace_routes constructors must pass project_id.

Background: TraceAugmenter and EpistemicEnricher each accept
project_id: Optional[str] = None.  When the kwarg is omitted, the
soft-hold check inside hold_paused_for_llm short-circuits on the
``if not project_id`` guard and dispatch proceeds unrestrained — so a
user starting /augment/run or /epistemic/run on Project B while Project
A holds exclusive mode would bypass the multi-project priority gate.

The HTTP layer always has project_id in scope as a path parameter, so
the fix is just plumbing it through.  This test asserts the invariant
statically (AST inspection) so the regression is caught even before any
runtime is exercised.
"""
from __future__ import annotations

import ast
from pathlib import Path

import prep.api.routers.trace_routes.enrichment as enrichment_mod


TARGET_CLASSES = {"TraceAugmenter", "EpistemicEnricher"}


def _collect_target_constructions(source: str) -> list[ast.Call]:
    """Return every ast.Call whose func name is one of TARGET_CLASSES."""
    tree = ast.parse(source)
    hits: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Pattern: TraceAugmenter(...) or EpistemicEnricher(...)
        if isinstance(func, ast.Name) and func.id in TARGET_CLASSES:
            hits.append(node)
    return hits


def test_trace_routes_enrichment_passes_project_id_to_every_constructor():
    """Every TraceAugmenter / EpistemicEnricher call site in
    trace_routes/enrichment.py must pass project_id= as a keyword arg.
    """
    src_path = Path(enrichment_mod.__file__)
    source = src_path.read_text()
    calls = _collect_target_constructions(source)

    # Sanity: the file does construct these classes; if zero, the test
    # is silently passing for the wrong reason.
    assert len(calls) >= 3, (
        f"expected >=3 TraceAugmenter/EpistemicEnricher constructions in "
        f"{src_path}, found {len(calls)}"
    )

    missing: list[str] = []
    for call in calls:
        cls = call.func.id  # type: ignore[union-attr]
        kwarg_names = {kw.arg for kw in call.keywords}
        if "project_id" not in kwarg_names:
            missing.append(f"{cls}() at line {call.lineno} — kwargs={sorted(kwarg_names)}")

    assert not missing, (
        "trace_routes/enrichment.py constructs these without project_id=, "
        "defeating Phase 127 multi-project soft-holds:\n  - "
        + "\n  - ".join(missing)
    )
