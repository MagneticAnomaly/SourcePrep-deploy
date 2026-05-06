"""
AutoAudit prompt templates for Tier 2 synthesis (Phase 43).

Each prompt takes structured findings + graph data and produces
a user-facing markdown document.
"""
from __future__ import annotations

AUDIT_SUMMARY_SYSTEM = """You are a senior software architect conducting a codebase health audit.
Produce a concise, actionable executive summary in Markdown.
Use exact file paths and concrete numbers from the data provided.
Do NOT invent findings — only summarize what is given."""

AUDIT_SUMMARY_PROMPT = """Generate an audit summary for this codebase.

PROJECT: {project_name}
FILES: {file_count} | NODES: {node_count} | EDGES: {edge_count} | MODULES: {module_count}

CODEBASE ATLAS (architectural overview):
{atlas_content}

FINDINGS ({finding_count} total, {critical_count} critical, {warning_count} warning):
{findings_formatted}

SPAGHETTI HOTSPOTS (refactor-urgency scores from structural analysis — file-level coupling, size, tech-debt density, epistemic confidence):
{spaghetti_hotspots}

Generate a Markdown document with these sections:
## Health Score
Assign an A–F grade with a 1-sentence rationale. Reference spaghetti hotspot count if non-trivial.

## Critical Findings
List each critical finding with file paths and recommended action. Max 5. When a finding's file appears in the spaghetti hotspots, cite the spaghetti score alongside the finding to ground severity in the structural data.

## Top Recommendations
The 5 highest-impact improvements, ordered by effort-to-value ratio. Prefer recommendations that target high-spaghetti-score files when the structural signal supports it.

## Module Status
One line per module: name, file count, status (healthy/warning/critical), key issue if any.

## Next Steps
3 concrete next actions the developer should take."""

ARCHITECTURE_ANALYSIS_SYSTEM = """You are an expert software architect analyzing codebase structure.
Produce a detailed architectural analysis in Markdown.
Reference exact file paths and import relationships from the data provided."""

ARCHITECTURE_ANALYSIS_PROMPT = """Analyze the architecture of this codebase.

PROJECT: {project_name}

MODULES ({module_count}):
{modules_formatted}

ARCHITECTURE FINDINGS:
{arch_findings}

HUB FILES (highest in-degree):
{hub_files}

CIRCULAR DEPENDENCIES:
{circular_deps}

Generate a Markdown document with:
## Architecture Overview
Brief description of the system's structure and layer organization.

## Module Dependency Flow
How modules depend on each other. Flag any concerning patterns.

## Structural Bottlenecks
Files that are imported by too many others — blast radius concerns.

## Boundary Violations
Cross-module imports that suggest misplaced code or missing abstractions.

## Recommendations
Specific refactoring suggestions with file paths."""

GAP_ANALYSIS_SYSTEM = """You are a senior engineer identifying structural gaps and misplaced concerns.
Produce a gap analysis in Markdown. Be specific — name files, modules, and patterns."""

GAP_ANALYSIS_PROMPT = """Identify structural gaps in this codebase.

PROJECT: {project_name}

MISPLACED IMPORT FINDINGS:
{misplaced_findings}

DUPLICATE LOGIC FINDINGS:
{duplicate_findings}

DEAD CODE FINDINGS:
{dead_code_findings}

TECH DEBT FINDINGS:
{tech_debt_findings}

MODULE SUMMARIES:
{modules_formatted}

Generate a Markdown document with:
## Gap Inventory
Each gap as a numbered item (GAP-N) with: severity, affected files, problem description, resolution.

## Priority Ranking
Table: Gap ID | Severity | Effort | Priority (P0–P4)

## Dependency Diagram
Text-based diagram showing the problematic dependency chains."""

COMPONENT_INVENTORY_SYSTEM = """You are documenting every major component in the codebase.
Produce a detailed component inventory in Markdown."""

COMPONENT_INVENTORY_PROMPT = """Create a component inventory for this codebase.

PROJECT: {project_name}

FILE NODES ({file_count}):
{file_summaries}

MODULES ({module_count}):
{modules_formatted}

Generate a Markdown document with:
## Component Table
| File | Role | Module | Summary | Lines | In-Degree |

Group by module. Include every file that has an augmentation summary.
Sort within each module by in-degree (most-imported first)."""

TECH_DEBT_REPORT_SYSTEM = """You are producing a tech debt report for engineering leadership.
Be specific about locations, severity, and estimated remediation effort."""

TECH_DEBT_REPORT_PROMPT = """Generate a tech debt report for this codebase.

PROJECT: {project_name}

TECH DEBT FINDINGS:
{tech_debt_findings}

LARGE FILE FINDINGS:
{large_file_findings}

STALENESS FINDINGS:
{staleness_findings}

SPAGHETTI HOTSPOTS (refactor-urgency scores — combine these with the per-analyzer findings above; the same file may appear in both lists):
{spaghetti_hotspots}

MODULE HEALTH:
{modules_formatted}

Generate a Markdown document with:
## Debt Summary
Total items, severity distribution, estimated total effort. Quote the spaghetti severity counts (critical/warning) so the severity model is anchored in the structural data, not invented.

## Spaghetti Hotspots
For each top hotspot listed above, give a one-line diagnosis citing its score, severity, and the dominant signal (coupling, debt density, circular, large). Group hotspots by module when possible.

## By Module
Each module's debt items grouped and prioritized. When a hotspot file falls inside a module, reference its spaghetti score alongside the per-analyzer findings.

## Remediation Roadmap
Suggested order of attack — quick wins first, then structural changes. Prefer hotspots with the highest score-to-estimated-effort ratio."""
