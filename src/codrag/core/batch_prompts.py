"""
Batched prompt templates for BYOK multi-item LLM calls.

Each function takes a list of per-item data dicts and returns a single
prompt string + system message that asks the model to produce a JSON array
of results — one per input item, in order.

These are the batched counterparts of the individual prompts in:
- augmenter.py (SYMBOL_SUMMARY_PROMPT, FILE_ROLE_PROMPT, DOC_ROLE_PROMPT)
- inferred_edges.py (INFERRED_EDGES_PROMPT)
- epistemic_enrichment.py (EPISTEMIC_CODE_PROMPT, EPISTEMIC_DOC_PROMPT)
- cluster.py (MODULE_SYNTHESIS_PROMPT)
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ── Catalogue: Symbols ────────────────────────────────────────────

BATCHED_SYMBOL_SYSTEM = """You are a code analyst. You produce concise, accurate summaries of code symbols.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input symbol, in order.
No markdown, no explanation outside the JSON."""

def build_batched_symbol_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for multiple symbol summaries.

    Each item dict should contain: name, symbol_type, file_path, start_line,
    end_line, source_code, imports, role_hint.
    """
    parts = [
        f"Analyze each of the following {len(items)} code symbols. "
        f"For EACH symbol, produce one JSON object with: summary, role, confidence.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== SYMBOL {i}: {item.get('name', '?')} ===")
        parts.append(f"Type: {item.get('symbol_type', '?')}")
        parts.append(f"File: {item.get('file_path', '?')}")
        parts.append(f"Lines: {item.get('start_line', '?')}-{item.get('end_line', '?')}")
        parts.append(f"Imports: {item.get('imports', '')}")
        parts.append(f"Source:\n```\n{item.get('source_code', '')}\n```")

    parts.append(
        '\nFor each symbol, respond with: '
        '{"id": <symbol_number>, "name": "<symbol_name>", '
        '"summary": "1-2 sentence description", '
        '"role": "<one of: entry_point, handler, utility, model, config, test, internal, script, api, core, ui>", '
        '"confidence": 0.85}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Catalogue: Files ──────────────────────────────────────────────

BATCHED_FILE_SYSTEM = """You are a code analyst. You classify files by their role in a codebase.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
No markdown, no explanation outside the JSON."""

def build_batched_file_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for multiple file role classifications.

    Each item dict should contain: file_path, symbol_names, imports,
    content_label, head.
    """
    parts = [
        f"Classify each of the following {len(items)} files. "
        f"For EACH file, produce one JSON object with: summary, role, confidence, key_exports, related_files.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== FILE {i}: {item.get('file_path', '?')} ===")
        parts.append(f"Symbols defined: {item.get('symbol_names', '')}")
        parts.append(f"Imports: {item.get('imports', '')}")
        label = item.get('content_label', 'First 30 lines')
        parts.append(f"{label}:\n```\n{item.get('head', '')}\n```")

    parts.append(
        '\nFor each file, respond with: '
        '{"id": <file_number>, "file": "<file_path>", '
        '"summary": "1 sentence file purpose", '
        '"role": "<one of: api, core, model, utility, config, test, script, ui, documentation>", '
        '"confidence": 0.85, '
        '"key_exports": ["symbol1"], '
        '"related_files": ["path/to/related.py"]}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Catalogue: Docs ───────────────────────────────────────────────

BATCHED_DOC_SYSTEM = """You are a documentation analyst. You classify documentation files by their type, status, and relationship to the codebase.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input document, in order.
No markdown, no explanation outside the JSON."""

def build_batched_doc_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for multiple doc role classifications.

    Each item dict should contain: file_path, section_names, file_refs,
    link_targets, content_label, content.
    """
    parts = [
        f"Analyze each of the following {len(items)} documentation files. "
        f"For EACH file, produce one JSON object.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== DOC {i}: {item.get('file_path', '?')} ===")
        parts.append(f"Sections: {item.get('section_names', '')}")
        parts.append(f"File references: {item.get('file_refs', '')}")
        parts.append(f"Link targets: {item.get('link_targets', '')}")
        label = item.get('content_label', 'Content')
        parts.append(f"{label}:\n```\n{item.get('content', '')}\n```")

    parts.append(
        '\nFor each doc, respond with: '
        '{"id": <doc_number>, "file": "<file_path>", '
        '"summary": "1-2 sentence doc purpose", '
        '"role": "documentation", "confidence": 0.85, '
        '"doc_type": "<research|design_spec|plan|guide|reference|changelog|readme|todo|status|analysis|overview>", '
        '"doc_status": "<active|completed|shelved|superseded|draft|stale>", '
        '"related_files": ["src/path.py"]}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Inferred Edges ────────────────────────────────────────────────

BATCHED_INFERRED_EDGES_SYSTEM = """You are a code analyst specializing in cross-file dependency detection.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
No markdown, no explanation outside the JSON."""

def build_batched_inferred_edges_prompt(
    items: List[Dict[str, Any]],
    known_files: str,
) -> str:
    """Build a batched prompt for inferred edge detection on multiple files.

    Each item dict should contain: file_path, language, source_code, existing_edges.
    known_files is the shared list of known file paths in the codebase.
    """
    parts = [
        f"For each of the following {len(items)} source files, identify relationships "
        f"to OTHER files that static import analysis would miss.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
        f"\nKnown files in the codebase:\n{known_files}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== FILE {i}: {item.get('file_path', '?')} ===")
        parts.append(f"Language: {item.get('language', '?')}")
        parts.append(f"Existing edges: {item.get('existing_edges', '(none)')}")
        parts.append(f"Source:\n```\n{item.get('source_code', '')}\n```")

    parts.append(
        '\nFor each file, respond with: '
        '{"id": <file_number>, "file": "<file_path>", '
        '"edges": [{"target_file": "path/to/target.py", "kind": "calls|implements|configures|listens_to|dispatches", '
        '"evidence": "reason", "confidence": 0.8}]}'
        '\nRules: ONLY emit edges to files in the known_files list. Max 10 edges per file. '
        'Return empty edges array if none found.'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Epistemic: Code ───────────────────────────────────────────────

BATCHED_EPISTEMIC_CODE_SYSTEM = """You are a senior software architect performing deep epistemic analysis of source code files.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
No markdown, no explanation outside the JSON."""

def build_batched_epistemic_code_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for epistemic code enrichment.

    Each item dict should contain: file_path, language, pass1_summary,
    pass1_role, neighbor_context, source_excerpt.
    """
    parts = [
        f"Perform deep epistemic analysis of each of the following {len(items)} code files. "
        f"For EACH file, produce a detailed analysis.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== CODE FILE {i}: {item.get('file_path', '?')} ===")
        parts.append(f"Language: {item.get('language', '?')}")
        parts.append(f"Pass 1 summary: {item.get('pass1_summary', '(none)')}")
        parts.append(f"Pass 1 role: {item.get('pass1_role', 'unknown')}")
        parts.append(f"Neighbor context:\n{item.get('neighbor_context', '(none)')}")
        parts.append(f"Source excerpt:\n```\n{item.get('source_excerpt', '')}\n```")

    parts.append(
        '\nFor each file, respond with: '
        '{"id": <file_number>, "file": "<file_path>", '
        '"extended_summary": "2-4 sentence detailed description", '
        '"domain_tags": ["tag1", "tag2"], '
        '"architecture_layer": "<presentation|business_logic|data|infrastructure|configuration|testing|documentation|build|unknown>", '
        '"subsystem": "name-of-subsystem", '
        '"design_patterns": [], '
        '"cross_references": [], '
        '"tech_debt": [], '
        '"staleness_risk": "low|medium|high", '
        '"epistemic_confidence": 0.85}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Epistemic: Docs ───────────────────────────────────────────────

BATCHED_EPISTEMIC_DOC_SYSTEM = """You are a senior software architect performing deep epistemic analysis of documentation files.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input document, in order.
No markdown, no explanation outside the JSON."""

def build_batched_epistemic_doc_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for epistemic doc enrichment.

    Each item dict should contain: file_path, section_names, pass1_summary,
    pass1_doc_type, pass1_doc_status, file_refs, link_targets,
    neighbor_context, content_excerpt.
    """
    parts = [
        f"Perform deep epistemic analysis of each of the following {len(items)} documentation files. "
        f"For EACH file, produce a detailed analysis.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== DOC FILE {i}: {item.get('file_path', '?')} ===")
        parts.append(f"Sections: {item.get('section_names', '(none)')}")
        parts.append(f"Pass 1 summary: {item.get('pass1_summary', '(none)')}")
        parts.append(f"Pass 1 doc_type: {item.get('pass1_doc_type', 'unknown')}")
        parts.append(f"Pass 1 doc_status: {item.get('pass1_doc_status', 'unknown')}")
        parts.append(f"File references: {item.get('file_refs', '(none)')}")
        parts.append(f"Link targets: {item.get('link_targets', '(none)')}")
        parts.append(f"Neighbor context:\n{item.get('neighbor_context', '(none)')}")
        parts.append(f"Content excerpt:\n```\n{item.get('content_excerpt', '')}\n```")

    parts.append(
        '\nFor each doc, respond with: '
        '{"id": <doc_number>, "file": "<file_path>", '
        '"extended_summary": "2-4 sentence description", '
        '"domain_tags": ["tag1"], '
        '"architecture_layer": "documentation", '
        '"subsystem": "name", '
        '"doc_type": "<research|design_spec|plan|guide|reference|changelog|readme|todo|status|analysis|overview>", '
        '"doc_status": "<active|completed|shelved|superseded|draft|stale>", '
        '"decision_chains": [], '
        '"cross_references": [], '
        '"tech_debt": [], '
        '"staleness_risk": "low|medium|high", '
        '"epistemic_confidence": 0.85}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── Clustering ────────────────────────────────────────────────────

BATCHED_CLUSTER_SYSTEM = """You are a software architect synthesizing module-level summaries from file clusters.
You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input cluster, in order.
No markdown, no explanation outside the JSON."""

def build_batched_cluster_prompt(items: List[Dict[str, Any]]) -> str:
    """Build a batched prompt for multiple cluster syntheses.

    Each item dict should contain: cluster_name, domain_tags, file_count,
    member_summaries, external_deps.
    """
    parts = [
        f"Synthesize a module-level summary for each of the following {len(items)} file clusters. "
        f"For EACH cluster, produce a synthesis.\n"
        f"Return a JSON object: {{\"results\": [{{...}}, {{...}}, ...]}}\n"
    ]

    for i, item in enumerate(items, 1):
        parts.append(f"\n=== CLUSTER {i}: {item.get('cluster_name', '?')} ===")
        parts.append(f"Domain tags: {item.get('domain_tags', '')}")
        parts.append(f"File count: {item.get('file_count', '?')}")
        parts.append(f"Member summaries:\n{item.get('member_summaries', '')}")
        parts.append(f"External dependencies:\n{item.get('external_deps', '(none)')}")

    parts.append(
        '\nFor each cluster, respond with: '
        '{"id": <cluster_number>, "name": "Subsystem Name", '
        '"summary": "2-4 sentence module purpose", '
        '"architecture_layers": ["business_logic"], '
        '"component_status": "active|stable|experimental|deprecated|unknown", '
        '"data_flow": "optional description of data flow", '
        '"dependencies": ["other-subsystem"], '
        '"tech_debt_summary": "optional summary or null"}'
    )
    parts.append('\nJSON response:')
    return "\n".join(parts)


# ── JSON Schema Definitions ──────────────────────────────────────
# For providers that support structured output (OpenAI json_schema,
# Anthropic output_config, Google response_schema).

def get_structured_schema(stage: str) -> Dict[str, Any]:
    """Return a JSON schema for structured output for a given stage.

    These schemas are used with providers that support guaranteed-valid
    JSON output (OpenAI strict mode, Anthropic structured outputs, etc.).
    """
    schemas = {
        "catalogue_symbol": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "summary": {"type": "string"},
                            "role": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["id", "name", "summary", "role", "confidence"],
                    },
                },
            },
            "required": ["results"],
        },
        "catalogue_file": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "file": {"type": "string"},
                            "summary": {"type": "string"},
                            "role": {"type": "string"},
                            "confidence": {"type": "number"},
                            "key_exports": {"type": "array", "items": {"type": "string"}},
                            "related_files": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "file", "summary", "role", "confidence"],
                    },
                },
            },
            "required": ["results"],
        },
        "inferred_edges": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "file": {"type": "string"},
                            "edges": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "target_file": {"type": "string"},
                                        "kind": {"type": "string"},
                                        "evidence": {"type": "string"},
                                        "confidence": {"type": "number"},
                                    },
                                    "required": ["target_file", "kind", "confidence"],
                                },
                            },
                        },
                        "required": ["id", "file", "edges"],
                    },
                },
            },
            "required": ["results"],
        },
        "epistemic_code": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "file": {"type": "string"},
                            "extended_summary": {"type": "string"},
                            "domain_tags": {"type": "array", "items": {"type": "string"}},
                            "architecture_layer": {"type": "string"},
                            "subsystem": {"type": "string"},
                            "design_patterns": {"type": "array", "items": {"type": "string"}},
                            "cross_references": {"type": "array", "items": {"type": "string"}},
                            "tech_debt": {"type": "array", "items": {"type": "string"}},
                            "staleness_risk": {"type": "string"},
                            "epistemic_confidence": {"type": "number"},
                        },
                        "required": ["id", "file", "extended_summary", "domain_tags",
                                     "architecture_layer", "epistemic_confidence"],
                    },
                },
            },
            "required": ["results"],
        },
        "epistemic_doc": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "file": {"type": "string"},
                            "extended_summary": {"type": "string"},
                            "domain_tags": {"type": "array", "items": {"type": "string"}},
                            "architecture_layer": {"type": "string"},
                            "subsystem": {"type": "string"},
                            "doc_type": {"type": "string"},
                            "doc_status": {"type": "string"},
                            "decision_chains": {"type": "array", "items": {"type": "string"}},
                            "cross_references": {"type": "array", "items": {"type": "string"}},
                            "tech_debt": {"type": "array", "items": {"type": "string"}},
                            "staleness_risk": {"type": "string"},
                            "epistemic_confidence": {"type": "number"},
                        },
                        "required": ["id", "file", "extended_summary", "domain_tags",
                                     "architecture_layer", "epistemic_confidence"],
                    },
                },
            },
            "required": ["results"],
        },
        "clustering": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "summary": {"type": "string"},
                            "architecture_layers": {"type": "array", "items": {"type": "string"}},
                            "component_status": {"type": "string"},
                            "data_flow": {"type": ["string", "null"]},
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "tech_debt_summary": {"type": ["string", "null"]},
                        },
                        "required": ["id", "name", "summary"],
                    },
                },
            },
            "required": ["results"],
        },
    }
    return schemas.get(stage, {})
