"""
CoDRAG Concept Seeder — Phase 74 (Epistemic Concepts) + Phase 96F (Swarm)
=========================================================================

LLM-powered concept extraction from existing pipeline outputs.
Reads atlas, module synthesis, and audit data to generate concept seeds
that capture the "why" behind the codebase.

**Two execution paths:**

1. **Swarm path** (`seed_concepts_swarm`, Phase 96F):
   - Decomposes work into per-module units (one WorkItem per module)
   - Coordinator assigns analysis_angle per module
   - Workers fan out across all available LLM workers (10 on Ollama cloud)
   - Synthesizer merges + dedupes + extracts cross-module invariants
   - Used when: ≥3 modules exist, model supports swarm, scheduler budget ≥3
   - Throughput: ~9x faster than sequential when conditions met

2. **Sequential path** (`seed_concepts`, original Phase 74):
   - Single LLM call with a global context prompt
   - Used as fallback when swarm conditions aren't met
   - Always available, single-worker

**Usage:**
  ``from codrag.core.concept_seeder import seed_concepts``
  ``result = seed_concepts(project_id)``  # auto-routes to swarm or sequential

To force the sequential path (e.g., for tests):
  ``result = seed_concepts(project_id, prefer_swarm=False)``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum files for a module to be included in seeding context
# (sequential path — keeps prompt focused on substantial subsystems)
MIN_MODULE_FILES = 5

# Phase 96F: Swarm path uses a lower per-module file threshold so that
# small/single-file modules still participate in the fan-out.  The
# whole point of swarm decomposition is maximum parallelism — filtering
# out trivial modules reduces fan-out without saving prompt budget
# (each worker only loads its own module, not the full atlas).
MIN_MODULE_FILES_FOR_SWARM = 1

# Phase 96F: Minimum modules for swarm fan-out (matches scheduler's
# min_workers floor of 3 to avoid coordinator/synthesizer overhead
# when there isn't enough work to parallelize).
MIN_MODULES_FOR_SWARM = 3


def seed_concepts(project_id: str, *, prefer_swarm: bool = True) -> Dict[str, Any]:
    """Run the concept seeding pipeline for a project.

    Phase 96F: When ``prefer_swarm`` is True (default), tries the swarm
    fan-out path first (per-module decomposition + parallel workers).
    Falls back to the sequential single-call path when swarm conditions
    aren't met (insufficient modules, model doesn't support swarm,
    scheduler budget too low, or any error during swarm setup).

    Args:
        project_id: The project to seed concepts for.
        prefer_swarm: If True, attempt swarm path first. Tests and edge
            cases can pass False to force the sequential path.

    Returns a summary dict with concepts_created, questions_created,
    status, and a 'mode' field indicating "swarm" or "sequential".
    """
    if prefer_swarm:
        try:
            return seed_concepts_swarm(project_id)
        except _SwarmFallback as fallback:
            logger.info(
                "Concept seeding falling back to sequential: %s",
                fallback,
            )
        except Exception:
            logger.warning(
                "Concept seeding swarm path raised, falling back to sequential",
                exc_info=True,
            )
    return _seed_concepts_sequential(project_id)


class _SwarmFallback(RuntimeError):
    """Internal sentinel: swarm path determined sequential is the right choice."""


def _seed_concepts_sequential(project_id: str) -> Dict[str, Any]:
    """Sequential single-LLM-call concept seeding (Phase 74 original).

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
        "mode": "sequential",
        "concepts_created": concepts_created,
        "questions_created": questions_created,
        "message": f"Generated {concepts_created} concept seeds and "
                   f"{questions_created} clarifying questions.",
    }


# ── Phase 96F: Swarm path ────────────────────────────────────────


def seed_concepts_swarm(project_id: str) -> Dict[str, Any]:
    """Swarm-based concept seeding with per-module fan-out.

    Decomposition: each module (≥MIN_MODULE_FILES files) becomes one
    WorkItem. Coordinator assigns analysis_angle per module. Workers
    generate per-module concepts in parallel. Synthesizer merges,
    dedupes, and extracts cross-module invariants + clarifying questions.

    Raises:
        _SwarmFallback: when conditions for swarm aren't met (caller
            should fall back to sequential).
    """
    from codrag.services.concept_store import concept_store
    from codrag.services.project_helpers import require_project
    from codrag.core.project_registry import project_index_dir
    from codrag.core.swarm_orchestrator import (
        SwarmOrchestrator, WorkItem, WorkerAssignment,
    )

    project = require_project(project_id)
    index_dir = project_index_dir(project)

    # 1. Get LLM client (need it for both swarm checks and execution)
    llm = _get_seeder_llm()
    if llm is None:
        raise _SwarmFallback("no LLM model configured")

    # 2. Check if model supports swarm via the scheduler's registry
    try:
        from codrag.services.pipeline.scheduler import is_swarm_active_for_stage
        if not is_swarm_active_for_stage("concepts", llm.provider, llm.model):
            raise _SwarmFallback(
                f"model {llm.provider}/{llm.model} not swarm-capable for concepts"
            )
    except _SwarmFallback:
        raise
    except Exception as e:
        raise _SwarmFallback(f"swarm capability check failed: {e}")

    # 3. Determine concurrency budget from the scheduler
    concurrency = 1
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        full = pipeline_scheduler.full_budget_for_swarm(
            llm.provider, llm.model, project_id=project_id,
        )
        if full is None:
            raise _SwarmFallback("scheduler returned None for swarm budget (likely below min_workers)")
        concurrency = full
    except _SwarmFallback:
        raise
    except Exception as e:
        raise _SwarmFallback(f"could not get scheduler budget: {e}")

    # 4. Load modules and build per-module work items
    modules = _load_modules_for_swarm(index_dir)
    if len(modules) < MIN_MODULES_FOR_SWARM:
        raise _SwarmFallback(
            f"only {len(modules)} modules with ≥{MIN_MODULE_FILES_FOR_SWARM} "
            f"files (need ≥{MIN_MODULES_FOR_SWARM} for swarm)"
        )

    # F-59: Cap concurrency for cloud-proxied models.  The cloud endpoint
    # serializes requests (Free=1, Pro=3, Max=10 concurrent).  With 10
    # workers all hitting a concurrency-1 endpoint, requests 2-10 queue
    # for 30-60s each, triggering read timeouts before they even start.
    # Cap at 3 as a safe default for most cloud tiers.
    if ":cloud" in llm.model.lower() or llm.provider in ("openai", "anthropic", "google"):
        cloud_max = 3
        if concurrency > cloud_max:
            logger.info(
                "[Swarm/Concepts] Capping concurrency %d → %d for cloud model %s",
                concurrency, cloud_max, llm.model,
            )
            concurrency = cloud_max

    # Cap fan-out at the configured concurrency
    if len(modules) > concurrency:
        logger.info(
            "[Swarm/Concepts] %d modules > %d workers — workers will process "
            "modules in batches", len(modules), concurrency,
        )

    items: List[WorkItem] = []
    for mod in modules:
        item_id = f"module:{mod.get('module_id', mod.get('name', 'unknown'))}"
        summary = _build_module_summary(mod)
        full_context = json.dumps(_build_module_context(mod))
        items.append(WorkItem(id=item_id, summary=summary, full_context=full_context))

    logger.info(
        "[Swarm/Concepts] Fan-out: %d modules across %d workers (model=%s)",
        len(items), concurrency, llm.model,
    )

    # 5. Run the swarm
    # Phase 96F follow-up: Use shorter coordinator/synthesis timeouts than
    # the default 120/180s.  Concept extraction prompts are small and
    # should respond fast — a hung kimi-k2.5:cloud coordinator burned 11+
    # minutes during initial validation before being killed.
    project_name = project.name
    # F-59: Skip coordinator for cloud models. The coordinator LLM call
    # takes 90s to time out on kimi-k2.5:cloud (which has a long thinking
    # phase even with think=False), adding 90s of dead time before workers
    # start.  The per-module fallback assignments ("perform standard
    # architectural analysis") work well enough for concept extraction.
    is_cloud_model = ":cloud" in llm.model.lower() or llm.provider in ("openai", "anthropic", "google")
    orch = SwarmOrchestrator(
        llm=llm,
        concurrency=concurrency,
        coordinator_timeout_s=10.0 if is_cloud_model else 90.0,  # skip fast on cloud
        synthesis_timeout_s=120.0,
    )

    coordinator_prompt = (
        "You are coordinating concept extraction across {n} subsystems of "
        "the codebase \"{project}\".\n\n"
        "Subsystems:\n{{group_summaries}}\n\n"
        "For EACH subsystem, choose an analysis_angle that suits its nature:\n"
        "- Pipeline/orchestration → \"control flow and coordination\"\n"
        "- Data/storage → \"data model and persistence boundaries\"\n"
        "- API/router → \"interface contracts and validation\"\n"
        "- Worker/processor → \"input transformation and side effects\"\n"
        "- Config/settings → \"constraint propagation and defaults\"\n"
        "- Test/eval → \"guarantees being verified\"\n"
        "- UI/component → \"user interaction patterns and state shape\"\n\n"
        "Also pick 1-3 priority_concerns per subsystem (specific risks "
        "or knowledge gaps to focus the analysis on).\n\n"
        "Respond with JSON only:\n"
        '{{"assignments": [{{"item_id": "module:...", '
        '"analysis_angle": "...", "priority_concerns": ["...", "..."]}}]}}'
    ).format(n=len(items), project=project_name)

    synthesis_prompt = (
        "Below are concepts extracted from {n} parallel subsystem analyses "
        "of \"{project}\".\n\n"
        "{{worker_outputs}}\n\n"
        "Your tasks:\n"
        "1. DEDUPLICATE: merge concepts with similar titles or overlapping "
        "content. Prefer the more specific version.\n"
        "2. CROSS-MODULE PATTERNS: identify concepts that span multiple "
        "subsystems and elevate them.\n"
        "3. GLOBAL INVARIANTS: generate 3-5 high-level concepts about the "
        "codebase as a whole (architectural decisions, hidden contracts, "
        "trade-offs that span subsystems).\n"
        "4. CLARIFYING QUESTIONS: generate 5-8 questions about areas "
        "where the \"why\" is still unclear.\n\n"
        "Respond with JSON only:\n"
        '{{"concepts": [{{"title": "...", "content": "...", '
        '"category": "architecture|domain|product|epistemic|process|brand|'
        'security|technical|pattern|constraint|decision", '
        '"confidence": 0.5-1.0, "anchors": ["..."], "tags": ["..."], '
        '"scope": "module|cross-module|global"}}], '
        '"questions": [{{"question": "...", "context": "...", '
        '"suggested_category": "...", "target_module": "..."}}]}}'
    ).format(n=len(items), project=project_name)

    def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
        # Each worker generates concepts for ONE module with a focused prompt.
        try:
            module_data = json.loads(item.full_context)
        except Exception:
            module_data = {}

        worker_prompt = (
            "You are analyzing the \"{name}\" subsystem of the codebase "
            "\"{project}\".\n\n"
            "Module data:\n{ctx}\n\n"
            "Analysis angle: {angle}\n"
            "Priority concerns: {concerns}\n\n"
            "Generate 3-8 concept seeds that capture the WHY of this "
            "subsystem. Focus on design rationale, hidden constraints, "
            "trade-offs, and business decisions that aren't obvious from "
            "reading the code itself.\n\n"
            "Each concept must be SPECIFIC to this subsystem (not generic "
            "statements). Anchor concepts to specific files in member_files.\n\n"
            "Respond with JSON only:\n"
            '{{"concepts": [{{"title": "...", "content": "2-4 sentences", '
            '"category": "architecture|domain|product|epistemic|process|brand|'
            'security|technical|pattern|constraint|decision", '
            '"confidence": 0.5-1.0, "anchors": ["..."], "tags": ["..."]}}]}}'
        ).format(
            name=module_data.get("name", item.id),
            project=project_name,
            ctx=item.full_context[:2500],
            angle=assignment.analysis_angle or "comprehensive analysis",
            concerns=", ".join(assignment.priority_concerns) or "none specified",
        )

        try:
            # Phase 96F follow-up (F-29): force think=False so reasoning
            # models (kimi-k2.5:cloud etc.) don't consume the response
            # budget on the thinking field.  Per-module concept extraction
            # is a structured-output task that doesn't need chain-of-
            # thought reasoning.
            text, _tokens = llm.generate(
                prompt=worker_prompt,
                json_mode=True,
                temperature=0.3,
                num_predict=4000,
                think=False,
            )
            return text
        except Exception:
            logger.warning("Concept worker failed for %s", item.id, exc_info=True)
            return None

    result = orch.execute(
        items=items,
        coordinator_prompt=coordinator_prompt,
        worker_fn=worker_fn,
        synthesis_prompt=synthesis_prompt,
    )

    if result is None:
        raise _SwarmFallback("swarm orchestrator returned None")

    # 6. Save concepts and questions from synthesis
    concepts_created = 0
    questions_created = 0

    synthesized = result.synthesis or {}
    final_concepts = synthesized.get("concepts", [])
    final_questions = synthesized.get("questions", [])

    # If synthesis failed but workers succeeded, fall back to merging
    # raw worker outputs (best-effort dedupe by title).
    if not final_concepts and result.worker_results:
        seen_titles: set[str] = set()
        for wr in result.worker_results:
            if not wr.success or not wr.parsed:
                continue
            for c in wr.parsed.get("concepts", []):
                title = (c.get("title") or "").strip().lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    final_concepts.append(c)
        logger.info(
            "[Swarm/Concepts] Synthesis empty; merged %d concepts from "
            "%d worker outputs", len(final_concepts), len(result.worker_results),
        )

    # Phase 96 / F-36: batch the concept saves into a single transaction
    # via concept_store.save_many() instead of N independent save() calls.
    # The previous N-call pattern hit SQLITE_BUSY against pipeline_journal,
    # pipeline_metadata, observation_store, and audit_log writes that
    # share the same database during finalize.  save_many holds the writer
    # lock once for the whole batch and includes a retry-on-locked wrapper.
    try:
        saved, _skipped = concept_store.save_many(project_id, final_concepts)
        concepts_created = saved
    except Exception as e:
        logger.warning(
            "save_many failed for %s, falling back to per-concept saves: %s",
            project_id, e,
        )
        for c in final_concepts:
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
            except Exception as e2:
                logger.warning("Failed to save concept '%s': %s", c.get("title"), e2)

    for q in final_questions:
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

    successful_workers = sum(1 for wr in result.worker_results if wr.success)
    logger.info(
        "[Swarm/Concepts] Complete for %s: %d concepts, %d questions, "
        "%d/%d workers succeeded",
        project_id, concepts_created, questions_created,
        successful_workers, len(result.worker_results),
    )

    return {
        "status": "success",
        "mode": "swarm",
        "concepts_created": concepts_created,
        "questions_created": questions_created,
        "modules_analyzed": len(items),
        "workers_succeeded": successful_workers,
        "workers_total": len(result.worker_results),
        "message": f"Swarm-generated {concepts_created} concept seeds and "
                   f"{questions_created} clarifying questions across "
                   f"{len(items)} subsystems.",
    }


def _load_modules_for_swarm(index_dir: Path) -> List[Dict[str, Any]]:
    """Load modules from trace_modules.jsonl for swarm decomposition.

    Phase 96F: Uses MIN_MODULE_FILES_FOR_SWARM (default 1) instead of
    the sequential-path MIN_MODULE_FILES (default 5).  Swarm wants
    maximum fan-out, so any module with at least one file becomes a
    work unit.
    """
    modules: List[Dict[str, Any]] = []
    modules_path = index_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return modules
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    mod = json.loads(line)
                except json.JSONDecodeError:
                    continue
                file_count = mod.get(
                    "file_count",
                    len(mod.get("member_files", mod.get("files", []))),
                )
                if file_count >= MIN_MODULE_FILES_FOR_SWARM:
                    modules.append(mod)
    except Exception as e:
        logger.debug("Failed to load modules for swarm: %s", e)
    # Sort by file count, biggest first
    modules.sort(
        key=lambda m: m.get(
            "file_count", len(m.get("member_files", m.get("files", []))),
        ),
        reverse=True,
    )
    return modules


def _build_module_summary(mod: Dict[str, Any]) -> str:
    """Build a one-line summary of a module for the coordinator."""
    name = mod.get("name", mod.get("module_id", "unnamed"))
    file_count = mod.get(
        "file_count", len(mod.get("member_files", mod.get("files", []))),
    )
    summary = (mod.get("summary") or "")[:120]
    return f"{name} ({file_count} files): {summary}"


def _build_module_context(mod: Dict[str, Any]) -> Dict[str, Any]:
    """Build a focused per-module context dict for a worker."""
    files = mod.get("member_files", mod.get("files", []))
    return {
        "name": mod.get("name", mod.get("module_id", "unnamed")),
        "summary": (mod.get("summary") or "")[:500],
        "domain_tags": mod.get("domain_tags", []),
        "file_count": len(files),
        "member_files": files[:25],  # cap to keep prompts small
        "internal_dependencies": mod.get("internal_dependencies", []),
        "external_dependencies": mod.get("external_dependencies", []),
        "data_flow": (mod.get("data_flow") or "")[:300],
        "component_status": mod.get("component_status", "unknown"),
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

            # Atlas may store data as separate keys OR as a single "content" string
            content_str = atlas.get("content", "")
            identity = atlas.get("identity", "")
            workspace_map = atlas.get("workspace_map", "")
            cross_cutting = atlas.get("cross_cutting", "")

            atlas_text = ""
            if content_str and isinstance(content_str, str):
                # Modern format: everything in a single content field
                atlas_text = content_str
            else:
                # Legacy/structured format: separate fields
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
                        # Support both "member_files" (current) and "files" (legacy)
                        file_count = mod.get("file_count", len(mod.get("member_files", mod.get("files", []))))
                        if file_count >= MIN_MODULE_FILES:
                            modules.append(mod)
                    except json.JSONDecodeError:
                        continue

            if modules:
                # Sort by file count (most important first)
                modules.sort(key=lambda m: m.get("file_count", len(m.get("member_files", m.get("files", [])))), reverse=True)
                mod_lines = []
                for mod in modules[:15]:  # Top 15 modules
                    name = mod.get("name", mod.get("module_id", "unnamed"))
                    summary = mod.get("summary", "")[:100]
                    files = mod.get("member_files", mod.get("files", []))
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

Respond with ONLY a JSON object. No markdown fencing, no reasoning tags, no preamble — start directly with the opening brace:
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

    # LLMClient.generate returns (text, token_count)
    # Budget needs headroom for thinking models that emit <think> tags
    # before the JSON. kimi-k2.5 uses ~2500 tokens for reasoning.
    text, _tokens = llm.generate(
        prompt=prompt,
        json_mode=True,
        temperature=0.3,
        num_predict=8000,
    )
    return text


def _strip_reasoning_tags(text: str) -> str:
    """Strip <think>...</think> or similar reasoning tags from LLM output."""
    import re
    # Remove <think>...</think> blocks (greedy — may span many lines)
    cleaned = re.sub(r'<think>[\s\S]*?</think>\s*', '', text)
    # Also handle unclosed <think> tag (reasoning ran into output)
    cleaned = re.sub(r'<think>[\s\S]*$', '', cleaned) if '<think>' in cleaned else cleaned
    return cleaned.strip()


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair JSON truncated by token limits.

    Strategy: find the last complete object in the concepts/questions array
    by looking for '}, {' or '}\n  ]' boundaries, then close all open brackets.
    """
    import re

    # Find the last complete array element: '},' or '}\n' followed by more content
    # This handles truncation mid-object
    last_obj_end = -1
    for m in re.finditer(r'\}\s*[,\]]', text):
        last_obj_end = m.start() + 1  # position after the }

    if last_obj_end == -1:
        # No complete objects found — try simpler approach
        last_complete = text.rfind('}')
        if last_complete == -1:
            return text
        last_obj_end = last_complete + 1

    candidate = text[:last_obj_end]

    # Close all open brackets/braces
    opens_bracket = candidate.count('[') - candidate.count(']')
    opens_brace = candidate.count('{') - candidate.count('}')
    candidate += ']' * max(0, opens_bracket)
    candidate += '}' * max(0, opens_brace)
    return candidate


def _parse_llm_response(raw: str) -> Dict[str, Any]:
    """Parse the LLM response into structured concepts and questions."""
    import re

    # Strip reasoning tags (e.g., <think>...</think> from thinking models)
    text = _strip_reasoning_tags(raw)

    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _validate_parsed(parsed)
    except json.JSONDecodeError as e:
        logger.debug("Direct JSON parse failed: %s", e)

    # Try to extract JSON from surrounding text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return _validate_parsed(parsed)
        except json.JSONDecodeError:
            # JSON is likely truncated — try repair
            repaired = _repair_truncated_json(match.group())
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, dict):
                    logger.info("Recovered %d concepts from truncated JSON",
                               len(parsed.get("concepts", [])))
                    return _validate_parsed(parsed)
            except json.JSONDecodeError:
                logger.debug("JSON repair also failed")

    logger.warning("Could not parse LLM response for concept seeding")
    return {"concepts": [], "questions": []}


def _validate_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and filter parsed concept/question data."""
    concepts = parsed.get("concepts", [])
    questions = parsed.get("questions", [])

    valid_concepts = []
    for c in concepts:
        if isinstance(c, dict) and c.get("title") and c.get("content"):
            valid_concepts.append(c)

    valid_questions = []
    for q in questions:
        if isinstance(q, dict) and q.get("question"):
            valid_questions.append(q)

    return {
        "concepts": valid_concepts,
        "questions": valid_questions,
    }
