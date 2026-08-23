"""Phase 125b — cross-cutting concept synthesizer.

Single-LLM-call synthesis that LIFTS ABSTRACTION from the per-module
rationale layer (the ~1,500-3,000 entries the swarm seeder produces)
to a small, curated, agent-actionable concept layer (~30-100).

The synthesizer's input is rich grounding from every upstream
artifact in the pipeline:

  * Atlas (modules, hubs, cross-cutting concerns)
  * Audit findings (top critical / warning)
  * Spaghetti hotspots (high-severity files)
  * Antibody-eligible patterns (already-derived constraints)
  * Clustered module rationale representatives (top-N by member count)
  * T2 markdown links (top docs by mention count — ADR / phase
    decision evidence)

A concept synthesized here:

  * spans MULTIPLE modules or files
  * captures a constraint, decision, or tradeoff that's NOT obvious
    from reading code
  * is action-shaping for an AI agent working on this codebase
  * is one of ≤100 across an entire project
  * is stored with ``kind='concept'`` (vs ``kind='module_rationale'``)

Public API:

    synthesize_concepts(project_id, llm=None) → SynthesisReport
        Reads all upstream artifacts, builds the prompt, calls the
        LLM once, parses the JSON array, saves with kind='concept'.

Pure-function helpers (testable without an LLM):

    build_synthesis_prompt(grounding) → (system, user)
    parse_synthesis_response(text) → list[SynthesizedConcept]
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Tier mapping (matches Phase 125 T3 research)
# ──────────────────────────────────────────────────────────────────────

TIER_TO_CONFIDENCE: dict[str, float] = {
    "T1": 0.30,
    "T2": 0.65,
    "T3": 0.92,
}
VALID_TIERS = frozenset(TIER_TO_CONFIDENCE.keys())
VALID_PAIRWISE = frozenset({"closer_to_lower", "closer_to_higher"})

# Hard cap on synthesizer output. The LLM is instructed to stay
# within ~30-100, but we enforce a ceiling defensively. If the
# model returns more, we keep the highest-tier-first.
MAX_SYNTHESIZED_CONCEPTS = 150


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class SynthesizedConcept:
    """One cross-cutting concept emerged from synthesis."""
    title: str
    content: str
    category: str
    tier: str                    # T1 | T2 | T3
    tier_pairwise: str           # closer_to_lower | closer_to_higher
    anchors: tuple[str, ...]     # files / docs that ground the claim
    counter_evidence: str = ""
    falsification: str = ""
    refined_content: str = ""    # may differ from content; preferred when set
    parse_warnings: tuple[str, ...] = ()

    @property
    def confidence(self) -> float:
        return TIER_TO_CONFIDENCE.get(self.tier, 0.0)

    def to_save_dict(self) -> dict[str, Any]:
        """Convert to the dict shape concept_store.save_many expects.

        Phase 125b: synthesizer is itself the quality gate. The LLM has
        already evaluated each item against the T1/T2/T3 rubric (anchored,
        cross-cutting, falsifiable). T2 and T3 are confident enough to
        surface as 'active' immediately; T1 stays 'seed' as a candidate
        for future review.
        """
        status = "active" if self.tier in ("T2", "T3") else "seed"
        return {
            "title": self.title[:200],
            "content": (self.refined_content or self.content)[:4000],
            "category": self.category,
            "status": status,
            "confidence": self.confidence,
            "anchors": list(self.anchors),
            "kind": "concept",
            "assertion": self.falsification or "",
        }


@dataclass
class SynthesisReport:
    """Aggregate output of one synthesis run."""
    project_id: str = ""
    concepts: list[SynthesizedConcept] = field(default_factory=list)
    total_emitted: int = 0
    saved: int = 0
    skipped: int = 0
    parse_failure: bool = False
    grounding_summary: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    dry_run: bool = False


# ──────────────────────────────────────────────────────────────────────
# Grounding loader — pulls every upstream artifact
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Grounding:
    """All inputs the synthesizer needs in a single struct."""
    project_name: str = ""
    atlas_summary: str = ""
    segments: list[dict] = field(default_factory=list)
    audit_findings: list[dict] = field(default_factory=list)
    spaghetti_hotspots: list[dict] = field(default_factory=list)
    antibody_patterns: list[dict] = field(default_factory=list)
    rationale_clusters: list[dict] = field(default_factory=list)
    top_md_docs: list[dict] = field(default_factory=list)
    # Investigation 2026-08-22 (A): source code slices for anchor files
    # so workers can verify their assertions against real code instead
    # of hallucinating about files they've never seen. Maps relative
    # path → ±20-line content slice.
    source_slices: dict[str, str] = field(default_factory=dict)


def load_grounding(
    project_id: str,
    *,
    idx_dir: Path,
    project_name: str = "",
    project_root: Optional[Path] = None,
    # Phase 125c post-review: rationale_top_n bumped 50 -> 200 so that
    # after Generate's per-category scope filter (3-axis fan-out divides
    # the rationale across workers), each worker still sees a meaningful
    # slice (~67 rows per axis on a typical project).
    rationale_top_n: int = 200,
    audit_top_n: int = 12,
    spaghetti_top_n: int = 10,
    docs_top_n: int = 10,
    # Investigation 2026-08-22 (A): max source slices to load.
    source_slice_max: int = 30,
    source_slice_lines: int = 20,
) -> Grounding:
    """Load every upstream artifact into a single struct for synthesis.

    Investigation 2026-08-22 (A): now also loads ±``source_slice_lines``
    line source code slices for anchor files referenced by rationale
    clusters, so workers can verify their assertions against real code.
    Requires ``project_root`` to resolve relative anchor paths.
    """
    g = Grounding(project_name=project_name)

    # Atlas summary + segments
    atlas_path = idx_dir / "atlas.json"
    if atlas_path.is_file():
        try:
            atlas = json.loads(atlas_path.read_text())
            g.atlas_summary = (atlas.get("content") or "")[:3000]
        except Exception:
            pass
    seg_path = idx_dir / "atlas_segments_manifest.json"
    if seg_path.is_file():
        try:
            segs = json.loads(seg_path.read_text())
            if isinstance(segs, list):
                g.segments = [
                    {
                        "id": s.get("id") or s.get("segment_id"),
                        "name": s.get("name") or s.get("segment_name"),
                        "file_count": s.get("file_count", 0),
                        "domain_tags": (s.get("domain_tags") or [])[:5],
                    }
                    for s in segs[:12]
                ]
        except Exception:
            pass

    # Audit findings
    findings_path = idx_dir / "audit" / "findings.json"
    if findings_path.is_file():
        try:
            data = json.loads(findings_path.read_text())
            findings = data.get("findings") or []
            findings.sort(
                key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.get("severity", "info"), 3),
            )
            g.audit_findings = [
                {
                    "title": f.get("title", "")[:80],
                    "severity": f.get("severity", ""),
                    "file_paths": (f.get("file_paths") or [])[:2],
                    "description": (f.get("description") or "")[:160],
                }
                for f in findings[:audit_top_n]
            ]
        except Exception:
            pass

    # Spaghetti hotspots
    sp_path = idx_dir / "audit" / "spaghetti.json"
    if sp_path.is_file():
        try:
            data = json.loads(sp_path.read_text())
            files = (data.get("files") or [])
            files = [f for f in files if f.get("severity") in ("critical", "warning")]
            files.sort(key=lambda f: -(f.get("score") or 0))
            g.spaghetti_hotspots = [
                {
                    "file_path": f.get("file_path", ""),
                    "score": round(f.get("score", 0.0), 2),
                    "severity": f.get("severity", ""),
                    "in_circular": bool(f.get("in_circular")),
                }
                for f in files[:spaghetti_top_n]
            ]
        except Exception:
            pass

    # Antibody-eligible patterns: top-priority constraint candidates.
    # Best-effort — we read the existing antibody store via
    # antibody_store if available; otherwise skip.
    try:
        from prep.services.antibody_store import antibody_store
        antibodies = antibody_store.list_antibodies(project_id, status="testing")[:8]
        g.antibody_patterns = [
            {
                "name": a.name[:80],
                "severity": getattr(a, "severity", ""),
            }
            for a in antibodies
        ]
    except Exception:
        pass

    # Top markdown docs (T2 link extraction)
    ml_path = idx_dir / "atlas_markdown_links.json"
    if ml_path.is_file():
        try:
            ml = json.loads(ml_path.read_text())
            md_to_files = ml.get("md_to_files") or {}
            ranked = sorted(
                md_to_files.items(), key=lambda kv: -len(kv[1] or []),
            )
            g.top_md_docs = [
                {"path": p, "links": len(refs or [])}
                for p, refs in ranked[:docs_top_n]
            ]
        except Exception:
            pass

    # Rationale clusters: pull from concept_store with kind='module_rationale'.
    # Ranking by anchor-count proxy (more anchored entries == more grounded).
    try:
        from prep.services.concept_store import concept_store
        rationale = concept_store.list_concepts(
            project_id,
            kind="module_rationale",
            include_archived=False,
        )
        rationale.sort(key=lambda c: -(len(c.anchors) + len(c.tags)))
        # Phase 125c post-review: include content[:400] so workers see
        # the WHY of each rationale row, not just the title. Title-only
        # grounding contributed to bug-description-shaped outputs because
        # workers were guessing meaning from short titles + anchor paths.
        g.rationale_clusters = [
            {
                "title": c.title[:90],
                "category": c.category,
                "anchors": list(c.anchors)[:3],
                "content": (c.content or "")[:400],
            }
            for c in rationale[:rationale_top_n]
        ]
    except Exception:
        pass

    # Investigation 2026-08-22 (A): load source code slices for anchor
    # files referenced by rationale clusters. Workers are asked to emit
    # grep-falsifiable assertions about source files, but until now they
    # never saw the actual source code — leading to hallucinated
    # assertions. We pull ±source_slice_lines around the first non-trivial
    # line of each anchor file, capped at source_slice_max files.
    if project_root is not None:
        seen_paths: set[str] = set()
        for rc in g.rationale_clusters:
            for anchor in (rc.get("anchors") or []):
                if len(g.source_slices) >= source_slice_max:
                    break
                anchor_str = str(anchor)
                # Normalize: anchors may be relative or absolute
                candidate = Path(anchor_str)
                if not candidate.is_absolute():
                    candidate = project_root / anchor_str
                rel_key = str(candidate.relative_to(project_root)) if (
                    candidate.is_absolute() and str(candidate).startswith(str(project_root))
                ) else anchor_str
                if rel_key in seen_paths:
                    continue
                try:
                    if candidate.is_file():
                        text = candidate.read_text(errors="replace")
                        lines = text.splitlines()
                        # Take first N non-empty lines (the meaningful
                        # top-of-file context — imports, class/function
                        # signatures, module docstring).
                        picked: list[str] = []
                        for line in lines:
                            if line.strip():
                                picked.append(line)
                            if len(picked) >= source_slice_lines:
                                break
                        g.source_slices[rel_key] = "\n".join(picked)
                        seen_paths.add(rel_key)
                except Exception:
                    pass

    return g


# ──────────────────────────────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────────────────────────────

SYNTH_SYSTEM_PROMPT = """You synthesize cross-cutting concepts from a codebase analysis.

A "concept" is a SINGLE statement that:
- spans MULTIPLE modules or files (>= 3 anchors)
- captures a constraint, decision, or tradeoff that is NOT obvious from
  reading code or filenames
- is action-shaping for an AI agent working on this codebase
- has at MOST ~30 across an entire project. Fewer is better.

═══════════════════════════════════════════════════════════════════════
EMPTY OUTPUT IS ACCEPTABLE — PADDING IS A FAILURE MODE
═══════════════════════════════════════════════════════════════════════

If <5 candidates pass the bar, return what passes. Do not invent. Do not
restate the stack ("uses React", "imports FastAPI"). If grounding is
mediocre, return ``[]``. The reviewer will praise a 3-concept output
of T3-grade insight more than a 50-concept output of T1 padding.

═══════════════════════════════════════════════════════════════════════
BANNED OUTPUTS — these are what a junior reviewer would propose; we ban them
═══════════════════════════════════════════════════════════════════════

Before drafting, mentally enumerate the 3-5 generic concepts a junior reviewer
would propose. Examples (NEVER emit anything resembling these):
  - "Uses async/await for I/O"
  - "Has tests in tests/ directory"
  - "Module X handles Y"
  - "Imports from external library Z"
  - "Follows MVC pattern"
  - "Uses dependency injection"
  - "Modular architecture"

Bad concepts you must NOT emit (belong in module rationale layer, not here):
  - File-level observations: "Function X validates inputs"
  - Graph facts: "A imports B"
  - Library uses: "This file uses Pydantic"

═══════════════════════════════════════════════════════════════════════
BUG DESCRIPTIONS AND AUDIT FINDINGS — DO NOT EMIT AS CONCEPTS
═══════════════════════════════════════════════════════════════════════

These belong in the AUDIT surface, not the concept layer. A "concept"
captures INTENT (what the system is FOR, what the rules are, what the
tradeoffs WERE chosen). It is NOT a defect report.

If you find yourself writing a candidate of any of these shapes, REJECT it
and emit nothing for that idea:
  - "X causes Y bug"                  (defect, not intent)
  - "X lacks Y mechanism"             (gap, not concept)
  - "X creates Y desync"              (failure mode, not concept)
  - "X has security vulnerability Y"  (audit finding, not concept)
  - "Module X has known issue Y"      (bug report, not concept)
  - "X risks Y"                       (audit, not concept)
  - "X is attacker-controllable"      (security finding, not concept)
  - "X lacks crypto verification"     (security finding, not concept)

A "Pi Agent must never call cloud LLM without license check" is a CONCEPT.
"License check is missing in Pi Agent at line 47" is an AUDIT FINDING.
The first belongs here; the second belongs elsewhere.

═══════════════════════════════════════════════════════════════════════
HISTORICAL / META OBSERVATIONS — also NOT concepts
═══════════════════════════════════════════════════════════════════════

These describe the documentation or the project's history, not the
codebase itself:
  - "Phase-numbered documentation encodes research evolution"
  - "Stage count expanded from N to M over time"
  - "Filename conventions encode experimental conditions"

A future agent working in the code cannot ACT on these. Skip them.

═══════════════════════════════════════════════════════════════════════
GOOD examples (cross-cutting, non-obvious, falsifiable)
═══════════════════════════════════════════════════════════════════════

  - "License verification must precede any cloud LLM call"
    → T3, falsifiable: grep call sites of LLMClient.generate without @licensed decorator
  - "Embedded mode preserves git-trackability — never write to ~/.local for indexes"
    → T2, falsifiable: grep writes to ~/.local under embedded_mode flag
  - "Prep is a headless intelligence engine that never owns UI real estate"
    → T2 (doc-anchored decision; Paperclip plugin docs cite this principle)
  - "Tauri over Electron for binary size — 8 MB vs 80 MB"
    → T1, observable in package.json + dist/ size

═══════════════════════════════════════════════════════════════════════
TIER RUBRIC — use NAMED labels, do not default to T2
═══════════════════════════════════════════════════════════════════════

T1 — "Pattern hint only; one or two anchors; would not survive adversarial review."
     A reader could find counter-examples in the same codebase. Observation,
     not enforcement.

T2 — "Documented decision OR enforced pattern — either, not both required."
     EITHER (a) anchored to an authoritative planning doc (ADR / RFC /
     Phase doc / ARCHITECTURE.md / DESIGN.md / a README that's heavily
     referenced from code), OR (b) at least one observable enforcement
     mechanism in code (test, lint, decorator, runtime check). Doc-only
     anchoring counts as T2 when the doc is authoritative — strategic
     positioning concepts ("we don't embed UI in client X") live in docs
     not in @licensed decorators. counter_evidence exists but is
     partially refuted by a specific anchor.

T3 — "Codified in CI/types/constraint-concept; violations fail the build."
     A developer who violated this CANNOT merge. counter_evidence is
     non-empty AND refuted with a specific anchor. Falsifiable in <5min
     with grep. T3 requires CODE enforcement; doc-only commitments
     are T2.

DO NOT DEFAULT TO T2. T1 is the correct tier for weak evidence. T3 is
RARE — most projects have 0-5 T3 concepts. If everything you emit is T2,
you are not committing to either evidence floor or evidence ceiling.

═══════════════════════════════════════════════════════════════════════
PROCESS — for each candidate, in order
═══════════════════════════════════════════════════════════════════════

1. QUOTE: name 1-3 verbatim spans from the input grounding (atlas /
   audit / clusters / docs) with file paths. If you cannot quote
   grounding, REJECT the candidate.

2. COUNTER-EVIDENCE FIRST: list 1-2 files or patterns that would
   WEAKEN this concept if found. Empty counter_evidence means you
   have not looked hard enough — re-examine or downgrade.

3. FALSIFICATION: phrase the assertion so a reviewer with grep can
   disprove it in <5 min. Bad: "uses dependency injection". Good:
   "no module in src/prep/services/ instantiates LLMClient directly;
   all go through container.resolve (verifiable: grep 'LLMClient(' src/prep/services/)".

4. TIER ASSIGNMENT — committed AFTER counter-evidence is populated.
   T3 requires non-empty counter_evidence that you then refute with
   a specific anchor.

5. HOSTILE REVIEWER PASS — before serializing, scan your draft list:
   "If a hostile reviewer demanded I downgrade every T3, which would
   actually survive on the evidence I quoted?" Downgrade the rest to
   T2 or T1. Re-emit only post-downgrade tiers.

═══════════════════════════════════════════════════════════════════════
OUTPUT SCHEMA — fields in this EXACT order. Tier is LAST.
═══════════════════════════════════════════════════════════════════════

  title:               ≤80 chars, a one-line CLAIM not a topic
  category:            architecture | constraint | decision | tradeoff
                       | technical | process | security | product | pattern
                       | domain | epistemic | brand
  anchors:             list of file paths or doc paths quoted in step 1
  counter_evidence:    What would CONTRADICT this concept? Quote files.
                       Empty string only if you can name no plausible
                       counter — and only at T1.
  falsification:       Concrete grep-able test that would refute the concept.
                       If you cannot name one, the concept is T1.
  refined_content:     2-4 sentence rationale, computed from quote +
                       counter_evidence + falsification
  tier_pairwise:       "closer_to_lower" | "closer_to_higher" — commit BEFORE tier
  tier:                "T1" | "T2" | "T3" — computed from prior fields

Output JSON ARRAY ONLY. No prose. No markdown fences. Empty array []
is acceptable when nothing meets the bar.

// Reminder: T1 = observed-only, T2 = enforced-by-test, T3 = enforced-by-build.
"""


def build_synthesis_prompt(grounding: Grounding) -> tuple[str, str]:
    """Return ``(system, user)`` prompts for the synthesizer LLM call."""
    parts: list[str] = []
    parts.append(f"PROJECT: {grounding.project_name or '(unnamed)'}")
    parts.append("")

    if grounding.atlas_summary:
        parts.append("ATLAS SUMMARY (first 3K chars):")
        parts.append(grounding.atlas_summary)
        parts.append("")

    if grounding.segments:
        parts.append(f"ATLAS SEGMENTS ({len(grounding.segments)} top):")
        for s in grounding.segments:
            tags = ", ".join(s.get("domain_tags") or [])
            parts.append(f"  - {s.get('name')} ({s.get('file_count')} files) [{tags}]")
        parts.append("")

    if grounding.audit_findings:
        parts.append(f"AUDIT FINDINGS (top {len(grounding.audit_findings)} by severity):")
        for f in grounding.audit_findings:
            paths = ", ".join(f.get("file_paths") or [])
            parts.append(f"  [{f.get('severity','?')}] {f.get('title')} — {paths}")
        parts.append("")

    if grounding.spaghetti_hotspots:
        parts.append(f"SPAGHETTI HOTSPOTS (top {len(grounding.spaghetti_hotspots)} by score):")
        for h in grounding.spaghetti_hotspots:
            tags = []
            if h.get("in_circular"):
                tags.append("circular")
            tag = f" [{', '.join(tags)}]" if tags else ""
            parts.append(
                f"  - {h.get('file_path')}  score={h.get('score')} ({h.get('severity')}){tag}"
            )
        parts.append("")

    if grounding.antibody_patterns:
        parts.append(f"ANTIBODY-ELIGIBLE PATTERNS ({len(grounding.antibody_patterns)}):")
        for a in grounding.antibody_patterns:
            parts.append(f"  - [{a.get('severity','?')}] {a.get('name')}")
        parts.append("")

    if grounding.top_md_docs:
        parts.append(f"TOP DOCS BY CODE-PATH MENTIONS ({len(grounding.top_md_docs)}):")
        for d in grounding.top_md_docs:
            parts.append(f"  - {d.get('path')}  ({d.get('links')} links)")
        parts.append("")

    if grounding.rationale_clusters:
        parts.append(
            f"MODULE RATIONALE CLUSTERS (top {len(grounding.rationale_clusters)} by anchor "
            "count — these are per-module observations; SYNTHESIZE across them, do NOT "
            "echo them):"
        )
        for r in grounding.rationale_clusters:
            anchors = ", ".join(r.get("anchors") or [])
            parts.append(f"  - [{r.get('category')}] {r.get('title')}  ←  {anchors}")
        parts.append("")

    parts.append(
        "TASK: emit cross-cutting concepts as a JSON array per the system "
        "prompt's schema. Target 5-30 concepts; emit 0 if grounding is "
        "mediocre. Anchor each concept to specific files/docs from the "
        "inputs above. Do NOT echo per-module rationale verbatim — LIFT "
        "abstraction across them. Reviewers prefer 5 T3-grade insights "
        "over 50 T1 restatements. Run the hostile-reviewer downgrade pass "
        "before serializing."
    )

    return SYNTH_SYSTEM_PROMPT, "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Response parsing (defensive)
# ──────────────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.+?)\n\s*```\s*$", re.DOTALL)


def _strip_fence(text: str) -> str:
    m = _FENCE_RE.match(text.strip())
    return m.group(1) if m else text


VALID_CATEGORY_LIST = (
    "architecture", "constraint", "decision", "tradeoff",
    "technical", "process", "security", "product",
    "pattern", "domain", "epistemic", "brand",
)


def _salvage_truncated_json_array(raw: str) -> Optional[list]:
    """Attempt to recover a JSON array that was truncated mid-element.

    The LLM may hit ``num_predict`` and stop mid-object. Walk backwards from
    the end, find the last complete object (last ``}``), close the array
    there, and re-parse. Better to save 25 valid concepts than to lose 30.
    """
    if not raw or "[" not in raw:
        return None
    start = raw.find("[")
    last_close = raw.rfind("}")
    if last_close < start:
        return None
    try:
        return json.loads(raw[start:last_close + 1] + "]")
    except json.JSONDecodeError:
        # Try walking back through preceding ``}`` until one parses.
        cursor = last_close
        for _ in range(50):
            cursor = raw.rfind("}", start, cursor)
            if cursor <= start:
                break
            try:
                return json.loads(raw[start:cursor + 1] + "]")
            except json.JSONDecodeError:
                continue
        return None


def parse_synthesis_response(text: str) -> list[SynthesizedConcept]:
    """Parse the JSON array of concepts from the LLM response.

    Robust to truncated output (LLM hit num_predict mid-array): falls
    back to ``_salvage_truncated_json_array`` to recover whatever
    complete objects are present.
    """
    if not text or not text.strip():
        return []
    raw = _strip_fence(text)
    data: Any
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        salvaged = _salvage_truncated_json_array(raw)
        if salvaged is None:
            logger.warning(
                "synthesis parse failed: %s; first 300 chars: %r",
                e, raw[:300],
            )
            return []
        logger.warning(
            "synthesis JSON truncated; salvaged %d entries (orig parse error: %s)",
            len(salvaged), e,
        )
        data = salvaged
    if not isinstance(data, list):
        logger.warning("synthesis response not a JSON array (got %s)", type(data).__name__)
        return []

    out: list[SynthesizedConcept] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        warnings: list[str] = []
        title = (entry.get("title") or "").strip()
        if not title:
            warnings.append("missing title; skipped")
            continue
        tier = (entry.get("tier") or "").strip().upper()
        if tier not in VALID_TIERS:
            warnings.append(f"invalid tier {tier!r}; skipped")
            continue
        pairwise = (entry.get("tier_pairwise") or "").strip().lower()
        if pairwise not in VALID_PAIRWISE:
            pairwise = "closer_to_lower"
            warnings.append(f"invalid tier_pairwise; defaulted")
        # tradeoff is mapped to 'decision' in the canonical category set
        # of concept_store; keep as-is in the LLM output, but synthesize_concepts
        # normalizes before save.
        category = (entry.get("category") or "technical").strip().lower()
        anchors = entry.get("anchors") or []
        if not isinstance(anchors, list):
            anchors = []
        anchors = tuple(a for a in anchors if isinstance(a, str) and a)

        out.append(SynthesizedConcept(
            title=title,
            content=str(entry.get("refined_content") or entry.get("content") or "")[:4000],
            category=category,
            tier=tier,
            tier_pairwise=pairwise,
            anchors=anchors,
            counter_evidence=str(entry.get("counter_evidence") or "")[:600],
            falsification=str(entry.get("falsification") or "")[:600],
            refined_content=str(entry.get("refined_content") or "")[:4000],
            parse_warnings=tuple(warnings),
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Runner — one LLM call, then save with kind='concept'
# ──────────────────────────────────────────────────────────────────────

def _emit_failure_event(
    idx_dir: Optional[Path],
    project_id: str,
    report: "SynthesisReport",
    *,
    reason: str,
) -> None:
    """Emit a synthesis-failure telemetry event so the harness sees it."""
    if idx_dir is None:
        return
    try:
        from prep.services.pipeline_telemetry import record_event
        record_event(
            idx_dir,
            "concept_synthesis_failed",
            {
                "reason": reason,
                "grounding": report.grounding_summary,
                "elapsed_seconds": round(report.elapsed_seconds, 2),
            },
            stage="concepts", project_id=project_id,
        )
    except Exception:
        pass


def _rationale_fingerprint(project_id: str) -> tuple[int, float]:
    """Return (count, max_updated_at) for kind='module_rationale' concepts."""
    try:
        from prep.services.concept_store import concept_store
        rows = concept_store.list_concepts(project_id, kind="module_rationale")
        if not rows:
            return (0, 0.0)
        max_ts = max((r.updated_at or r.created_at or 0.0) for r in rows)
        return (len(rows), float(max_ts))
    except Exception:
        return (0, 0.0)


def _read_synth_manifest(idx_dir: Path) -> Optional[dict]:
    p = idx_dir / "concept_synthesis_manifest.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _write_synth_manifest(idx_dir: Path, payload: dict) -> None:
    try:
        p = idx_dir / "concept_synthesis_manifest.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


def synthesize_concepts(
    project_id: str,
    *,
    llm: Any = None,
    idx_dir: Optional[Path] = None,
    project_name: str = "",
    project_root: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False,
) -> SynthesisReport:
    """Run cross-cutting concept synthesis for a project.

    Reads grounding from atlas/audit/spaghetti/antibodies/rationale/T2,
    builds a single rich prompt, calls the LLM once, parses, saves with
    kind='concept'.

    Args:
        project_id: project to synthesize for.
        llm: LLM client (defaults to WorkerFactory's concepts task client).
        idx_dir: project index dir for telemetry + grounding loading.
        project_name: optional human-readable name for the prompt header.
        dry_run: if True, generate the prompt and return what would be saved
            without actually persisting. Useful for offline prompt review.
        force: if True, bypass the freshness check and re-synthesize even
            when rationale hasn't changed since the last successful run.
    """
    t0 = time.time()
    report = SynthesisReport(project_id=project_id, dry_run=dry_run)

    # Resolve idx_dir if not provided.
    if idx_dir is None:
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            if not project_name:
                project_name = project.name or ""
        except Exception as e:
            raise RuntimeError(f"could not resolve project: {e}")

    # Freshness check: skip if rationale hasn't changed since last run.
    rationale_count, rationale_max_ts = _rationale_fingerprint(project_id)
    if not force and not dry_run and rationale_count > 0:
        manifest = _read_synth_manifest(idx_dir) if idx_dir else None
        if manifest:
            last_count = int(manifest.get("rationale_count") or 0)
            last_ts = float(manifest.get("rationale_max_updated_at") or 0.0)
            if last_count == rationale_count and rationale_max_ts <= last_ts:
                logger.info(
                    "[Synth] skipping for %s — rationale unchanged "
                    "(count=%d, max_ts=%.0f). Pass force=True to override.",
                    project_id, rationale_count, rationale_max_ts,
                )
                report.elapsed_seconds = time.time() - t0
                report.grounding_summary = {"freshness_skip": 1}
                try:
                    from prep.services.pipeline_telemetry import record_event
                    record_event(
                        idx_dir, "concept_synthesis_skipped_fresh",
                        {
                            "rationale_count": rationale_count,
                            "last_synth_ts": float(manifest.get("synth_completed_at") or 0.0),
                        },
                        stage="concepts", project_id=project_id,
                    )
                except Exception:
                    pass
                return report

    grounding = load_grounding(
        project_id, idx_dir=idx_dir, project_name=project_name,
        project_root=project_root,
    )
    report.grounding_summary = {
        "audit_findings": len(grounding.audit_findings),
        "spaghetti_hotspots": len(grounding.spaghetti_hotspots),
        "antibody_patterns": len(grounding.antibody_patterns),
        "rationale_clusters": len(grounding.rationale_clusters),
        "top_md_docs": len(grounding.top_md_docs),
        "atlas_segments": len(grounding.segments),
    }

    system, user = build_synthesis_prompt(grounding)

    if dry_run:
        logger.info(
            "[Synth/dry-run] %d-char prompt; would call LLM with grounding: %s",
            len(system) + len(user), report.grounding_summary,
        )
        report.elapsed_seconds = time.time() - t0
        return report

    if llm is None:
        try:
            from prep.services.pipeline.workers import WorkerFactory
            llm = WorkerFactory._get_llm_client_for_task("concepts")
        except Exception as e:
            raise RuntimeError(f"could not resolve LLM client: {e}")

    # Single LLM call. Defensive defaults aligned with T3_RESEARCH.md.
    # num_predict=5000 is sufficient for ~50 well-formed concepts at
    # ~100 tokens each. Larger budgets risk hitting the cap mid-JSON
    # (SourcePrep 2026-05-03 evidence: 8000-token cap → truncated array
    # → parse failure). The salvage parser catches truncations anyway,
    # but a tighter budget reduces the risk and shortens wall-time.
    try:
        text, _tokens = llm.generate(
            prompt=user,
            system=system,
            json_mode=True,
            temperature=0.1,
            num_predict=5000,
            think=False,
        )
    except Exception as e:
        logger.warning("synthesis LLM call failed: %s", e, exc_info=True)
        report.parse_failure = True
        report.elapsed_seconds = time.time() - t0
        _emit_failure_event(idx_dir, project_id, report, reason=f"llm_call_failed: {e}")
        return report

    parsed = parse_synthesis_response(text or "")
    if not parsed:
        report.parse_failure = True
        report.elapsed_seconds = time.time() - t0
        _emit_failure_event(idx_dir, project_id, report, reason="parse_failed_or_empty")
        return report

    # Cap defensively + sort by tier descending so the most important
    # concepts win if the cap fires.
    parsed.sort(key=lambda c: TIER_TO_CONFIDENCE.get(c.tier, 0), reverse=True)
    if len(parsed) > MAX_SYNTHESIZED_CONCEPTS:
        logger.warning(
            "synthesis emitted %d concepts; capping to %d (highest tier first)",
            len(parsed), MAX_SYNTHESIZED_CONCEPTS,
        )
        parsed = parsed[:MAX_SYNTHESIZED_CONCEPTS]

    report.concepts = parsed
    report.total_emitted = len(parsed)

    # Persist with kind='concept'
    try:
        from prep.services.concept_store import concept_store
        save_dicts = [c.to_save_dict() for c in parsed]
        saved, skipped = concept_store.save_many(project_id, save_dicts)
        report.saved = saved
        report.skipped = skipped
    except Exception as e:
        logger.warning("synthesis save_many failed: %s", e, exc_info=True)

    # Telemetry
    try:
        from prep.services.pipeline_telemetry import record_event
        tier_dist: dict[str, int] = {}
        for c in parsed:
            tier_dist[c.tier] = tier_dist.get(c.tier, 0) + 1
        record_event(
            idx_dir,
            "concept_synthesis_complete",
            {
                "total_emitted": report.total_emitted,
                "saved": report.saved,
                "skipped": report.skipped,
                "grounding": report.grounding_summary,
                "tier_distribution": tier_dist,
                "elapsed_seconds": round(time.time() - t0, 2),
            },
            stage="concepts", project_id=project_id,
        )
    except Exception:
        pass

    report.elapsed_seconds = time.time() - t0
    logger.info(
        "[Synth] project=%s emitted=%d saved=%d (tiers: %s) in %.1fs",
        project_id, report.total_emitted, report.saved,
        sorted(set(c.tier for c in parsed)),
        report.elapsed_seconds,
    )

    # Write manifest so the next run can skip if rationale is unchanged.
    if idx_dir is not None and report.saved > 0:
        _write_synth_manifest(idx_dir, {
            "rationale_count": rationale_count,
            "rationale_max_updated_at": rationale_max_ts,
            "synth_completed_at": time.time(),
            "saved": report.saved,
            "total_emitted": report.total_emitted,
        })

    return report
