"""
Role Vectors for Prep Role Composition Engine (Phase 64A).

Defines the RoleVector dataclass — a continuous weight vector over Prep's
existing epistemic dimensions (architecture_layer, domain_tags, centrality,
confidence).  Each built-in role is a preset RoleVector that controls how
the atlas is filtered and compressed for a specific audience.

A role is NOT a category.  It is a lens applied to the same underlying
knowledge graph, adjusting which facets are surfaced and at what detail level.

Zero LLM calls.  Zero pipeline changes.  Pure Python projection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Synonym clusters for fuzzy domain-tag matching ───────────────────

SYNONYM_CLUSTERS: List[frozenset] = [
    frozenset({"ui", "presentation", "frontend", "component", "view", "layout", "widget"}),
    frozenset({"api", "endpoint", "route", "handler", "controller", "rest", "graphql"}),
    frozenset({"auth", "authentication", "authorization", "permission", "security", "token", "credential"}),
    frozenset({"data", "database", "persistence", "storage", "model", "schema", "orm", "migration"}),
    frozenset({"deploy", "infrastructure", "devops", "ci-cd", "docker", "kubernetes", "helm", "terraform"}),
    frozenset({"test", "testing", "spec", "qa", "quality", "coverage", "e2e"}),
    frozenset({"build", "compile", "bundle", "webpack", "vite", "toolchain", "packaging"}),
    frozenset({"docs", "documentation", "readme", "guide", "reference", "wiki"}),
    frozenset({"state", "state-management", "store", "context", "redux", "zustand"}),
    frozenset({"style", "css", "theme", "design-system", "design-token", "styling", "sass"}),
    frozenset({"monitoring", "observability", "logging", "metrics", "tracing", "telemetry"}),
    frozenset({"ml", "machine-learning", "ai", "model-training", "inference", "embedding"}),
]

# Pre-computed lookup:  tag_lower → index into SYNONYM_CLUSTERS
_TAG_TO_CLUSTER: Dict[str, int] = {}
for _idx, _cluster in enumerate(SYNONYM_CLUSTERS):
    for _tag in _cluster:
        _TAG_TO_CLUSTER[_tag] = _idx


def are_synonyms(tag_a: str, tag_b: str) -> bool:
    """Return True if two (lowercased) tags belong to the same synonym cluster."""
    idx_a = _TAG_TO_CLUSTER.get(tag_a)
    idx_b = _TAG_TO_CLUSTER.get(tag_b)
    if idx_a is not None and idx_b is not None:
        return idx_a == idx_b
    return False


def max_tag_affinity(file_tags: List[str], affinity_keywords: List[str]) -> float:
    """Compute max fuzzy affinity between a file's tags and a role's keywords.

    Three strategies per (tag, keyword) pair:
      1. Exact match           → 1.0
      2. Substring containment → 0.7   ("auth" in "authentication")
      3. Synonym cluster match → 0.5   ("ui" ↔ "presentation")

    Returns the best match score across all (tag × keyword) pairs.
    """
    if not file_tags or not affinity_keywords:
        return 0.0

    best = 0.0
    for tag in file_tags:
        tl = tag.lower().replace("-", " ").replace("_", " ")
        for kw in affinity_keywords:
            kl = kw.lower().replace("-", " ").replace("_", " ")

            # 1. Exact
            if tl == kl:
                return 1.0  # can't beat 1.0

            # 2. Substring (either direction)
            if kl in tl or tl in kl:
                best = max(best, 0.7)
                continue

            # 3. Synonym
            if best < 0.5 and are_synonyms(tl.replace(" ", "-"), kl.replace(" ", "-")):
                best = 0.5

    return best


# ── RoleVector dataclass ─────────────────────────────────────────────

@dataclass
class RoleVector:
    """A weighted lens for projecting the codebase atlas to a specific role.

    Fields:
        role_id:            Canonical identifier (lowercase, underscores).
        display_name:       Human-readable role name.
        layer_weights:      Relevance of each architecture_layer (0.0-1.0).
        domain_affinity:    Keywords fuzzy-matched against domain_tags.
        centrality_weight:  Preference for hub files (0.0=niche, 1.0=hubs).
        detail_level:       Output granularity (0.0=executive, 1.0=practitioner).
        max_chars:          Context budget for the projected sub-atlas.
    """
    role_id: str
    display_name: str
    layer_weights: Dict[str, float] = field(default_factory=dict)
    domain_affinity: List[str] = field(default_factory=list)
    centrality_weight: float = 0.5
    detail_level: float = 0.7
    max_chars: int = 3000

    def to_dict(self) -> Dict:
        return {
            "role_id": self.role_id,
            "display_name": self.display_name,
            "layer_weights": self.layer_weights,
            "domain_affinity": self.domain_affinity,
            "centrality_weight": self.centrality_weight,
            "detail_level": self.detail_level,
            "max_chars": self.max_chars,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "RoleVector":
        return cls(
            role_id=d["role_id"],
            display_name=d.get("display_name", d["role_id"]),
            layer_weights=d.get("layer_weights", {}),
            domain_affinity=d.get("domain_affinity", []),
            centrality_weight=float(d.get("centrality_weight", 0.5)),
            detail_level=float(d.get("detail_level", 0.7)),
            max_chars=int(d.get("max_chars", 3000)),
        )

    def copy(self) -> "RoleVector":
        return deepcopy(self)

    def to_json(self) -> str:
        """Serialize to JSON for passing to Rust FFI bridge."""
        import json
        return json.dumps(self.to_dict())

# ── Built-in role vectors ────────────────────────────────────────────

# Architecture layers (from VALID_ARCHITECTURE_LAYERS in epistemic_enrichment.py):
#   presentation, business_logic, data, infrastructure,
#   configuration, testing, documentation, build, unknown

_DEFAULT_LAYERS = {
    "presentation": 0.3,
    "business_logic": 0.5,
    "data": 0.3,
    "infrastructure": 0.2,
    "configuration": 0.2,
    "testing": 0.2,
    "documentation": 0.3,
    "build": 0.1,
    "unknown": 0.1,
}

BUILT_IN_ROLES: Dict[str, RoleVector] = {

    # ── Executive / Strategic ────────────────────────────────────────

    "ceo": RoleVector(
        role_id="ceo",
        display_name="CEO",
        layer_weights={
            "presentation": 0.3, "business_logic": 0.7, "data": 0.4,
            "infrastructure": 0.2, "configuration": 0.1, "testing": 0.2,
            "documentation": 0.8, "build": 0.1, "unknown": 0.1,
        },
        domain_affinity=[
            "architecture", "strategy", "api", "integration", "security",
            "monetization", "user-facing", "product", "analytics",
        ],
        centrality_weight=0.9,
        detail_level=0.2,
        max_chars=1500,
    ),

    "cto": RoleVector(
        role_id="cto",
        display_name="CTO",
        layer_weights={
            "presentation": 0.3, "business_logic": 0.8, "data": 0.6,
            "infrastructure": 0.7, "configuration": 0.3, "testing": 0.4,
            "documentation": 0.7, "build": 0.4, "unknown": 0.1,
        },
        domain_affinity=[
            "architecture", "api", "infrastructure", "security", "scalability",
            "pipeline", "orchestration", "strategy", "deploy",
        ],
        centrality_weight=0.85,
        detail_level=0.4,
        max_chars=2500,
    ),

    # ── Engineering ──────────────────────────────────────────────────

    "engineering": RoleVector(
        role_id="engineering",
        display_name="Software Engineer",
        layer_weights={
            "presentation": 0.5, "business_logic": 0.9, "data": 0.7,
            "infrastructure": 0.4, "configuration": 0.4, "testing": 0.5,
            "documentation": 0.3, "build": 0.3, "unknown": 0.2,
        },
        domain_affinity=[
            # Intent markers — engineering builds service-layer + pipeline systems
            "architecture", "pipeline", "orchestration", "state-management",
            "data-persistence", "error-handling", "concurrency",
            # Service-layer engines (embedder, augmenter, enrichment) — Run 12 calibration
            "embeddings", "vector-search", "llm-integration", "retrieval",
            "trace-augmentation", "semantic-analysis", "pipeline-stage",
            "llm-orchestration", "epistemic-analysis", "knowledge-representation",
            # Engineering-flavored compound terms
            "service-layer", "factory-pattern", "embedder", "augmenter",
            "pipeline-orchestration", "incremental-builds",
        ],
        centrality_weight=0.4,  # surface niche service files over centrality hubs
        detail_level=0.8,
        max_chars=4000,  # budget parity with A's neutral baseline (also 4000)
    ),

    "architect": RoleVector(
        role_id="architect",
        display_name="Software Architect",
        layer_weights={
            "presentation": 0.3, "business_logic": 0.9, "data": 0.7,
            "infrastructure": 0.7, "configuration": 0.5, "testing": 0.3,
            "documentation": 0.6, "build": 0.4, "unknown": 0.1,
        },
        domain_affinity=[
            # Intent markers
            "architecture", "integration", "scalability", "infrastructure",
            "design-patterns",
            # Data-driven additions (compound terms confirmed present as tags)
            "entry-point", "bootstrap",
            "daemon", "daemon-architecture", "daemon-lifecycle",
            "cli", "mcp", "fastapi", "rag",
            "pipeline-orchestration", "llm-orchestration",
            "architecture-audit", "audit-architecture",
            "api",
            # Run 09: hub/dependency/cross-cutting graph vocabulary for gq-a04
            "dependency-graph", "dependency-analysis", "dependency-management",
            "dependency-extraction", "dependency-injection", "dependency-inference",
            "graph-analysis", "code-graph", "trace-graph", "graph-construction",
            "graph-algorithms", "graph-traversal", "graph-engine",
            "knowledge-graph", "cross-platform", "cross-cutting",
            "import-cycle", "centrality", "hub-file",
        ],
        centrality_weight=0.6,  # was 0.8; reduced to surface entry points + leaves, not only hubs
        detail_level=0.8,        # Run 07: 0.7→0.8 crosses manager→practitioner boundary (<=0.7 is manager, role-unscored)
        max_chars=3000,
    ),

    "full_stack": RoleVector(
        role_id="full_stack",
        display_name="Full Stack Developer",
        layer_weights={
            "presentation": 0.8, "business_logic": 0.8, "data": 0.6,
            "infrastructure": 0.3, "configuration": 0.4, "testing": 0.5,
            "documentation": 0.3, "build": 0.3, "unknown": 0.2,
        },
        domain_affinity=[
            "ui", "api", "component", "state-management", "data-persistence",
            "authentication", "routing",
        ],
        centrality_weight=0.5,
        detail_level=0.8,
        max_chars=3500,
    ),

    # ── Design ───────────────────────────────────────────────────────

    "design": RoleVector(
        role_id="design",
        display_name="UX Designer",
        layer_weights={
            "presentation": 0.9, "business_logic": 0.3, "data": 0.2,
            "infrastructure": 0.1, "configuration": 0.3, "testing": 0.3,
            "documentation": 0.6, "build": 0.2, "unknown": 0.1,
        },
        domain_affinity=[
            "ui", "component", "design-system", "layout", "theme", "styling",
            "animation", "responsive", "a11y", "design-token",
        ],
        centrality_weight=0.4,
        detail_level=0.7,
        max_chars=2500,
    ),

    "design_engineer": RoleVector(
        role_id="design_engineer",
        display_name="Design Engineer",
        layer_weights={
            "presentation": 0.85, "business_logic": 0.6, "data": 0.3,
            "infrastructure": 0.1, "configuration": 0.3, "testing": 0.4,
            "documentation": 0.5, "build": 0.2, "unknown": 0.1,
        },
        domain_affinity=[
            "ui", "component", "design-system", "layout", "theme", "styling",
            "api", "state-management", "animation", "responsive",
        ],
        centrality_weight=0.5,
        detail_level=0.75,
        max_chars=3000,
    ),

    # ── Quality & Security ───────────────────────────────────────────

    "qa": RoleVector(
        role_id="qa",
        display_name="QA Engineer",
        layer_weights={
            "presentation": 0.3, "business_logic": 0.6, "data": 0.4,
            "infrastructure": 0.2, "configuration": 0.3, "testing": 0.95,
            "documentation": 0.4, "build": 0.2, "unknown": 0.1,
        },
        domain_affinity=[
            "testing", "error-handling", "validation", "coverage", "api",
            "e2e", "integration", "regression", "fixture",
        ],
        centrality_weight=0.4,
        detail_level=0.7,
        max_chars=2500,
    ),

    "security": RoleVector(
        role_id="security",
        display_name="Security Engineer",
        layer_weights={
            # Run 08: presentation 0.2→0.5 to surface API-layer security (envelopes, middleware, auth routes)
            "presentation": 0.5, "business_logic": 0.5, "data": 0.7,
            "infrastructure": 0.6, "configuration": 0.7, "testing": 0.4,
            "documentation": 0.3, "build": 0.3, "unknown": 0.1,
        },
        domain_affinity=[
            # Intent markers (broad; always useful)
            "security", "authentication", "authorization", "encryption",
            "permission", "credential", "vulnerability",
            # Data-driven additions (compound terms confirmed present in
            # trace_epistemic tag universe as of Phase 103 R3 calibration)
            "admin-policy", "security-policy", "policy-enforcement",
            "access-control", "role-based-access-control",
            "input-sanitization", "cryptography", "cryptographic-hashing",
            "session-management", "credentials", "cors",
            "security-audit", "audit-logging", "audit-trail",
            # Run 08: API-layer security surface (error envelopes, auth middleware, exception filters)
            "api-design", "response-envelope", "error-handling",
            "exception-handling", "middleware", "fastapi",
        ],
        centrality_weight=0.6,
        detail_level=0.8,  # Run 07: 0.7→0.8 crosses manager→practitioner boundary (<=0.7 is manager, role-unscored)
        max_chars=2500,
    ),

    # ── Operations ───────────────────────────────────────────────────

    "devops": RoleVector(
        role_id="devops",
        display_name="DevOps Engineer",
        layer_weights={
            "presentation": 0.1, "business_logic": 0.2, "data": 0.3,
            "infrastructure": 0.9, "configuration": 0.8, "testing": 0.3,
            "documentation": 0.4, "build": 0.9, "unknown": 0.1,
        },
        domain_affinity=[
            "infrastructure", "deploy", "ci-cd", "docker", "kubernetes",
            "monitoring", "build", "pipeline", "terraform", "helm",
        ],
        centrality_weight=0.5,
        detail_level=0.7,
        max_chars=2500,
    ),

    "devsecops": RoleVector(
        role_id="devsecops",
        display_name="DevSecOps Engineer",
        layer_weights={
            "presentation": 0.1, "business_logic": 0.3, "data": 0.5,
            "infrastructure": 0.9, "configuration": 0.8, "testing": 0.5,
            "documentation": 0.4, "build": 0.8, "unknown": 0.1,
        },
        domain_affinity=[
            "security", "auth", "infrastructure", "deploy", "ci-cd",
            "docker", "monitoring", "encryption", "token", "permission",
            "build", "pipeline",
        ],
        centrality_weight=0.6,
        detail_level=0.7,
        max_chars=2500,
    ),

    # ── Product & Content ────────────────────────────────────────────

    "product": RoleVector(
        role_id="product",
        display_name="Product Manager",
        layer_weights={
            "presentation": 0.5, "business_logic": 0.6, "data": 0.3,
            "infrastructure": 0.1, "configuration": 0.1, "testing": 0.2,
            "documentation": 0.8, "build": 0.1, "unknown": 0.1,
        },
        domain_affinity=[
            "feature", "api", "user-facing", "integration", "analytics",
            "product", "monetization", "onboarding",
        ],
        centrality_weight=0.7,
        detail_level=0.35,
        max_chars=2000,
    ),

    "writer": RoleVector(
        role_id="writer",
        display_name="Technical Writer",
        layer_weights={
            "presentation": 0.4, "business_logic": 0.4, "data": 0.3,
            "infrastructure": 0.2, "configuration": 0.3, "testing": 0.2,
            "documentation": 0.95, "build": 0.1, "unknown": 0.1,
        },
        domain_affinity=[
            "documentation", "api", "guide", "reference", "tutorial",
            "readme", "onboarding",
        ],
        centrality_weight=0.5,
        detail_level=0.6,
        max_chars=2500,
    ),

    # ── Data & ML ────────────────────────────────────────────────────

    "data_engineer": RoleVector(
        role_id="data_engineer",
        display_name="Data Engineer",
        layer_weights={
            "presentation": 0.1, "business_logic": 0.5, "data": 0.95,
            "infrastructure": 0.5, "configuration": 0.5, "testing": 0.3,
            "documentation": 0.3, "build": 0.3, "unknown": 0.1,
        },
        domain_affinity=[
            "data", "database", "pipeline", "schema", "migration",
            "etl", "analytics", "storage", "embedding", "ml",
        ],
        centrality_weight=0.5,
        detail_level=0.7,
        max_chars=2500,
    ),

    # ── Personal Assistant / Coordination (Phase 103 broadening) ────
    # Prep isn't only a dev tool. AI agents like OpenClaw operate as
    # personal assistants — focused on plans, decisions, MVP specs, todo
    # lists, and project memory rather than code. These roles serve those
    # non-dev agent personas reading the same codebase atlas.

    "assistant": RoleVector(
        role_id="assistant",
        display_name="Personal Assistant",
        # Heavy documentation lens — assistants live in plans/specs/notes,
        # not code. Some business_logic for understanding what the project
        # actually does. Minimal infra/build awareness.
        layer_weights={
            "presentation": 0.3, "business_logic": 0.4, "data": 0.2,
            "infrastructure": 0.1, "configuration": 0.2, "testing": 0.1,
            "documentation": 0.95, "build": 0.1, "unknown": 0.2,
        },
        domain_affinity=[
            # Planning artifacts (the assistant's primary deliverables)
            "planning", "implementation-plan", "roadmap", "milestone",
            "specification", "spec", "mvp", "requirements",
            "phase", "deliverable", "scope",
            # Decisions, tracking, action items
            "decision-log", "todo", "task", "action-item",
            "status", "tracking", "blocker",
            # Agent-coordination vocabulary (OpenClaw-relevant)
            "agent-architecture", "agent-orchestration",
            "context-engineering", "knowledge-management",
            "tacit-knowledge", "memory",
            # User-facing intent
            "user-facing", "onboarding", "feature",
        ],
        centrality_weight=0.3,  # specs/decisions live in leaves, not graph hubs
        detail_level=0.8,        # practitioner — file-level role-scored selection
        max_chars=4000,
    ),

    "pm": RoleVector(
        role_id="pm",
        display_name="Project Manager",
        # Project managers track operational state — phases, dependencies,
        # blockers — not the strategic vision (that's `product`).
        layer_weights={
            "presentation": 0.3, "business_logic": 0.4, "data": 0.2,
            "infrastructure": 0.2, "configuration": 0.2, "testing": 0.2,
            "documentation": 0.9, "build": 0.2, "unknown": 0.1,
        },
        domain_affinity=[
            "project-management", "roadmap", "milestone", "deliverable",
            "phase", "deadline", "tracking", "status",
            "scheduling", "scope", "blocker",
            "dependency-management", "release-management", "rollout",
            "implementation-plan", "team-coordination",
            "agile", "sprint", "kanban", "retrospective",
            "tech-debt", "technical-debt",
        ],
        centrality_weight=0.5,
        detail_level=0.8,
        max_chars=3500,
    ),

    "researcher": RoleVector(
        role_id="researcher",
        display_name="Research Analyst",
        # Research/analysis — comparisons, evaluations, methodology. Cares
        # about both code (what was built/measured) and docs (findings).
        layer_weights={
            "presentation": 0.2, "business_logic": 0.5, "data": 0.5,
            "infrastructure": 0.2, "configuration": 0.2, "testing": 0.4,
            "documentation": 0.9, "build": 0.2, "unknown": 0.1,
        },
        domain_affinity=[
            "research", "research-engine", "research-strategy",
            "evaluation", "benchmark", "comparison", "ablation",
            "hypothesis", "finding", "experiment",
            "metrics", "measurement", "analysis", "literature",
            "survey", "methodology", "calibration",
            # Prep-research-adjacent vocabulary
            "ai-agent", "agent-architecture", "knowledge-graph",
            "epistemic-analysis", "context-engineering",
            "code-intelligence", "graph-rag",
        ],
        centrality_weight=0.4,
        detail_level=0.8,
        max_chars=4000,
    ),

    # ── Learning / Onboarding ────────────────────────────────────────

    "intern": RoleVector(
        role_id="intern",
        display_name="Intern / New Contributor",
        layer_weights={
            "presentation": 0.5, "business_logic": 0.7, "data": 0.4,
            "infrastructure": 0.3, "configuration": 0.3, "testing": 0.4,
            "documentation": 0.9, "build": 0.3, "unknown": 0.2,
        },
        domain_affinity=[
            "architecture", "api", "documentation", "guide", "tutorial",
            "readme", "onboarding", "component",
        ],
        centrality_weight=0.4,
        detail_level=1.0,
        max_chars=4000,
    ),
}
