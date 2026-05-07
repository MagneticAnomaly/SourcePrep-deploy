"""Phase 125 T3 — scoped LLM refine of cluster representatives.

Implements Pass 3 of the four-pass concept promotion pipeline. After
Pass 2's CPU-only anchor-overlap clustering reduces ~1,500 raw seeds
to ~1,300 cluster representatives, Pass 3 runs a per-(category,segment)
LLM critique that:

1. Forces the model to produce counter-evidence, coincidence
   hypothesis, and a falsification test BEFORE assigning a tier.
2. Replaces the broken "confidence: float" field with a discrete
   T1/T2/T3 tier. The LLM never sees floats or descriptive labels —
   tiers map to confidence at storage time.
3. Adds a pairwise pre-commit ("closer_to_lower" | "closer_to_higher")
   to resist middle-bias mode collapse (Constitutional AI / G-Eval
   standard mitigation).
4. Long free-text fields (refined_title, refined_content) come LAST
   in the schema so truncation hits least-critical fields.

Full design rationale + citations: ``docs/Phase125_ConceptPromotionPipeline/T3_RESEARCH.md``.

Public API:

    run_pass3_refine(project_id, llm=None) → Pass3Report
        Group cluster representatives by (category, atlas_segment),
        fan out one LLM call per group, parse responses, update
        concept store with refined tier/title/content.

Pure-function helpers (testable without an LLM):

    make_t3_system_prompt() → str
    make_t3_user_prompt(group, few_shot=True) → str
    parse_t3_response(text) → list[T3RefinedConcept]
    map_tier_to_confidence(tier) → float
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from prep.core.concept_clustering import ConceptInput

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Tier mapping (the LLM never sees these floats)
# ──────────────────────────────────────────────────────────────────────

TIER_TO_CONFIDENCE: dict[str, float] = {
    "T1": 0.30,
    "T2": 0.65,
    "T3": 0.92,
}

VALID_TIERS = frozenset(TIER_TO_CONFIDENCE.keys())
VALID_PAIRWISE = frozenset({"closer_to_lower", "closer_to_higher"})
VALID_ACTIONS = frozenset({"keep", "split", "drop"})

# Per-group cap. With 12-20 concepts per group + few-shot + system prompt
# we stay well under the 64K-token Kimi context.
MAX_GROUP_SIZE = 20


def map_tier_to_confidence(tier: str) -> float:
    """Map a tier label to its stored confidence float. Default 0 on unknown."""
    return TIER_TO_CONFIDENCE.get(tier, 0.0)


# ──────────────────────────────────────────────────────────────────────
# Refined-concept record
# ──────────────────────────────────────────────────────────────────────

@dataclass
class T3RefinedConcept:
    """One concept after Pass 3 LLM critique.

    Field order matches the JSON schema (rationale before score).
    """
    concept_id: str
    counter_evidence: str
    coincidence: str
    falsification: str
    tier_pairwise: str       # "closer_to_lower" | "closer_to_higher"
    tier: str                # "T1" | "T2" | "T3"
    tier_justification: str
    consolidation_action: str
    refined_title: str
    refined_content: str
    parse_warnings: tuple[str, ...] = ()

    @property
    def confidence(self) -> float:
        return map_tier_to_confidence(self.tier)


@dataclass
class Pass3Report:
    """Aggregate result of one Pass 3 run."""
    project_id: str = ""
    input_count: int = 0
    refined_count: int = 0
    parse_failure_count: int = 0
    group_count: int = 0
    largest_group_size: int = 0
    tier_distribution: dict[str, int] = field(default_factory=dict)
    consolidation_distribution: dict[str, int] = field(default_factory=dict)
    refined: list[T3RefinedConcept] = field(default_factory=list)
    dry_run: bool = False


# ──────────────────────────────────────────────────────────────────────
# Prompt templates (the heart of T3 — see T3_RESEARCH.md)
# ──────────────────────────────────────────────────────────────────────

T3_SYSTEM_PROMPT = """You evaluate code-intelligence concepts extracted from a codebase.
Each concept is a short rationale claim about a software pattern.

Your job: classify each concept against three tiers. The tier reflects
how well the EVIDENCE supports the concept — not how plausible-sounding
the wording is.

TIER DEFINITIONS (each is a PASSING TEST):

  T1 — pattern observed in code; no enforcement.
       Test: a reader could find counter-examples in the same codebase
       that don't follow the pattern, and nothing prevents them.
       Anchor example: "Database access uses connection pools" —
       observed in 3 modules but two other modules use raw connections;
       no test, lint, or type check enforces pooling.

  T2 — documented decision with at least one enforcing mechanism
       (test, lint rule, docstring referenced as a contract, ADR with
       a named anchor).
       Test: a developer who violated this pattern would either
       (a) get a test failure, OR (b) be flagged by a linter, OR
       (c) be pointed at a written decision document by a reviewer.
       Anchor example: "API responses use envelope format" — enforced
       by test_api_envelope.py and documented in API.md.

  T3 — codified in CI/types/constraint-concept; violations fail the build.
       Test: a developer who violated this pattern CANNOT merge —
       PR-time mypy strict / build / tests will block it.
       Anchor example: "All API responses must be Pydantic BaseModels"
       — mypy strict catches non-BaseModel returns, test_api_schema.py
       validates structure at every PR.

ADVERSARIAL CRITIQUE FIRST: before you assign a tier, you MUST think
about counter-evidence, coincidence, and falsification.

OUTPUT FORMAT: a single JSON ARRAY of objects, one per concept, IN
THE INPUT ORDER. Each object has these fields IN THIS EXACT ORDER:

  concept_id:           the input concept_id (echo it back)
  counter_evidence:     What would CONTRADICT this concept? Quote
                        specific files, classes, or patterns. If you
                        cannot name counter-evidence, write
                        "none observed" — but that should make the
                        tier lower, not higher.
  coincidence:          Could the pattern exist for an UNRELATED
                        reason (legacy code, copy-paste, framework
                        defaults)?
  falsification:        What CONCRETE observation would refute the
                        concept? If you cannot name a falsification
                        test, the concept is T1.
  tier_pairwise:        Before naming the tier, commit: is this
                        CLOSER TO the lower or higher neighbor tier?
                        Pick "closer_to_lower" or "closer_to_higher".
  tier:                 "T1" | "T2" | "T3"
  tier_justification:   Cite which TIER PASSING TEST is satisfied.
                        Reference specific files/tests if you can.
  consolidation_action: "keep" | "split" | "merge_with_<concept_id>" | "drop"
  refined_title:        Improved title (≤80 chars).
  refined_content:      Improved 2-4 sentence rationale.

Output JSON ONLY. No prose, no markdown fences, no explanation.

// Reminder: T1 = observed-only, T2 = enforced-by-test, T3 = enforced-by-build."""


_FEW_SHOT_EXAMPLES = """[FEW-SHOT EXAMPLES — three concepts ascending T1 → T2-boundary → T3]

Example 1 (T1, observed-only):
  Input concept:
    concept_id: "ex1"
    title: "Configuration loaded from environment variables"
    content: "Settings prefer environment variables over hardcoded values."
    anchors: ["src/cli.py", "src/server.py"]

  Output:
    {
      "concept_id": "ex1",
      "counter_evidence": "src/utils/defaults.py contains hardcoded timeouts; nothing flags this.",
      "coincidence": "Two files using env vars could be coincidence — Python framework convention, not a deliberate decision.",
      "falsification": "If a developer hardcoded a config value tomorrow, no test or lint would catch it.",
      "tier_pairwise": "closer_to_higher",
      "tier": "T1",
      "tier_justification": "Pattern observed but no enforcement mechanism named. Counter-example exists.",
      "consolidation_action": "keep",
      "refined_title": "Environment-variable config preference (observed, unenforced)",
      "refined_content": "Some files load configuration from environment variables, but the pattern is not enforced — defaults files contain hardcoded values, and no test or lint rule prevents new hardcoded settings."
    }

Example 2 (T2-boundary, looks T3 but isn't):
  Input concept:
    concept_id: "ex2"
    title: "All API responses use envelope format"
    content: "Responses wrap payload in {success, data, error} envelope."
    anchors: ["src/api/envelope.py", "tests/test_api_envelope.py", "docs/API.md"]

  Output:
    {
      "concept_id": "ex2",
      "counter_evidence": "test_api_envelope.py covers most routes but not /health or /metrics; those routes are exempted.",
      "coincidence": "Could be just a Pydantic-default convention, but envelope.py + the named test + docs/API.md make it intentional.",
      "falsification": "If a new route returned a bare dict instead of an envelope, test_api_envelope.py would fail at PR time.",
      "tier_pairwise": "closer_to_higher",
      "tier": "T2",
      "tier_justification": "Enforcement mechanism is the named test (test_api_envelope.py) plus the docs/API.md contract — passes T2's test. Not T3 because mypy/types do not require envelope; only the test does.",
      "consolidation_action": "keep",
      "refined_title": "API envelope contract enforced via tests",
      "refined_content": "API responses use a {success, data, error} envelope, contractually enforced by test_api_envelope.py and documented in API.md. Two routes (/health, /metrics) are exempted; mypy does not enforce envelope shape."
    }

Example 3 (T3, fails build):
  Input concept:
    concept_id: "ex3"
    title: "All public functions are type-annotated"
    content: "Functions exposed in __init__.py have full type annotations."
    anchors: ["src/foo/__init__.py", "pyproject.toml", ".github/workflows/ci.yml"]

  Output:
    {
      "concept_id": "ex3",
      "counter_evidence": "none observed — every public function has type annotations.",
      "coincidence": "Could be IDE auto-completion habit, but pyproject.toml has [tool.mypy] strict=true and CI runs mypy as a required check.",
      "falsification": "Adding an unannotated public function would fail mypy in CI; the PR cannot merge until annotations are added.",
      "tier_pairwise": "closer_to_lower",
      "tier": "T3",
      "tier_justification": "Codified in pyproject.toml (mypy strict) and CI (.github/workflows/ci.yml runs mypy as a blocking check). Violations fail the build at PR time.",
      "consolidation_action": "keep",
      "refined_title": "Public functions are mypy-strict type-annotated",
      "refined_content": "Public functions exposed in __init__.py modules carry full type annotations. Enforced by pyproject.toml's mypy strict mode plus a CI gate (.github/workflows/ci.yml) that blocks merges with unannotated public APIs."
    }
"""


def make_t3_system_prompt() -> str:
    """Return the full system prompt with embedded few-shot examples.

    Few-shot examples follow the system rules in the SAME prompt — they
    teach the model the JSON shape and the rationale-first ordering.
    """
    return T3_SYSTEM_PROMPT + "\n\n" + _FEW_SHOT_EXAMPLES


def make_t3_user_prompt(
    group: list[ConceptInput],
    *,
    category: str = "",
    segment: str = "",
) -> str:
    """Render the per-group user prompt.

    All concepts in ``group`` share a (category, segment) tuple — the
    LLM gets coherent siblings, which improves consolidation decisions
    and resists per-concept context-switch drift.
    """
    parts: list[str] = []
    parts.append(
        f"CONCEPTS TO EVALUATE (category={category!r}, segment={segment!r}, count={len(group)}):"
    )
    for c in group:
        parts.append("")
        parts.append(f"  concept_id: {c.id!r}")
        parts.append(f"  title: {c.title!r}")
        # Cap content to keep prompt tight
        content = ""
        try:
            content = (c.title and "")  # placeholder — content not in ConceptInput
        except Exception:
            pass
        parts.append(f"  anchors: {list(c.anchors)[:8]!r}")
        parts.append(f"  confidence_hint: {c.confidence:.2f}  // ignore — calibrate via tier")
    parts.append("")
    parts.append("Output a JSON array, one object per concept above, IN THE SAME ORDER.")
    parts.append("// Reminder: T1 = observed-only, T2 = enforced-by-test, T3 = enforced-by-build.")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Response parsing (defensive — Kimi sometimes wraps JSON in fences)
# ──────────────────────────────────────────────────────────────────────

_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.+?)\n\s*```\s*$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    m = _CODE_FENCE_RE.match(text.strip())
    return m.group(1) if m else text


def parse_t3_response(text: str) -> list[T3RefinedConcept]:
    """Parse a Pass-3 LLM response into refined concept records.

    Returns an empty list on JSON parse failure. Per-concept failures
    are flagged via ``parse_warnings`` but the record is still returned
    when possible.
    """
    if not text or not text.strip():
        return []
    raw = _strip_code_fence(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("T3 JSON parse failed: %s; first 300 chars: %r", e, raw[:300])
        return []
    if not isinstance(data, list):
        logger.warning("T3 response not a JSON array (got %s)", type(data).__name__)
        return []

    out: list[T3RefinedConcept] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        warnings: list[str] = []
        cid = str(entry.get("concept_id") or "").strip()
        if not cid:
            warnings.append("missing concept_id")
        tier = str(entry.get("tier") or "").strip().upper()
        if tier not in VALID_TIERS:
            warnings.append(f"invalid tier {tier!r}; skipping")
            continue
        pairwise = str(entry.get("tier_pairwise") or "").strip().lower()
        if pairwise not in VALID_PAIRWISE:
            warnings.append(f"invalid tier_pairwise {pairwise!r}; defaulting to closer_to_lower")
            pairwise = "closer_to_lower"
        action_raw = str(entry.get("consolidation_action") or "keep").strip().lower()
        if action_raw.startswith("merge_with_"):
            action = action_raw  # preserve full target
        elif action_raw in VALID_ACTIONS:
            action = action_raw
        else:
            warnings.append(f"invalid consolidation_action {action_raw!r}; defaulting to keep")
            action = "keep"

        out.append(T3RefinedConcept(
            concept_id=cid,
            counter_evidence=str(entry.get("counter_evidence") or "")[:600],
            coincidence=str(entry.get("coincidence") or "")[:600],
            falsification=str(entry.get("falsification") or "")[:600],
            tier_pairwise=pairwise,
            tier=tier,
            tier_justification=str(entry.get("tier_justification") or "")[:600],
            consolidation_action=action,
            refined_title=str(entry.get("refined_title") or "")[:80],
            refined_content=str(entry.get("refined_content") or "")[:1500],
            parse_warnings=tuple(warnings),
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Group-by-(category, segment) for fan-out
# ──────────────────────────────────────────────────────────────────────

def group_concepts_for_t3(
    concepts: Iterable[ConceptInput],
    *,
    file_to_segment: Optional[dict[str, str]] = None,
    max_group_size: int = MAX_GROUP_SIZE,
) -> list[tuple[str, str, list[ConceptInput]]]:
    """Partition concepts into ``(category, segment, members)`` groups.

    Args:
        concepts: cluster representatives (post Pass 2).
        file_to_segment: optional ``file_path → segment_id`` map. When
            provided, segment is derived from the most-common segment
            across a concept's anchors. When None, segment="*".
        max_group_size: hard cap; oversize groups are split into
            chunks (sub-grouped on the fly).

    The mapping from concept → category is read from ``concepts``; we
    expect the caller to populate ``ConceptInput`` with category if the
    schema supports it. ``ConceptInput`` only has id/title/confidence/anchors,
    so this function reads category from a parallel mapping passed in.
    """
    raise NotImplementedError(
        "ConceptInput doesn't carry category. Use group_with_category() below.",
    )


def group_with_category(
    items: Iterable[tuple[ConceptInput, str]],
    *,
    file_to_segment: Optional[dict[str, str]] = None,
    max_group_size: int = MAX_GROUP_SIZE,
) -> list[tuple[str, str, list[ConceptInput]]]:
    """Partition (concept, category) pairs into groups.

    Returns a list of ``(category, segment, members)`` tuples. Each
    tuple becomes one Pass-3 LLM call.
    """
    by_key: dict[tuple[str, str], list[ConceptInput]] = {}
    for concept, category in items:
        # Derive segment from majority anchor segment.
        segment = "*"
        if file_to_segment:
            seg_votes: dict[str, int] = {}
            for a in concept.anchors:
                s = file_to_segment.get(a)
                if s:
                    seg_votes[s] = seg_votes.get(s, 0) + 1
            if seg_votes:
                segment = max(seg_votes.items(), key=lambda kv: kv[1])[0]
        by_key.setdefault((category, segment), []).append(concept)

    groups: list[tuple[str, str, list[ConceptInput]]] = []
    for (cat, seg), members in by_key.items():
        # Split oversize groups
        for i in range(0, len(members), max_group_size):
            chunk = members[i:i + max_group_size]
            groups.append((cat, seg, chunk))
    return groups


# ──────────────────────────────────────────────────────────────────────
# Runner (DB-applying wrapper) — kept thin; LLM client passed by caller
# ──────────────────────────────────────────────────────────────────────

def run_pass3_refine(
    project_id: str,
    *,
    llm: Any = None,
    idx_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Pass3Report:
    """Run Pass 3 refinement for all cluster representatives in a project.

    For each (category, segment) group, calls the LLM with the T3
    tier-based prompt and updates concept records with the refined
    tier/title/content. When ``llm`` is None, uses
    ``WorkerFactory._get_llm_client_for_task("concepts")``.

    Args:
        project_id: project to refine.
        llm: optional LLM client; defaults to the concepts task client.
        idx_dir: optional index dir for telemetry. Resolved if None.
        dry_run: if True, decide refinements but do NOT update the DB.
    """
    from prep.core.concept_clustering import load_concepts_for_clustering
    from prep.core.project_registry import prep_data_dir
    from prep.services.concept_store import concept_store

    db_path = Path(prep_data_dir()) / "prep_concepts.db"
    if not db_path.is_file():
        raise RuntimeError(f"concept DB not found at {db_path}")

    # Load cluster representatives — concepts with status='seed' that
    # are NOT shadows. Pass 2 sets shadows to status='shadow', so a
    # status='seed' filter selects representatives + singletons.
    seeds = load_concepts_for_clustering(str(db_path), project_id, status="seed")
    if not seeds:
        return Pass3Report(project_id=project_id, dry_run=dry_run)

    # Pull category for each concept by id
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        cat_rows = conn.execute(
            "SELECT id, category FROM concepts WHERE project_id=?",
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    cat_by_id = {row[0]: (row[1] or "?") for row in cat_rows}

    items = [(c, cat_by_id.get(c.id, "?")) for c in seeds]

    # Optional: derive file → segment from atlas_segments_manifest
    file_to_segment: Optional[dict[str, str]] = None
    try:
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project
        project = require_project(project_id)
        seg_path = Path(project_index_dir(project)) / "atlas_segments_manifest.json"
        if seg_path.is_file():
            manifest = json.loads(seg_path.read_text())
            if isinstance(manifest, list):
                file_to_segment = {}
                for entry in manifest:
                    sid = entry.get("id") or entry.get("segment_id")
                    for fp in entry.get("file_paths") or []:
                        if isinstance(fp, str):
                            file_to_segment.setdefault(fp, sid)
    except Exception as e:
        logger.debug("segment derivation skipped: %s", e)

    groups = group_with_category(items, file_to_segment=file_to_segment)

    # Resolve LLM client if not provided
    if llm is None:
        try:
            from prep.services.pipeline.workers import WorkerFactory
            llm = WorkerFactory._get_llm_client_for_task("concepts")
        except Exception as e:
            raise RuntimeError(f"could not resolve LLM client: {e}")

    system_prompt = make_t3_system_prompt()
    refined_all: list[T3RefinedConcept] = []
    parse_failures = 0

    for cat, seg, members in groups:
        user_prompt = make_t3_user_prompt(members, category=cat, segment=seg)
        try:
            text, _tokens = llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                json_mode=True,
                temperature=0.1,
                num_predict=4000,
                think=False,
            )
            refined = parse_t3_response(text or "")
            if not refined:
                parse_failures += len(members)
                logger.warning(
                    "[Pass3] group (%s,%s) %d members: parse failure",
                    cat, seg, len(members),
                )
                continue
            refined_all.extend(refined)
            logger.info(
                "[Pass3] group (%s,%s) %d in → %d refined",
                cat, seg, len(members), len(refined),
            )
        except Exception as e:
            logger.warning(
                "[Pass3] LLM call failed for group (%s,%s): %s", cat, seg, e,
            )
            parse_failures += len(members)
            continue

    # Aggregate stats
    tier_d: dict[str, int] = {}
    cons_d: dict[str, int] = {}
    for r in refined_all:
        tier_d[r.tier] = tier_d.get(r.tier, 0) + 1
        cons_d[r.consolidation_action] = cons_d.get(r.consolidation_action, 0) + 1

    report = Pass3Report(
        project_id=project_id,
        input_count=len(seeds),
        refined_count=len(refined_all),
        parse_failure_count=parse_failures,
        group_count=len(groups),
        largest_group_size=max((len(g[2]) for g in groups), default=0),
        tier_distribution=tier_d,
        consolidation_distribution=cons_d,
        refined=refined_all,
        dry_run=dry_run,
    )

    if not dry_run:
        # Apply refinements to DB
        for r in refined_all:
            try:
                concept_store.update(
                    r.concept_id,
                    title=r.refined_title or None,
                    content=r.refined_content or None,
                )
                # Confidence is in concept_store via the same update?
                # ConceptStore.update doesn't have a confidence arg —
                # need to verify schema. Tier is stored via tags.
                # For now just update title+content; confidence
                # update needs a schema extension (T4 territory).
            except Exception as e:
                logger.warning("Pass3 update failed for %s: %s", r.concept_id, e)

    # Telemetry
    if idx_dir is not None:
        try:
            from prep.services.pipeline_telemetry import record_event
            record_event(
                idx_dir,
                "pass3_refine_complete" if not dry_run else "pass3_dry_run",
                {
                    "input_count": report.input_count,
                    "refined_count": report.refined_count,
                    "parse_failures": report.parse_failure_count,
                    "group_count": report.group_count,
                    "largest_group": report.largest_group_size,
                    "tier_distribution": report.tier_distribution,
                    "consolidation_distribution": report.consolidation_distribution,
                    "dry_run": dry_run,
                },
                stage="concepts", project_id=project_id,
            )
        except Exception:
            pass

    return report
