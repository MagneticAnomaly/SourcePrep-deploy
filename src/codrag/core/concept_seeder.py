"""
CoDRAG Concept Seeder — Phase 74 (Epistemic Concepts)
=====================================================

LLM-powered concept extraction from existing pipeline outputs.
Reads atlas, module synthesis, and audit data to generate 20-40
concept seeds that capture the "why" behind the codebase.

**Design:**
  - Single LLM call with a focused prompt (≤4000 input chars)
  - Uses the ``large_model`` slot (thinking model) for quality
  - Generates structured JSON with title, content, category, anchors
  - Also generates 5-8 clarifying questions for uncovered areas
  - Filters modules to ≥5 files to avoid noise from trivial subsystems

**Usage:**
  ``from codrag.core.concept_seeder import seed_concepts``
  ``result = seed_concepts(project_id)``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum files for a module to be included in seeding context
MIN_MODULE_FILES = 5


def seed_concepts(project_id: str) -> Dict[str, Any]:
    """Run the full concept seeding pipeline for a project.

    1. Load atlas + modules + audit context
    2. Assemble a focused prompt
    3. Call the LLM to generate concept seeds
    4. Store concepts and questions in the ConceptStore

    Returns a summary dict with counts and any errors.
    """
    from codrag.services.concept_store import concept_store
    from codrag.services.project_helpers import require_project
    from codrag.core.project_registry import project_index_dir

    project = require_project(project_id)
    index_dir = project_index_dir(project)

    # 1. Load pipeline data
    context_text = _assemble_seeding_context(index_dir, project.path)
    if not context_text or len(context_text) < 100:
        return {
            "status": "insufficient_data",
            "message": "Not enough pipeline data to seed concepts. "
                       "Run the knowledge pipeline first (Fast Sync + Deep Enrichment).",
            "concepts_created": 0,
            "questions_created": 0,
        }

    # 2. Get LLM client
    llm = _get_seeder_llm()
    if llm is None:
        return {
            "status": "no_model",
            "message": "No LLM model configured. Configure a thinking model "
                       "in Settings → AI Models to generate concepts.",
            "concepts_created": 0,
            "questions_created": 0,
        }

    # 3. Generate concepts via LLM
    try:
        raw_response = _call_llm_for_concepts(llm, context_text, project.name)
    except Exception as e:
        logger.error("Concept seeding LLM call failed: %s", e, exc_info=True)
        return {
            "status": "llm_error",
            "message": f"LLM call failed: {e}",
            "concepts_created": 0,
            "questions_created": 0,
        }

    # 4. Parse and store
    parsed = _parse_llm_response(raw_response)
    concepts_created = 0
    questions_created = 0

    for c in parsed.get("concepts", []):
        try:
            concept_store.save(
                project_id=project_id,
                title=c.get("title", "Untitled"),
                content=c.get("content", ""),
                category=c.get("category", "technical"),
                status="seed",
                confidence=c.get("confidence", 0.7),
                anchors=c.get("anchors", []),
                tags=c.get("tags", []),
            )
            concepts_created += 1
        except Exception as e:
            logger.warning("Failed to save concept '%s': %s", c.get("title"), e)

    for q in parsed.get("questions", []):
        try:
            concept_store.save_question(
                project_id=project_id,
                question=q.get("question", ""),
                context=q.get("context", ""),
                suggested_category=q.get("suggested_category", "technical"),
                target_module=q.get("target_module"),
            )
            questions_created += 1
        except Exception as e:
            logger.warning("Failed to save question: %s", e)

    logger.info(
        "Concept seeding complete for %s: %d concepts, %d questions",
        project_id, concepts_created, questions_created,
    )

    return {
        "status": "success",
        "concepts_created": concepts_created,
        "questions_created": questions_created,
        "message": f"Generated {concepts_created} concept seeds and "
                   f"{questions_created} clarifying questions.",
    }


def _assemble_seeding_context(index_dir: Path, project_path: str) -> str:
    """Assemble context from pipeline outputs for the LLM prompt.

    Reads atlas.json, trace_modules.jsonl, and audit findings.
    Budget: ~3500 chars total to leave room for the prompt + response.
    """
    parts: List[str] = []
    budget = 3500

    # 1. Atlas (identity + workspace map — the richest context)
    atlas_path = index_dir / "atlas.json"
    if atlas_path.exists():
        try:
            with open(atlas_path, "r", encoding="utf-8") as f:
                atlas = json.load(f)
            identity = atlas.get("identity", "")
            workspace_map = atlas.get("workspace_map", "")
            cross_cutting = atlas.get("cross_cutting", "")

            atlas_text = ""
            if identity:
                atlas_text += f"IDENTITY: {identity}\n"
            if workspace_map:
                atlas_text += f"WORKSPACE MAP:\n{workspace_map}\n"
            if cross_cutting:
                atlas_text += f"CROSS-CUTTING: {cross_cutting}\n"

            if atlas_text:
                trimmed = atlas_text[:1500]
                parts.append(f"## Codebase Atlas\n{trimmed}")
                budget -= len(trimmed) + 20
        except Exception as e:
            logger.debug("Failed to load atlas for seeding: %s", e)

    # 2. Modules (filtered to ≥5 files)
    modules_path = index_dir / "trace_modules.jsonl"
    if modules_path.exists() and budget > 200:
        try:
            modules = []
            with open(modules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        mod = json.loads(line)
                        file_count = len(mod.get("files", []))
                        if file_count >= MIN_MODULE_FILES:
                            modules.append(mod)
                    except json.JSONDecodeError:
                        continue

            if modules:
                # Sort by file count (most important first)
                modules.sort(key=lambda m: len(m.get("files", [])), reverse=True)
                mod_lines = []
                for mod in modules[:15]:  # Top 15 modules
                    name = mod.get("name", "unnamed")
                    summary = mod.get("summary", "")[:100]
                    files = mod.get("files", [])
                    mod_lines.append(f"- {name} ({len(files)} files): {summary}")

                mod_text = "\n".join(mod_lines)[:budget - 50]
                parts.append(f"## Major Modules ({len(modules)} with ≥{MIN_MODULE_FILES} files)\n{mod_text}")
                budget -= len(mod_text) + 50
        except Exception as e:
            logger.debug("Failed to load modules for seeding: %s", e)

    # 3. Audit findings summary (if available)
    audit_path = index_dir / "audit_findings.json"
    if audit_path.exists() and budget > 200:
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                findings = json.load(f)
            if isinstance(findings, list) and findings:
                finding_lines = []
                for f_item in findings[:8]:
                    if isinstance(f_item, dict):
                        finding_lines.append(
                            f"- [{f_item.get('category', '?')}] {f_item.get('title', '?')}: "
                            f"{f_item.get('message', '')[:80]}"
                        )
                if finding_lines:
                    finding_text = "\n".join(finding_lines)[:budget]
                    parts.append(f"## Audit Findings\n{finding_text}")
        except Exception as e:
            logger.debug("Failed to load audit findings for seeding: %s", e)

    return "\n\n".join(parts)


def _get_seeder_llm():
    """Get the LLM client for concept seeding (large model slot)."""
    try:
        from codrag.server import _get_llm_client_for_task
        client = _get_llm_client_for_task("concepts")
        if client is None:
            # Fall back to enrichment task (also uses large model)
            client = _get_llm_client_for_task("enrichment")
        return client
    except Exception as e:
        logger.debug("Failed to get LLM for concept seeding: %s", e)
        return None


def _call_llm_for_concepts(llm, context_text: str, project_name: str) -> str:
    """Call the LLM with the concept extraction prompt."""
    prompt = f"""You are analyzing the codebase "{project_name}" to extract high-level concepts.

Based on the following codebase analysis data, generate:
1. **Concepts** (15-30): High-level knowledge about WHY the code is this way, business decisions, architecture rationale, design patterns, domain concepts, and constraints.
2. **Questions** (5-8): Clarifying questions about areas where the "why" is unclear and a human developer could provide valuable insight.

Each concept should capture knowledge that isn't obvious from reading the code itself — the intent, the trade-off, the business reason.

**Categories:**
- **architecture**: System design, pipeline topologies, overarching structural intent
- **domain**: Core business logic and rules
- **product**: UX goals, user journeys, feature prioritization logic
- **epistemic**: Knowledge representation, agentic reasoning models, cognitive pipelines
- **process**: CI/CD workflows, operational playbooks, agent operations
- **brand**: Visual identity, typography, UI/UX feel, tone of voice
- **security**: Authentication flows, privacy boundaries, data isolation
- **technical**: Specific implementation constraints, library choices
- **pattern**: Recurrent code structures and design patterns
- **constraint**: Performance limits, API restrictions, legacy compatibility
- **decision**: ADRs, trade-off rationale, why X was chosen over Y

## Codebase Data

{context_text}

## Output Format

Respond with ONLY a JSON object (no markdown fencing):
{{
  "concepts": [
    {{
      "title": "Short descriptive title",
      "content": "2-4 sentence explanation of the concept and why it matters",
      "category": "architecture|domain|product|epistemic|process|brand|security|technical|pattern|constraint|decision",
      "confidence": 0.5-1.0,
      "anchors": ["path/to/relevant/file.py"],
      "tags": ["tag1", "tag2"]
    }}
  ],
  "questions": [
    {{
      "question": "Why does the system use X instead of Y?",
      "context": "The code shows X pattern but the reason isn't clear from the structure.",
      "suggested_category": "architecture|domain|product|epistemic|process|brand|security|technical|pattern|constraint|decision",
      "target_module": "module_name"
    }}
  ]
}}"""

    # Use the LLM client's chat method
    messages = [{"role": "user", "content": prompt}]
    response = llm.chat(messages, temperature=0.3, max_tokens=4000)

    # Extract content from response
    if isinstance(response, dict):
        # OpenAI-style response
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return response.get("content", "")
    return str(response)


def _parse_llm_response(raw: str) -> Dict[str, Any]:
    """Parse the LLM response into structured concepts and questions."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first line (```json or ```)
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            # Validate structure
            concepts = parsed.get("concepts", [])
            questions = parsed.get("questions", [])

            # Filter valid concepts
            valid_concepts = []
            for c in concepts:
                if isinstance(c, dict) and c.get("title") and c.get("content"):
                    valid_concepts.append(c)

            # Filter valid questions
            valid_questions = []
            for q in questions:
                if isinstance(q, dict) and q.get("question"):
                    valid_questions.append(q)

            return {
                "concepts": valid_concepts,
                "questions": valid_questions,
            }
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse concept seeder response as JSON: %s", e)
        # Try to find JSON in the response
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    logger.warning("Could not parse LLM response for concept seeding")
    return {"concepts": [], "questions": []}
