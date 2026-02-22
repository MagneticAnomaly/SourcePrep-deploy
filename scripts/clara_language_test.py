#!/usr/bin/env python3
"""
CLaRa Language-Only Compression Test — Phase 31B

Tests CLaRa on the NATURAL LANGUAGE content in CoDRAG's pipeline:
1. Augmentation summaries (trace_augmented.jsonl)
2. Epistemic enrichments (trace_epistemic.jsonl)
3. Module descriptions (trace_modules.jsonl)
4. User markdown documentation chunks
5. Atlas segment descriptions

Validates that CLaRa preserves key facts, domain tags, file references,
and architectural concepts when compressing language content.

Usage:
    # Run against live CLaRa server with realistic synthetic data
    python scripts/clara_language_test.py

    # Use real project data (reads from project index dir)
    python scripts/clara_language_test.py --project-dir /path/to/codrag_data/projects/<id>

    # Quick test (2 scenarios)
    python scripts/clara_language_test.py --quick
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clara_language")


# ---------------------------------------------------------------------------
# Realistic test data — modeled after real CoDRAG pipeline output
# ---------------------------------------------------------------------------

# Augmentation summaries (from trace_augmented.jsonl)
AUGMENTATION_MEMORIES = [
    "File: src/codrag/core/index.py\nRole: core\nSummary: Core search index module. Manages document chunks and their embeddings. Provides cosine similarity search with role weights, path weights, intent multipliers, keyword boosts, and FTS boosts. Supports incremental rebuilding by tracking file content hashes. Implements adaptive-K cutoff and MMR diversity reranking.",
    "File: src/codrag/core/trace.py\nRole: core\nSummary: Trace graph builder. Constructs a directed graph of file-level and symbol-level dependencies using the Rust engine (codrag-parser). Tracks imports, function calls, class inheritance, and cross-file references. Produces trace_nodes.jsonl and trace_edges.jsonl.",
    "File: src/codrag/core/embedder.py\nRole: core\nSummary: Embedding abstraction layer. Provides NativeEmbedder (ONNX, nomic-embed-text-v1.5, 768 dims) and OllamaEmbedder (API-based, supports nomic-embed-text, nomic-embed-code). Handles Matryoshka dimension truncation and L2 normalization.",
    "File: src/codrag/core/compressor.py\nRole: core\nSummary: Context compression abstraction. ClaraCompressor sends memories to the CLaRa server for semantic compression. NoopCompressor passes text through unchanged. Used by the context endpoint to optionally reduce output size.",
    "File: src/codrag/core/atlas.py\nRole: core\nSummary: Codebase atlas and routing system. Generates natural language descriptions of codebase segments. Implements pre-retrieval routing via SegmentDescriptor embeddings. Routes queries to relevant subsystems before main search runs.",
    "File: src/codrag/api/routers/projects.py\nRole: api\nSummary: Project management API endpoints. Handles project CRUD, search, context retrieval, trace operations, and build management. The /context endpoint is the primary entry point for MCP tool calls.",
    "File: src/codrag/core/knowledge.py\nRole: core\nSummary: Knowledge vector index. Indexes augmentation summaries, epistemic enrichments, and module descriptions into a secondary search index. Enables semantic search over conceptual descriptions rather than literal code.",
    "File: src/codrag/core/augmenter.py\nRole: core\nSummary: LLM-powered file augmentation. Generates summaries, role classifications, and related file hypotheses for every traced file. Uses separate prompts for code files and markdown documents. Includes synthetic fallback for LLM failures.",
    "File: src/codrag/core/repo_profile.py\nRole: utility\nSummary: Repository profiling and classification. Scans top-level directory structure to detect languages, frameworks, and project type. Assigns role weights (code=1.0, docs=0.85, tests=0.95). Classifies paths into code/docs/tests/other roles.",
    "File: src/codrag/core/watcher.py\nRole: core\nSummary: File system watcher. Monitors project directories for changes using watchdog. Triggers incremental index rebuilds when files are created, modified, or deleted. Debounces rapid changes to avoid redundant builds.",
]

# Epistemic enrichments (from trace_epistemic.jsonl)
EPISTEMIC_MEMORIES = [
    "File: src/codrag/core/index.py\nDomain: search, indexing, vector-retrieval, ranking\nLayer: core-engine\nSummary: Central search orchestrator. Combines embedding similarity with multi-signal boosting (keywords, FTS, primers, segments). The search() method is the most-called function in the entire codebase with 15 direct callers. Implements three context assembly modes: plain string, structured with metadata, and trace-expanded with graph neighbors.",
    "File: src/codrag/core/trace.py\nDomain: static-analysis, dependency-graph, code-understanding\nLayer: core-engine\nSummary: Structural backbone of CoDRAG. The trace graph captures import relationships, function calls, and containment edges across the entire project. Used by 8 downstream consumers including augmentation, epistemic scoring, atlas generation, and trace expansion. The Rust engine processes ~500 files in under 100ms.",
    "File: src/codrag/core/atlas.py\nDomain: navigation, routing, codebase-mapping, segmentation\nLayer: orchestration\nSummary: Strategic navigation layer. Segments the codebase into logical subsystems based on directory structure and module clustering. Routing descriptors embed domain vocabulary for pre-retrieval query routing. Atlas narratives provide high-level codebase orientation for AI tools.",
    "File: src/codrag/dashboard/src/App.tsx\nDomain: ui, dashboard, monitoring, project-management\nLayer: presentation\nSummary: Main dashboard application component. Manages global state for project selection, build status, trace coverage, and deep analysis progress. Renders panel-based layout with 12+ configurable panels. Fetches data from the CoDRAG API on project change.",
    "File: src/codrag/core/pipeline_orchestrator.py\nDomain: pipeline, orchestration, deep-analysis, scheduling\nLayer: orchestration\nSummary: Deep analysis pipeline controller. Orchestrates the 8-stage pipeline: trace → augment → validate → enrich → cluster → deepen → atlas → knowledge. Manages worker threads, progress reporting, and automatic scheduling. Budget-aware: respects token limits per time window.",
]

# Module descriptions (from trace_modules.jsonl)
MODULE_MEMORIES = [
    "Module: Core Search Engine\nFiles: index.py, embedder.py, chunking.py, repo_profile.py, repo_policy.py\nPurpose: Handles all semantic search operations including document chunking, embedding generation, similarity computation, and multi-signal ranking. This is the performance-critical path for every MCP tool call.",
    "Module: Trace & Analysis Pipeline\nFiles: trace.py, augmenter.py, epistemic_score.py, epistemic_enrichment.py, pipeline_orchestrator.py\nPurpose: Builds and enriches the structural understanding of the codebase. Starts with static analysis (trace graph), adds LLM summaries (augmentation), validates relationships, and deepens understanding through iterative enrichment.",
    "Module: Atlas & Navigation\nFiles: atlas.py, knowledge.py, compressor.py\nPurpose: Provides high-level codebase orientation and intelligent routing. Atlas generates natural language maps of the codebase. Knowledge index enables conceptual search. Routing directs queries to relevant subsystems before search.",
    "Module: API & Server\nFiles: server.py, projects.py, build.py, search.py, mcp_server.py, mcp_tools.py\nPurpose: HTTP API layer and MCP integration. Exposes all CoDRAG functionality via REST endpoints. The MCP server provides codrag_context, codrag_search, and codrag_atlas tools for AI coding assistants.",
]

# User documentation chunks (from .md files in user's repo)
DOC_MEMORIES = [
    "# Architecture Overview\n\nCoDRAG uses a layered architecture with three main subsystems:\n\n1. **Core Engine** — Handles indexing, search, and embedding. Uses nomic-embed-text-v1.5 (768-dim ONNX) for zero-dependency semantic search.\n\n2. **Deep Analysis Pipeline** — 8-stage pipeline that builds structural understanding: trace → augment → validate → enrich → cluster → deepen → atlas → knowledge.\n\n3. **Integration Layer** — MCP server for AI tool integration, REST API for dashboard, file watcher for auto-rebuild.\n\nThe trace graph is the structural backbone. Every file and symbol becomes a node, with edges for imports, calls, and containment. This graph feeds augmentation (LLM summaries), epistemic scoring (confidence metrics), and atlas generation (codebase maps).",
    "# Search Pipeline\n\nWhen a query arrives via the MCP `codrag_context` tool:\n\n1. The query is embedded using nomic-embed-text-v1.5\n2. Cosine similarity is computed against all chunk embeddings\n3. Keyword boosts are added for exact term matches\n4. FTS (full-text search) boosts are added from the SQLite FTS5 index\n5. Primer boosts elevate always-relevant files (e.g., README)\n6. Atlas routing boosts files in query-relevant segments\n7. Role weights adjust scores by file type (code=1.0, docs=0.85)\n8. Intent multipliers adjust by query type (code intent boosts code files)\n9. Path weights apply user-defined per-folder adjustments\n10. Adaptive-K truncates results when score drops sharply\n11. MMR reranking diversifies the final result set\n12. Top-K results are assembled into a context string with file headers\n\nThe entire pipeline runs in <100ms for a 1000-file project.",
    "# Configuration Guide\n\n## Path Weights\n\nPath weights let you boost or suppress specific directories:\n\n```json\n{\n  \"src/core/\": 1.5,\n  \"docs/\": 0.5,\n  \"vendor/\": 0.2\n}\n```\n\nWeights multiply the similarity score. A weight of 1.5 means chunks from that directory score 50% higher. A weight of 0.2 means they score 80% lower.\n\n## Role Weights\n\nDefault role weights:\n- code: 1.0 (no adjustment)\n- docs: 0.85 (15% penalty — prevents documentation from drowning code)\n- tests: 0.95 (5% penalty)\n- other: 0.80 (20% penalty)\n\n## Min Score\n\nDefault: 0.15. Chunks scoring below this are dropped entirely. Raise to 0.25 for higher precision, lower to 0.10 for broader recall.",
    "# MCP Integration\n\nCoDRAG exposes three MCP tools:\n\n- **codrag_context** — Primary tool. Returns relevant code context for a query. Used by Cursor, Windsurf, and Claude Code for codebase-aware responses.\n- **codrag_search** — Returns search results with metadata (scores, file paths, roles). Useful for exploration.\n- **codrag_atlas** — Returns the codebase atlas narrative. Gives the AI tool a high-level understanding of project structure.\n\nThe MCP server runs as a stdio process spawned by the AI tool. It connects to the CoDRAG daemon via HTTP on port 8400.",
]

# Atlas segment descriptions
ATLAS_MEMORIES = [
    "Segment: src/codrag/core (Core Engine)\nCovers: search indexing embedding trace graph analysis ranking scoring\nModules: Core Search Engine, Trace & Analysis Pipeline\nKey files: index, trace, embedder, augmenter, atlas\nThis segment contains the performance-critical search and analysis infrastructure. It handles document chunking, embedding generation, cosine similarity search, trace graph construction, and the deep analysis pipeline.",
    "Segment: src/codrag/api (API Layer)\nCovers: http rest endpoints projects builds search context mcp\nModules: API & Server\nKey files: server, projects, build, search\nThis segment exposes CoDRAG's functionality via REST endpoints. The /projects/{id}/context endpoint is the primary entry point for all MCP tool calls. It orchestrates search, trace expansion, atlas routing, and optional CLaRa compression.",
    "Segment: src/codrag/dashboard (Dashboard UI)\nCovers: react typescript panels monitoring status configuration\nModules: Dashboard\nKey files: App, panelRegistry, useDashboardPanels\nThis segment contains the web dashboard for monitoring CoDRAG projects. It provides real-time status for builds, traces, deep analysis, and search testing. Built with React, TypeScript, and Tailwind CSS.",
]


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

@dataclass
class LanguageTestScenario:
    """A test scenario combining different language content types."""
    name: str
    query: str
    memories: List[str]
    expected_facts: List[str]
    expected_file_refs: List[str]  # File paths that should survive
    expected_concepts: List[str]  # Domain concepts that should survive
    content_types: List[str]  # What types of content are included


SCENARIOS: List[LanguageTestScenario] = [
    LanguageTestScenario(
        name="augmentations_only",
        query="How does the search and indexing system work in this codebase?",
        memories=AUGMENTATION_MEMORIES,
        expected_facts=[
            "cosine similarity", "role weights", "path weights",
            "adaptive-K", "MMR", "incremental", "embeddings",
        ],
        expected_file_refs=[
            "index.py", "embedder.py", "trace.py", "repo_profile.py",
        ],
        expected_concepts=[
            "search", "index", "embedding", "ranking", "boost",
        ],
        content_types=["augmentation"],
    ),
    LanguageTestScenario(
        name="epistemic_only",
        query="What are the main architectural layers and how do they relate?",
        memories=EPISTEMIC_MEMORIES,
        expected_facts=[
            "core-engine", "orchestration", "presentation",
            "8-stage pipeline", "trace graph", "routing",
        ],
        expected_file_refs=[
            "index.py", "trace.py", "atlas.py", "pipeline_orchestrator.py",
        ],
        expected_concepts=[
            "search", "trace", "atlas", "pipeline", "dashboard",
            "dependency", "navigation",
        ],
        content_types=["epistemic"],
    ),
    LanguageTestScenario(
        name="modules_only",
        query="What are the major subsystems and what does each one do?",
        memories=MODULE_MEMORIES,
        expected_facts=[
            "Core Search Engine", "Trace & Analysis Pipeline",
            "Atlas & Navigation", "API & Server",
        ],
        expected_file_refs=[
            "index.py", "trace.py", "atlas.py", "server.py", "mcp",
        ],
        expected_concepts=[
            "search", "trace", "atlas", "MCP", "knowledge",
            "augmentation", "enrichment", "routing",
        ],
        content_types=["module"],
    ),
    LanguageTestScenario(
        name="docs_only",
        query="How does the search pipeline process a query from start to finish?",
        memories=DOC_MEMORIES,
        expected_facts=[
            "nomic-embed-text", "cosine similarity", "keyword boost",
            "FTS", "primer", "role weights", "intent",
            "adaptive-K", "MMR", "path weights",
        ],
        expected_file_refs=[
            "codrag_context", "codrag_search", "codrag_atlas",
        ],
        expected_concepts=[
            "MCP", "search", "embedding", "ranking", "context",
            "trace", "atlas", "routing",
        ],
        content_types=["docs"],
    ),
    LanguageTestScenario(
        name="mixed_language_full",
        query="Give me a comprehensive overview of the CoDRAG system architecture and how search works",
        memories=(
            AUGMENTATION_MEMORIES[:5]
            + EPISTEMIC_MEMORIES[:3]
            + MODULE_MEMORIES[:2]
            + DOC_MEMORIES[:2]
            + ATLAS_MEMORIES[:2]
        ),
        expected_facts=[
            "cosine similarity", "trace graph", "8-stage pipeline",
            "nomic-embed-text", "Core Search Engine", "MCP",
            "atlas", "routing", "augmentation",
        ],
        expected_file_refs=[
            "index.py", "trace.py", "atlas.py", "embedder.py",
        ],
        expected_concepts=[
            "search", "indexing", "trace", "embedding", "pipeline",
            "atlas", "routing", "MCP", "knowledge",
        ],
        content_types=["augmentation", "epistemic", "module", "docs", "atlas"],
    ),
    LanguageTestScenario(
        name="atlas_routing",
        query="How does atlas routing direct queries to the right part of the codebase?",
        memories=ATLAS_MEMORIES + AUGMENTATION_MEMORIES[4:6] + EPISTEMIC_MEMORIES[2:3],
        expected_facts=[
            "SegmentDescriptor", "routing", "pre-retrieval",
            "domain vocabulary", "cosine similarity",
        ],
        expected_file_refs=[
            "atlas.py", "projects.py",
        ],
        expected_concepts=[
            "segment", "routing", "query", "search", "boost",
        ],
        content_types=["atlas", "augmentation", "epistemic"],
    ),
]

QUICK_SCENARIOS = [SCENARIOS[0], SCENARIOS[4]]  # augmentations_only + mixed_full


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass
class LanguageTestResult:
    """Result of a single language compression test."""
    scenario_name: str
    query: str
    content_types: List[str]

    input_chars: int = 0
    input_memories: int = 0
    output_chars: int = 0
    compression_ratio: float = 1.0
    latency_ms: float = 0.0

    # Retention
    facts_retained: List[str] = field(default_factory=list)
    facts_total: int = 0
    facts_pct: float = 0.0

    file_refs_retained: List[str] = field(default_factory=list)
    file_refs_total: int = 0
    file_refs_pct: float = 0.0

    concepts_retained: List[str] = field(default_factory=list)
    concepts_total: int = 0
    concepts_pct: float = 0.0

    overall_retention_pct: float = 0.0

    # Hallucination
    hallucinated_names: List[str] = field(default_factory=list)

    # Output preview
    output_preview: str = ""

    error: Optional[str] = None


def check_items(output: str, items: List[str]) -> Tuple[List[str], float]:
    """Check which items appear in output (case-insensitive)."""
    retained = []
    out_lower = output.lower()
    for item in items:
        if item.lower() in out_lower:
            retained.append(item)
        elif item.replace("-", " ").lower() in out_lower:
            retained.append(item)
        elif item.replace("_", " ").lower() in out_lower:
            retained.append(item)
    pct = (len(retained) / len(items) * 100) if items else 100.0
    return retained, pct


def detect_hallucinated_files(output: str, all_input: str) -> List[str]:
    """Detect file references in output that weren't in input."""
    # Extract .py/.ts/.tsx/.js file references from output
    output_files = set(re.findall(r"\b[\w/]+\.(?:py|ts|tsx|js|rs)\b", output))
    input_files = set(re.findall(r"\b[\w/]+\.(?:py|ts|tsx|js|rs)\b", all_input))
    return sorted(output_files - input_files)


def run_scenario(
    clara_url: str,
    scenario: LanguageTestScenario,
    max_new_tokens: int = 512,
    timeout_s: float = 120.0,
) -> LanguageTestResult:
    """Run a single language test scenario."""
    all_input = "\n\n---\n\n".join(scenario.memories)

    result = LanguageTestResult(
        scenario_name=scenario.name,
        query=scenario.query,
        content_types=scenario.content_types,
        input_chars=len(all_input),
        input_memories=len(scenario.memories),
        facts_total=len(scenario.expected_facts),
        file_refs_total=len(scenario.expected_file_refs),
        concepts_total=len(scenario.expected_concepts),
    )

    payload = {
        "memories": scenario.memories,
        "query": scenario.query,
        "max_new_tokens": max_new_tokens,
    }

    t0 = time.monotonic()
    try:
        resp = requests.post(f"{clara_url}/compress", json=payload, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        result.error = str(e)
        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    result.latency_ms = round((time.monotonic() - t0) * 1000, 1)

    if not data.get("success"):
        result.error = data.get("error", "CLaRa returned success=false")
        return result

    output = data.get("answer", "")
    result.output_chars = len(output)
    result.compression_ratio = round(len(all_input) / max(len(output), 1), 1)
    result.output_preview = output[:500]

    # Check retention
    result.facts_retained, result.facts_pct = check_items(output, scenario.expected_facts)
    result.file_refs_retained, result.file_refs_pct = check_items(output, scenario.expected_file_refs)
    result.concepts_retained, result.concepts_pct = check_items(output, scenario.expected_concepts)

    # Overall
    all_expected = scenario.expected_facts + scenario.expected_file_refs + scenario.expected_concepts
    _, result.overall_retention_pct = check_items(output, all_expected)

    # Hallucination
    result.hallucinated_names = detect_hallucinated_files(output, all_input)

    return result


# ---------------------------------------------------------------------------
# Real project data loading
# ---------------------------------------------------------------------------

def load_real_project_data(project_dir: Path) -> List[LanguageTestScenario]:
    """Load real augmentation/epistemic/module data from a project index dir."""
    scenarios: List[LanguageTestScenario] = []
    memories: List[str] = []
    content_types: List[str] = []

    # Load augmentations
    aug_path = project_dir / "trace_augmented.jsonl"
    if aug_path.exists():
        with open(aug_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    summary = entry.get("summary", "")
                    if summary and len(summary) > 20:
                        mem = f"File: {entry.get('node_id', '?')}\nRole: {entry.get('role', '?')}\nSummary: {summary}"
                        memories.append(mem)
                except json.JSONDecodeError:
                    continue
        if memories:
            content_types.append("augmentation")
            logger.info("Loaded %d augmentation memories", len(memories))

    # Load epistemic
    epi_path = project_dir / "trace_epistemic.jsonl"
    epi_memories: List[str] = []
    if epi_path.exists():
        with open(epi_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    summary = entry.get("extended_summary") or entry.get("one_liner", "")
                    if summary and len(summary) > 20:
                        tags = ", ".join(entry.get("domain_tags", []))
                        layer = entry.get("architecture_layer", "unknown")
                        mem = f"File: {entry.get('node_id', '?')}\nDomain: {tags}\nLayer: {layer}\nSummary: {summary}"
                        epi_memories.append(mem)
                except json.JSONDecodeError:
                    continue
        if epi_memories:
            content_types.append("epistemic")
            logger.info("Loaded %d epistemic memories", len(epi_memories))

    # Load modules
    mod_path = project_dir / "trace_modules.jsonl"
    mod_memories: List[str] = []
    if mod_path.exists():
        with open(mod_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    name = entry.get("name", "")
                    desc = entry.get("description") or entry.get("purpose", "")
                    files = entry.get("files", [])
                    if name and desc:
                        mem = f"Module: {name}\nFiles: {', '.join(files[:10])}\nPurpose: {desc}"
                        mod_memories.append(mem)
                except json.JSONDecodeError:
                    continue
        if mod_memories:
            content_types.append("module")
            logger.info("Loaded %d module memories", len(mod_memories))

    if not memories and not epi_memories and not mod_memories:
        logger.warning("No language data found in %s", project_dir)
        return []

    # Build scenario with a sample of real data
    all_memories = memories[:15] + epi_memories[:10] + mod_memories[:5]
    file_refs = []
    for m in all_memories:
        refs = re.findall(r"File:\s*(.+?)(?:\n|$)", m)
        file_refs.extend(refs)

    scenarios.append(LanguageTestScenario(
        name="real_project_mixed",
        query="Give me a comprehensive overview of this codebase's architecture and key components",
        memories=all_memories,
        expected_facts=[],  # Can't know in advance
        expected_file_refs=file_refs[:10],
        expected_concepts=["search", "index", "trace", "api"],  # Generic
        content_types=content_types,
    ))

    return scenarios


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results(results: List[LanguageTestResult], code_baseline: Optional[Dict] = None) -> None:
    """Print comparison table."""
    print("\n" + "═" * 80)
    print("  CLaRa Language-Only Compression Results")
    print("═" * 80)

    # Per-scenario results
    for r in results:
        status = "✓" if not r.error else f"✗ {r.error[:40]}"
        print(f"\n  [{status}] {r.scenario_name}")
        print(f"      Types:       {', '.join(r.content_types)}")
        print(f"      Input:       {r.input_memories} memories, {r.input_chars:,} chars")
        print(f"      Output:      {r.output_chars:,} chars ({r.compression_ratio}× compression)")
        print(f"      Latency:     {r.latency_ms:.0f}ms")
        if not r.error:
            print(f"      Facts:       {len(r.facts_retained)}/{r.facts_total} ({r.facts_pct:.0f}%)")
            print(f"      File refs:   {len(r.file_refs_retained)}/{r.file_refs_total} ({r.file_refs_pct:.0f}%)")
            print(f"      Concepts:    {len(r.concepts_retained)}/{r.concepts_total} ({r.concepts_pct:.0f}%)")
            print(f"      Overall:     {r.overall_retention_pct:.0f}%")
            if r.hallucinated_names:
                print(f"      Halluc:      {len(r.hallucinated_names)} ({', '.join(r.hallucinated_names[:5])})")
            print(f"      Preview:     {r.output_preview[:200]}...")

    # Summary
    ok = [r for r in results if not r.error]
    if ok:
        avg_facts = sum(r.facts_pct for r in ok) / len(ok)
        avg_refs = sum(r.file_refs_pct for r in ok) / len(ok)
        avg_concepts = sum(r.concepts_pct for r in ok) / len(ok)
        avg_overall = sum(r.overall_retention_pct for r in ok) / len(ok)
        avg_ratio = sum(r.compression_ratio for r in ok) / len(ok)
        avg_latency = sum(r.latency_ms for r in ok) / len(ok)
        avg_halluc = sum(len(r.hallucinated_names) for r in ok) / len(ok)

        print("\n" + "─" * 60)
        print("  LANGUAGE CONTENT SUMMARY")
        print("─" * 60)
        print(f"  Tests passed:      {len(ok)}/{len(results)}")
        print(f"  Avg facts:         {avg_facts:.0f}%")
        print(f"  Avg file refs:     {avg_refs:.0f}%")
        print(f"  Avg concepts:      {avg_concepts:.0f}%")
        print(f"  Avg overall:       {avg_overall:.0f}%")
        print(f"  Avg compression:   {avg_ratio:.1f}×")
        print(f"  Avg latency:       {avg_latency:.0f}ms")
        print(f"  Avg hallucinations:{avg_halluc:.1f}")

        # Compare against code baseline (Phase B results)
        if code_baseline:
            print("\n" + "─" * 60)
            print("  LANGUAGE vs CODE COMPARISON")
            print("─" * 60)
            print(f"  {'Metric':<25} {'Code (Phase B)':>15} {'Language':>15} {'Delta':>10}")
            print(f"  {'─'*25} {'─'*15} {'─'*15} {'─'*10}")

            cb = code_baseline
            print(f"  {'Overall retention':<25} {cb['overall']:>14.0f}% {avg_overall:>14.0f}% {avg_overall - cb['overall']:>+9.0f}%")
            print(f"  {'File/path refs':<25} {cb['paths']:>14.0f}% {avg_refs:>14.0f}% {avg_refs - cb['paths']:>+9.0f}%")
            print(f"  {'Key facts':<25} {cb['facts']:>14.0f}% {avg_facts:>14.0f}% {avg_facts - cb['facts']:>+9.0f}%")
            print(f"  {'Hallucinations (avg)':<25} {cb['halluc']:>15.1f} {avg_halluc:>15.1f} {avg_halluc - cb['halluc']:>+10.1f}")

        # Pass/fail gates
        print("\n" + "─" * 60)
        print("  DECISION GATES")
        print("─" * 60)
        gates = [
            ("Overall retention ≥60%", avg_overall >= 60),
            ("File refs ≥50%", avg_refs >= 50),
            ("Concepts ≥70%", avg_concepts >= 70),
            ("Hallucinations <3 avg", avg_halluc < 3),
        ]
        for name, passed in gates:
            print(f"  {'✅' if passed else '❌'} {name}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="CLaRa Language-Only Compression Test")
    parser.add_argument("--clara-url", default="http://localhost:8765")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--quick", action="store_true", help="Run 2 scenarios only")
    parser.add_argument("--project-dir", default="", help="Path to real project index dir")
    parser.add_argument("--output", default="", help="Output JSON path")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    # Determine scenarios
    scenarios = QUICK_SCENARIOS if args.quick else list(SCENARIOS)

    # Add real project data if available
    if args.project_dir:
        real = load_real_project_data(Path(args.project_dir))
        scenarios.extend(real)

    logger.info("Running %d language test scenarios against %s", len(scenarios), args.clara_url)

    # Run tests
    results: List[LanguageTestResult] = []
    for i, sc in enumerate(scenarios, 1):
        logger.info("[%d/%d] %s (%d memories, types: %s)",
                    i, len(scenarios), sc.name, len(sc.memories),
                    ", ".join(sc.content_types))

        r = run_scenario(args.clara_url, sc, args.max_new_tokens, args.timeout)
        results.append(r)

        if r.error:
            logger.warning("  ✗ %s", r.error)
        else:
            logger.info("  ✓ %d→%d chars (%.1f×), overall=%.0f%%, %.0fms",
                       r.input_chars, r.output_chars, r.compression_ratio,
                       r.overall_retention_pct, r.latency_ms)

    # Phase B code baseline for comparison
    code_baseline = {
        "overall": 29.0,
        "paths": 0.0,
        "facts": 19.0,
        "halluc": 4.0,
    }

    print_results(results, code_baseline)

    # Save
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"docs/Phase31_CLaRa-tests/language_results_{ts}.json")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)
    logger.info("Results saved to %s", out_path)


if __name__ == "__main__":
    main()
