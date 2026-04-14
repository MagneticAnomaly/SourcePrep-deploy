"""
Role Resolver for CoDRAG Role Composition Engine (Phase 64A).

Maps arbitrary role strings to RoleVector instances using three strategies:
  A. Exact match against built-in roles
  B. Keyword decomposition + vector blending for compound roles
  C. (Future) LLM-resolved vectors — not in Phase 64A

Examples:
  "CEO"              → exact match → CEO_VECTOR
  "design engineer"  → keyword decomposition → blend(design=0.4, engineering=0.6)
  "Senior QA Lead"   → keywords [qa] + modifiers [senior, lead]
  "xyzzy"            → fallback → engineering vector
"""
from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from .role_vectors import BUILT_IN_ROLES, RoleVector

logger = logging.getLogger(__name__)


# ── Keyword → base role mapping ──────────────────────────────────────

KEYWORD_TO_BASE: Dict[str, str] = {
    # ── Engineering ──────────────────────────────────────────────
    "engineer": "engineering",
    "developer": "engineering",
    "dev": "engineering",
    "programmer": "engineering",
    "coder": "engineering",
    "swe": "engineering",
    "backend": "engineering",
    "frontend": "full_stack",
    "fullstack": "full_stack",
    "full-stack": "full_stack",
    "full_stack": "full_stack",
    "mobile": "full_stack",
    "ios": "full_stack",
    "android": "full_stack",
    "embedded": "engineering",
    "firmware": "engineering",
    "systems": "engineering",
    # ── Design / Creative ────────────────────────────────────────
    "design": "design",
    "designer": "design",
    "ux": "design",
    "ui": "design",
    "creative": "design",
    "art": "design",
    "visual": "design",
    "interaction": "design",
    "motion": "design",
    "brand": "design",
    "researcher": "design",          # UX Researcher → design
    # ── Security ─────────────────────────────────────────────────
    "security": "security",
    "sec": "security",
    "infosec": "security",
    "appsec": "security",
    "penetration": "security",
    "pentest": "security",
    "vulnerability": "security",
    "threat": "security",
    "soc": "security",
    "compliance": "security",
    # ── QA / Testing ─────────────────────────────────────────────
    "qa": "qa",
    "test": "qa",
    "tester": "qa",
    "testing": "qa",
    "quality": "qa",
    "sdet": "qa",
    "automation": "qa",
    "performance": "qa",
    # ── DevOps / Infrastructure ──────────────────────────────────
    "ops": "devops",
    "devops": "devops",
    "sre": "devops",
    "infra": "devops",
    "infrastructure": "devops",
    "platform": "devops",
    "cloud": "devops",
    "reliability": "devops",
    "release": "devops",
    "build": "devops",
    "network": "devops",
    "database": "devops",
    "dba": "devops",
    "administrator": "devops",
    # ── Product / Project ────────────────────────────────────────
    "product": "product",
    "pm": "product",
    "program": "product",
    "project": "product",
    "scrum": "product",
    "agile": "product",
    "owner": "product",
    "analyst": "product",
    "business": "product",
    "strategist": "product",
    "growth": "product",
    # ── Marketing / Content ──────────────────────────────────────
    "marketing": "writer",
    "cmo": "writer",
    "content": "writer",
    "copywriter": "writer",
    "seo": "writer",
    "social": "writer",
    "media": "writer",
    "digital": "writer",
    "communications": "writer",
    "editorial": "writer",
    "producer": "writer",
    # ── Data / AI / ML ───────────────────────────────────────────
    "data": "data_engineer",
    "ml": "data_engineer",
    "ai": "data_engineer",
    "analytics": "data_engineer",
    "scientist": "data_engineer",
    "machine": "data_engineer",
    "learning": "data_engineer",
    "intelligence": "data_engineer",
    "bi": "data_engineer",
    "nlp": "data_engineer",
    "deep": "data_engineer",
    # ── Architecture ─────────────────────────────────────────────
    "architect": "architect",
    "architecture": "architect",
    "solutions": "architect",
    # ── Writing / Documentation ──────────────────────────────────
    "writer": "writer",
    "docs": "writer",
    "documentation": "writer",
    "technical": "writer",
    # ── Executive / Leadership ───────────────────────────────────
    "ceo": "ceo",
    "cto": "cto",
    "cfo": "ceo",
    "coo": "ceo",
    "cio": "cto",               # Tech-leaning exec
    "ciso": "security",         # Security exec
    "cpo": "product",           # Chief Product Officer
    "vp": "cto",
    "director": "cto",
    "exec": "ceo",
    "executive": "ceo",
    "chief": "ceo",
    "board": "ceo",
    "president": "ceo",
    "founder": "ceo",
    "managing": "ceo",
    "partner": "ceo",
    # ── Sales / Business Development ─────────────────────────────
    "sales": "product",
    "account": "product",
    "customer": "product",
    "success": "product",
    "consultant": "product",
    # ── Finance / Legal / HR ─────────────────────────────────────
    "finance": "ceo",           # Finance → executive view
    "financial": "ceo",
    "accountant": "ceo",
    "accounting": "ceo",
    "controller": "ceo",
    "treasurer": "ceo",
    "legal": "security",        # Legal → security/compliance view
    "counsel": "security",
    "attorney": "security",
    "paralegal": "security",
    "regulatory": "security",
    "hr": "product",            # HR → product/people ops view
    "human": "product",
    "talent": "product",
    "recruiter": "product",
    "recruiting": "product",
    "people": "product",
    "compensation": "product",
    # ── Support / DevRel ─────────────────────────────────────────
    "support": "qa",            # Support → QA/user-facing view
    "advocate": "writer",       # DevRel → content view
    "relations": "writer",
    "community": "writer",
    "training": "writer",
    "enablement": "writer",
    # ── Onboarding ───────────────────────────────────────────────
    "intern": "intern",
    "junior": "intern",
    "new": "intern",
    "onboarding": "intern",
}


# Modifiers that adjust the vector instead of selecting a base role
MODIFIER_TERMS = frozenset({
    "senior", "sr", "staff", "principal", "distinguished",
    "junior", "jr", "intern", "associate",
    "lead", "head", "manager", "director",
})

# Which modifiers map to which modifier category
_SENIORITY_UP = frozenset({"senior", "sr", "staff", "principal", "distinguished"})
_SENIORITY_DOWN = frozenset({"junior", "jr", "intern", "associate"})
_LEADERSHIP = frozenset({"lead", "head", "manager", "director"})


# ── Core resolver ────────────────────────────────────────────────────

def resolve_role(role_string: str) -> RoleVector:
    """Resolve an arbitrary role string to a RoleVector.

    Strategy A: Exact match against BUILT_IN_ROLES.
    Strategy B: Keyword decomposition + vector blending.
    Fallback:   engineering vector.

    Args:
        role_string: Free-form role name (e.g., "CEO", "Design Engineer",
                     "Senior QA Lead", "DevSecOps").

    Returns:
        A RoleVector appropriate for the given role.
    """
    if not role_string or not role_string.strip():
        return BUILT_IN_ROLES["engineering"].copy()

    # Normalize: lowercase, strip, replace separators
    # Also split CamelCase/PascalCase (e.g., "QADevOpsLead" → "QA Dev Ops Lead")
    raw = role_string.strip()
    # Insert space before uppercase runs: "QADevOpsLead" → "QA Dev Ops Lead"
    raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)      # camelCase
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", raw) # ACRONYMWord
    normalized = raw.lower()
    normalized = normalized.replace("-", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()  # collapse whitespace

    # ── Strategy A: Exact match ────────────────────────────────────
    # Try the full normalized string against built-in role IDs and display names
    if normalized in BUILT_IN_ROLES:
        return BUILT_IN_ROLES[normalized].copy()

    # Also try with underscores (e.g., "design engineer" → "design_engineer")
    underscore_key = normalized.replace(" ", "_")
    if underscore_key in BUILT_IN_ROLES:
        return BUILT_IN_ROLES[underscore_key].copy()

    # Also match by display name (case-insensitive)
    for role_id, rv in BUILT_IN_ROLES.items():
        if rv.display_name.lower() == normalized:
            return rv.copy()

    # ── Strategy B: Keyword decomposition ──────────────────────────
    tokens = normalized.split()

    base_roles: List[str] = []
    modifiers: List[str] = []

    for token in tokens:
        if token in MODIFIER_TERMS:
            modifiers.append(token)
        elif token in KEYWORD_TO_BASE:
            base_id = KEYWORD_TO_BASE[token]
            if base_id not in base_roles:
                base_roles.append(base_id)
        # else: ignored token (e.g., "of", "and", "the")

    if not base_roles:
        # No recognizable keywords — fall back to engineering
        logger.debug("Role '%s' did not match any keywords, defaulting to engineering", role_string)
        vector = BUILT_IN_ROLES["engineering"].copy()
    elif len(base_roles) == 1:
        vector = BUILT_IN_ROLES[base_roles[0]].copy()
    else:
        # Blend multiple base roles with equal weights
        weighted = [
            (BUILT_IN_ROLES[rid], 1.0 / len(base_roles))
            for rid in base_roles
        ]
        vector = blend_vectors(weighted, role_id=underscore_key, display_name=role_string.strip())

    # Apply modifiers
    for mod in modifiers:
        vector = apply_modifier(vector, mod)

    return vector


# ── Vector blending ──────────────────────────────────────────────────

def blend_vectors(
    weighted_roles: List[Tuple[RoleVector, float]],
    role_id: str = "blended",
    display_name: str = "Blended Role",
) -> RoleVector:
    """Blend multiple RoleVectors with weights.

    Each role contributes proportionally to the blended vector.
    Layer weights, centrality, detail_level, and max_chars are all
    blended via weighted average.  Domain affinity keywords are unioned
    (deduplicated, order preserved).

    Args:
        weighted_roles: List of (RoleVector, weight) tuples.
        role_id:        ID for the blended result.
        display_name:   Display name for the blended result.

    Returns:
        A new RoleVector with blended values.
    """
    if not weighted_roles:
        return BUILT_IN_ROLES["engineering"].copy()

    if len(weighted_roles) == 1:
        rv = weighted_roles[0][0].copy()
        rv.role_id = role_id
        rv.display_name = display_name
        return rv

    # Normalize weights to sum to 1.0
    total = sum(w for _, w in weighted_roles)
    if total <= 0:
        total = 1.0
    normed = [(v, w / total) for v, w in weighted_roles]

    # Blend layer weights
    all_layers = set()
    for v, _ in normed:
        all_layers.update(v.layer_weights.keys())

    blended_layers: Dict[str, float] = {}
    for layer in all_layers:
        blended_layers[layer] = round(
            sum(v.layer_weights.get(layer, 0.0) * w for v, w in normed), 3
        )

    # Union domain affinity (deduplicated, order preserved)
    seen_kw: set = set()
    domain: List[str] = []
    for v, _ in normed:
        for kw in v.domain_affinity:
            if kw not in seen_kw:
                domain.append(kw)
                seen_kw.add(kw)

    # Blend scalars
    centrality = round(sum(v.centrality_weight * w for v, w in normed), 3)
    detail = round(sum(v.detail_level * w for v, w in normed), 3)
    budget = int(sum(v.max_chars * w for v, w in normed))

    return RoleVector(
        role_id=role_id,
        display_name=display_name,
        layer_weights=blended_layers,
        domain_affinity=domain,
        centrality_weight=centrality,
        detail_level=detail,
        max_chars=budget,
    )


# ── Modifier application ────────────────────────────────────────────

def apply_modifier(vector: RoleVector, modifier: str) -> RoleVector:
    """Apply a seniority/leadership modifier to a RoleVector.

    Modifiers adjust the vector without changing its base role identity:
      - senior/staff:    less detail, more strategic (higher centrality)
      - junior/intern:   more detail, more docs, bigger budget
      - lead/manager:    higher centrality, + testing visibility

    Args:
        vector: The base RoleVector to modify (will be copied).
        modifier: One of the MODIFIER_TERMS.

    Returns:
        A new modified RoleVector.
    """
    v = vector.copy()

    if modifier in _SENIORITY_UP:
        # Senior: less hand-holding, more strategic awareness
        v.detail_level = max(0.1, v.detail_level - 0.15)
        v.centrality_weight = min(1.0, v.centrality_weight + 0.1)
        v.max_chars = max(1000, v.max_chars - 300)

    elif modifier in _SENIORITY_DOWN:
        # Junior/intern: more detail, more docs, bigger budget
        v.detail_level = min(1.0, v.detail_level + 0.2)
        v.max_chars = int(v.max_chars * 1.3)
        v.layer_weights = dict(v.layer_weights)  # defensive copy
        v.layer_weights["documentation"] = min(
            1.0, v.layer_weights.get("documentation", 0.3) + 0.3
        )
        v.layer_weights["testing"] = min(
            1.0, v.layer_weights.get("testing", 0.2) + 0.15
        )

    elif modifier in _LEADERSHIP:
        # Lead: more strategic, quality-aware
        v.centrality_weight = min(1.0, v.centrality_weight + 0.2)
        v.detail_level = max(0.1, v.detail_level - 0.1)
        v.layer_weights = dict(v.layer_weights)
        v.layer_weights["testing"] = min(
            1.0, v.layer_weights.get("testing", 0.3) + 0.2
        )

    return v


# ── Task → Role inference (Phase 103 R4) ─────────────────────────────

def _build_role_term_idf() -> Dict[str, float]:
    """Compute IDF-style weights for every domain_affinity term across roles.

    Terms appearing in many role vectors (e.g. 'api' shows up in CEO,
    CTO, architect, etc.) are poor discriminators for role inference
    and should contribute less to the score. Terms appearing in one
    or two roles (e.g. 'admin-policy', 'storybook', 'daemon-architecture')
    are strong signals and should weigh more.

    Weight formula: 1 / sqrt(n_roles_containing_term). Capped at 1.0
    for terms unique to a single role. Called lazily on first use.
    """
    import math
    counts: Dict[str, int] = {}
    for rv in BUILT_IN_ROLES.values():
        seen_in_role = set()
        for term in rv.domain_affinity:
            tn = re.sub(r"[-_]", " ", term.lower())
            if tn in seen_in_role:
                continue
            seen_in_role.add(tn)
            counts[tn] = counts.get(tn, 0) + 1
    return {t: min(1.0, 1.0 / math.sqrt(n)) for t, n in counts.items()}


_ROLE_TERM_IDF: Optional[Dict[str, float]] = None


def infer_role_from_task(task: str, min_confidence: float = 0.9) -> Tuple[Optional[str], float]:
    """Infer the best-matching built-in role for a free-form task description.

    Scoring (Phase 103 R4 v2):
      - Normalize hyphens/underscores to spaces in both task and terms so
        compound domain terms like 'admin-policy' match 'admin policy'.
      - Each (role, term) hit contributes IDF-style weight: terms present
        in many roles score low (poor discriminators); terms unique to a
        role score 1.0 (strong signal).
      - Whole-word hits count fully; in-compound substring hits count 50%.

    Returns None when confidence is below threshold so callers can fall
    back to the uniform atlas rather than project through a guessed role.

    Args:
        task: Free-form task text.
        min_confidence: IDF-weighted minimum score. Default 0.9 ≈ one
            moderately-discriminative term or two weak ones.

    Returns:
        (role_id, score) when score >= min_confidence.
        (None, best_score) otherwise.
    """
    if not task or not task.strip():
        return (None, 0.0)

    global _ROLE_TERM_IDF
    if _ROLE_TERM_IDF is None:
        _ROLE_TERM_IDF = _build_role_term_idf()
    idf = _ROLE_TERM_IDF

    def _norm(s: str) -> str:
        return re.sub(r"[-_]", " ", s.lower())

    task_norm = _norm(task)
    task_words = set(re.findall(r"[a-z][a-z0-9]+", task_norm))

    best_role: Optional[str] = None
    best_score: float = 0.0

    for role_id, rv in BUILT_IN_ROLES.items():
        score = 0.0
        for term in rv.domain_affinity:
            tn = _norm(term)
            w = idf.get(tn, 1.0)
            if " " in tn:
                if tn in task_norm:
                    score += 1.0 * w
            else:
                if tn in task_words:
                    score += 1.0 * w
                elif len(tn) >= 4 and tn in task_norm:
                    score += 0.5 * w
        if score > best_score:
            best_score = score
            best_role = role_id

    if best_score >= min_confidence:
        return (best_role, best_score)
    return (None, best_score)


def resolve_role_from_task_or_slug(
    role_slug: Optional[str] = None,
    task: Optional[str] = None,
) -> Tuple[RoleVector, str]:
    """Unified entry point for Phase 103 R4 universal API.

    Resolution order (first non-empty wins):
      1. Explicit role_slug → resolve_role(slug) — always trusted.
      2. Task → infer_role_from_task(task) — used when confident.
      3. Neither / low confidence → caller decides (uniform atlas).

    Returns (RoleVector, source) where source ∈
        {"explicit", "inferred", "default"}.
    """
    if role_slug and role_slug.strip():
        return (resolve_role(role_slug), "explicit")

    if task and task.strip():
        inferred, score = infer_role_from_task(task)
        if inferred is not None:
            return (resolve_role(inferred), "inferred")

    # No strong signal — caller should treat as uniform/neutral.
    # Return the engineering default to preserve existing callers that
    # always expect a RoleVector, but flag the source as "default".
    return (BUILT_IN_ROLES["engineering"].copy(), "default")
