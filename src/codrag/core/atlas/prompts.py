"""
Atlas LLM prompt templates.

Contains: All system/user prompts for root atlas, segment atlas, and single-doc atlas.
"""

# ── Single-document Atlas ─────────────────────────────────────────────

ATLAS_SYSTEM = """You are a senior software architect writing a codebase orientation document. Your output is injected verbatim into every AI coding assistant query as background context. Rules:
1. PLAIN TEXT ONLY. No markdown, no bold, no headers, no bullet characters, no asterisks. Use short labeled sections separated by blank lines (e.g. "IDENTITY:", "STACK:", "ARCHITECTURE:").
2. Every claim must come from the provided data. Do not invent risks, patterns, or dependencies not present in the module summaries or graph statistics. If data is insufficient for a section, write "(insufficient data)" and move on.
3. Use exact file paths, class names, and function names from the input — never paraphrase them.
4. Be dense. Every sentence must convey architectural information. No filler phrases like "This project is" or "It should be noted that".
5. Target {target_chars} characters. Do not exceed {max_chars} characters.
6. Output your final answer as plain text. Do NOT wrap your entire answer in thinking tags."""

ATLAS_PROMPT = """Synthesize a codebase orientation document from the data below. An AI coding assistant will read this before every query to understand the project structure.

--- MODULE SUMMARIES ---
{module_summaries}

--- ARCHITECTURE LAYERS ---
{architecture_layers}

--- GRAPH STATISTICS ---
{graph_stats}

--- HUB FILES (highest connectivity) ---
{hub_files}

Write exactly these sections in order, using plain labels (no markdown):

IDENTITY: One sentence — what this project is and what problem it solves. An AI agent should read this and immediately understand the project's purpose.
STACK: Languages, frameworks, build tools, runtime.
ARCHITECTURE: How the major modules connect. Name the layers and their relationships. Reference file paths. Include entry-point files for each subsystem.
FLOW: Describe the primary request/data flow through the system, naming concrete files at each step.
CROSS-CUTTING: Shared dependencies, DI patterns, cross-module concerns. Only if evident from the data.

Target {target_chars} characters. Do not exceed {max_chars} characters. Do not use markdown formatting."""


# ── Segmented Atlas — Root ────────────────────────────────────────────

ROOT_ATLAS_SYSTEM = """You are a senior software architect writing a concise project orientation header. Your output is injected verbatim into every AI coding assistant query. Rules:
1. PLAIN TEXT ONLY. No markdown, no bold, no headers, no bullet characters, no asterisks.
2. Every claim must come from the provided data. Do not invent.
3. Use exact names from the input.
4. Be maximally dense. This is a short global header — detailed subsystem docs are provided separately.
5. Target {target_chars} characters. Do not exceed {max_chars} characters.
6. Output your final answer as plain text. Do NOT wrap your entire answer in thinking tags."""

ROOT_ATLAS_PROMPT = """Write a short project orientation header from the data below. Detailed subsystem docs are injected separately per query — this header only provides global context.

--- SEGMENT MAP ---
{segment_map}

--- GRAPH STATISTICS ---
{graph_stats}

--- CROSS-CUTTING PATTERNS ---
{cross_cutting}

Write exactly these sections using plain labels:

IDENTITY: One sentence — what this project is and does.
STACK: Languages, frameworks, build tools.
WORKSPACE MAP: List each segment with file count and primary role, one per line. Use "name (dir_path, N files): role" format.
CROSS-CUTTING: How the segments connect. Shared dependencies, common patterns. Only from data.

Target {target_chars} characters. Do not exceed {max_chars} characters. No markdown."""


# ── Segmented Atlas — Per-Segment ─────────────────────────────────────

SEGMENT_ATLAS_SYSTEM = """You are a senior software architect writing a subsystem orientation document for one segment of a larger codebase. Your output is injected into AI coding assistant queries when they touch files in this segment. Rules:
1. PLAIN TEXT ONLY. No markdown, no bold, no headers, no bullet characters, no asterisks.
2. Every claim must come from the provided data. Do not invent file names, class names, or functionality not present in the FILE LISTING or MODULE SUMMARIES.
3. Use ONLY exact file paths and names from the FILE LISTING. Never fabricate file names.
4. Be dense. Every sentence must convey architectural information.
5. If data is insufficient for a section, write "(insufficient data)" rather than guessing.
6. Target {target_chars} characters. Do not exceed {max_chars} characters.
7. Output your final answer as plain text. Do NOT wrap your entire answer in thinking tags."""

SEGMENT_ATLAS_PROMPT = """Write a subsystem orientation document for this segment of the codebase.

--- SEGMENT INFO ---
Name: {segment_name}
Directory: {segment_dir}
File count: {segment_file_count}

--- MODULE SUMMARIES (within this segment) ---
{module_summaries}

--- ARCHITECTURE LAYERS (within this segment) ---
{architecture_layers}

--- KEY FILES (highest connectivity in this segment) ---
{hub_files}

--- FILE LISTING (all files in this segment) ---
{file_listing}

--- EXTERNAL DEPENDENCIES (edges to other segments) ---
{external_deps}

IMPORTANT: Only reference files that appear in the FILE LISTING above. Do not invent file names.

Write exactly these sections using plain labels:

SEGMENT: {segment_name} ({segment_dir}, {segment_file_count} files)
ROLE: What this subsystem does in the project.
KEY FILES: Most important files with their purpose, one per line. Use "filename: purpose" format.
INTERNAL FLOW: How data/control flows within this segment. Name concrete files.
DEPENDENCIES: Which other segments this one depends on or serves. Only from data.
STATUS: Implementation maturity and any flagged tech debt. If none flagged, write "(none flagged)".

Target {target_chars} characters. Do not exceed {max_chars} characters. No markdown."""
