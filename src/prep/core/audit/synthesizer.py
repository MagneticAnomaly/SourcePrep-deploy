"""
AutoAudit Tier 2 synthesizer for CoDRAG (Phase 43).

Takes Tier 1 findings + graph data and uses an LLM to generate
user-facing markdown report documents.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from prep.core.context_config import PipelineTask, compute_optimal_settings
from prep.core.llm_client import TASK_MAX_CHARS
from typing import Any, Callable, Dict, List, Optional

from .models import AuditContext, AuditDocument, AuditResult, Finding
from . import prompts

logger = logging.getLogger(__name__)


class AuditSynthesizer:
    """LLM-based synthesis of audit findings into markdown documents."""

    def __init__(self, llm_client: Any, project_name: str = ""):
        self.llm = llm_client
        self.project_name = project_name

    def synthesize_all(
        self,
        result: AuditResult,
        ctx: AuditContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        *,
        concurrency: Optional[int] = None,
    ) -> List[AuditDocument]:
        """Generate all report documents from findings.

        Returns a list of AuditDocument objects. Each document is
        independently generated — if one fails, others still succeed.

        Phase 96F: When ``concurrency`` is provided and > 1, the 5
        document generators run in parallel via a ThreadPoolExecutor.
        Concurrency is sourced from the scheduler's swarm budget when
        the audit stage runs inside a swarm window.  Falls back to
        sequential execution when concurrency is None or 1, when only
        one generator is present, or when threading isn't applicable.

        Audit's "swarm" shape is parallel-fixed-fan-out: there are 5
        independent document generators, no coordinator/synthesizer
        decomposition needed (unlike concepts which decomposes work
        per-module).  ThreadPoolExecutor is the right primitive here.
        """
        generators = [
            ("AUDIT_SUMMARY", "Audit Summary", self._gen_summary),
            ("ARCHITECTURE_ANALYSIS", "Architecture Analysis", self._gen_architecture),
            ("GAP_ANALYSIS", "Gap Analysis", self._gen_gaps),
            ("COMPONENT_INVENTORY", "Component Inventory", self._gen_inventory),
            ("TECH_DEBT_REPORT", "Tech Debt Report", self._gen_tech_debt),
        ]

        if concurrency and concurrency > 1 and len(generators) > 1:
            return self._synthesize_parallel(
                generators, result, ctx,
                concurrency=concurrency,
                progress_callback=progress_callback,
            )
        return self._synthesize_sequential(
            generators, result, ctx, progress_callback=progress_callback,
        )

    def _synthesize_sequential(
        self,
        generators: List,
        result: AuditResult,
        ctx: AuditContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[AuditDocument]:
        """Sequential synthesis path — original Phase 43 behavior."""
        documents: List[AuditDocument] = []
        total = len(generators)

        for i, (name, title, gen_fn) in enumerate(generators):
            if progress_callback:
                progress_callback("audit_synthesizing", i, total)

            doc = self._run_generator(name, title, gen_fn, result, ctx)
            documents.append(doc)

        if progress_callback:
            progress_callback("audit_synthesizing", total, total)

        return documents

    def _synthesize_parallel(
        self,
        generators: List,
        result: AuditResult,
        ctx: AuditContext,
        *,
        concurrency: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[AuditDocument]:
        """Phase 96F: Parallel synthesis using ThreadPoolExecutor.

        Each of the 5 (or N) document generators runs in its own thread.
        Order is preserved in the output list — results are placed at
        their original index regardless of completion order.

        Concurrency is capped at min(concurrency, len(generators)) so we
        don't spawn idle threads.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(generators)
        max_workers = min(concurrency, total)
        documents: List[Optional[AuditDocument]] = [None] * total

        logger.info(
            "[Audit/Swarm] Parallel synthesis: %d generators across %d workers",
            total, max_workers,
        )

        if progress_callback:
            progress_callback("audit_synthesizing", 0, total)

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self._run_generator, name, title, gen_fn, result, ctx): i
                for i, (name, title, gen_fn) in enumerate(generators)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    documents[idx] = future.result()
                except Exception as e:
                    # _run_generator already catches generator errors and
                    # returns a fallback. Reaching here means a deeper
                    # failure — emit a minimal stub.
                    name, title, _ = generators[idx]
                    logger.error(
                        "Audit generator %s raised at the future level: %s",
                        name, e, exc_info=True,
                    )
                    documents[idx] = self._structural_fallback(name, title, result, ctx)
                completed += 1
                if progress_callback:
                    progress_callback("audit_synthesizing", completed, total)

        # All slots filled (None should be impossible at this point but defensive cast)
        return [d for d in documents if d is not None]

    def _run_generator(
        self,
        name: str,
        title: str,
        gen_fn: Callable,
        result: AuditResult,
        ctx: AuditContext,
    ) -> AuditDocument:
        """Run a single document generator and wrap as an AuditDocument.

        Catches generator exceptions and returns a structural fallback
        document so partial failures don't kill the whole synthesis.
        Extracted from synthesize_all in Phase 96F so it can be reused
        by both sequential and parallel paths.
        """
        try:
            content = gen_fn(result, ctx)
            doc = AuditDocument(
                name=name,
                title=title,
                content=content,
                generated_at=datetime.now(timezone.utc).isoformat(),
                finding_count=result.finding_count,
                char_count=len(content),
            )
            logger.info("Generated %s (%d chars)", name, len(content))
            return doc
        except Exception as e:
            logger.warning("Failed to generate %s: %s", name, e)
            return self._structural_fallback(name, title, result, ctx)

    # ── Individual generators ────────────────────────────────────

    def _gen_summary(self, result: AuditResult, ctx: AuditContext) -> str:
        """Generate AUDIT_SUMMARY.md"""
        findings_text = self._format_findings(result.findings, max_items=20)
        atlas_content = ""
        if ctx.atlas:
            atlas_content = ctx.atlas.get("content", "")[:2000]

        prompt = prompts.AUDIT_SUMMARY_PROMPT.format(
            project_name=self.project_name,
            file_count=len(ctx.file_nodes),
            node_count=len(ctx.nodes),
            edge_count=len(ctx.edges),
            module_count=len(ctx.modules),
            atlas_content=atlas_content or "(no atlas generated yet)",
            finding_count=result.finding_count,
            critical_count=len(result.findings_by_severity("critical")),
            warning_count=len(result.findings_by_severity("warning")),
            findings_formatted=findings_text,
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system=prompts.AUDIT_SUMMARY_SYSTEM,
            json_mode=False,
            temperature=0.3,
            num_predict=num_predict,
            max_chars=TASK_MAX_CHARS["audit"],
            num_ctx=num_ctx,
        )
        return _clean_markdown(text)

    def _gen_architecture(self, result: AuditResult, ctx: AuditContext) -> str:
        """Generate ARCHITECTURE_ANALYSIS.md"""
        modules_text = self._format_modules(ctx.modules)
        arch_findings = self._format_findings(
            result.findings_by_category("architecture"), max_items=15
        )
        hub_findings = self._format_findings(
            result.findings_by_analyzer("hub_bottlenecks"), max_items=10
        )
        circular = self._format_findings(
            result.findings_by_analyzer("circular_deps"), max_items=10
        )

        prompt = prompts.ARCHITECTURE_ANALYSIS_PROMPT.format(
            project_name=self.project_name,
            module_count=len(ctx.modules),
            modules_formatted=modules_text,
            arch_findings=arch_findings or "(none)",
            hub_files=hub_findings or "(none)",
            circular_deps=circular or "(none)",
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system=prompts.ARCHITECTURE_ANALYSIS_SYSTEM,
            json_mode=False,
            temperature=0.3,
            num_predict=num_predict,
            max_chars=TASK_MAX_CHARS["audit"],
            num_ctx=num_ctx,
        )
        return _clean_markdown(text)

    def _gen_gaps(self, result: AuditResult, ctx: AuditContext) -> str:
        """Generate GAP_ANALYSIS.md"""
        prompt = prompts.GAP_ANALYSIS_PROMPT.format(
            project_name=self.project_name,
            misplaced_findings=self._format_findings(
                result.findings_by_analyzer("misplaced_imports"), max_items=10
            ) or "(none)",
            duplicate_findings=self._format_findings(
                result.findings_by_analyzer("duplicate_logic"), max_items=10
            ) or "(none)",
            dead_code_findings=self._format_findings(
                result.findings_by_analyzer("dead_code"), max_items=15
            ) or "(none)",
            tech_debt_findings=self._format_findings(
                result.findings_by_analyzer("tech_debt"), max_items=10
            ) or "(none)",
            modules_formatted=self._format_modules(ctx.modules),
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system=prompts.GAP_ANALYSIS_SYSTEM,
            json_mode=False,
            temperature=0.3,
            num_predict=num_predict,
            max_chars=TASK_MAX_CHARS["audit"],
            num_ctx=num_ctx,
        )
        return _clean_markdown(text)

    def _gen_inventory(self, result: AuditResult, ctx: AuditContext) -> str:
        """Generate COMPONENT_INVENTORY.md"""
        file_summaries = self._format_file_summaries(ctx, max_files=100)

        prompt = prompts.COMPONENT_INVENTORY_PROMPT.format(
            project_name=self.project_name,
            file_count=len(ctx.file_nodes),
            file_summaries=file_summaries,
            module_count=len(ctx.modules),
            modules_formatted=self._format_modules(ctx.modules),
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system=prompts.COMPONENT_INVENTORY_SYSTEM,
            json_mode=False,
            temperature=0.2,
            num_predict=num_predict,
            max_chars=TASK_MAX_CHARS["audit"],
            num_ctx=num_ctx,
        )
        return _clean_markdown(text)

    def _gen_tech_debt(self, result: AuditResult, ctx: AuditContext) -> str:
        """Generate TECH_DEBT_REPORT.md"""
        prompt = prompts.TECH_DEBT_REPORT_PROMPT.format(
            project_name=self.project_name,
            tech_debt_findings=self._format_findings(
                result.findings_by_analyzer("tech_debt"), max_items=15
            ) or "(none)",
            large_file_findings=self._format_findings(
                result.findings_by_analyzer("large_files"), max_items=10
            ) or "(none)",
            staleness_findings=self._format_findings(
                result.findings_by_analyzer("staleness"), max_items=5
            ) or "(none)",
            modules_formatted=self._format_modules(ctx.modules),
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.AUDIT,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        text, _ = self.llm.generate(
            prompt=prompt,
            system=prompts.TECH_DEBT_REPORT_SYSTEM,
            json_mode=False,
            temperature=0.3,
            num_predict=num_predict,
            max_chars=TASK_MAX_CHARS["audit"],
            num_ctx=num_ctx,
        )
        return _clean_markdown(text)

    # ── Structural fallback (no LLM) ────────────────────────────

    def _structural_fallback(
        self, name: str, title: str, result: AuditResult, ctx: AuditContext
    ) -> AuditDocument:
        """Generate a stats-only document when LLM is unavailable."""
        lines = [
            f"# {title}",
            "",
            f"*Generated structurally (LLM unavailable) at {datetime.now(timezone.utc).isoformat()}*",
            "",
            f"- **Total findings:** {result.finding_count}",
        ]
        for sev in ("critical", "warning", "info", "suggestion"):
            count = len(result.findings_by_severity(sev))
            if count:
                lines.append(f"- **{sev.title()}:** {count}")

        lines.append("")
        lines.append("## Findings")
        lines.append("")

        for f in result.findings[:30]:
            lines.append(f"### [{f.severity.upper()}] {f.title}")
            lines.append(f"{f.description}")
            if f.suggested_action:
                lines.append(f"**Action:** {f.suggested_action}")
            lines.append("")

        content = "\n".join(lines)
        return AuditDocument(
            name=name,
            title=title,
            content=content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            finding_count=result.finding_count,
            char_count=len(content),
        )

    # ── Formatting helpers ───────────────────────────────────────

    @staticmethod
    def _format_findings(findings: List[Finding], max_items: int = 20) -> str:
        """Format findings as text for LLM prompts."""
        lines: List[str] = []
        for f in findings[:max_items]:
            files_str = ", ".join(f.file_paths[:3])
            lines.append(
                f"[{f.severity.upper()}] {f.title}\n"
                f"  Files: {files_str}\n"
                f"  {f.description[:200]}\n"
                f"  Action: {f.suggested_action}"
            )
        if len(findings) > max_items:
            lines.append(f"... and {len(findings) - max_items} more findings")
        return "\n\n".join(lines)

    @staticmethod
    def _format_modules(modules: List[Dict[str, Any]]) -> str:
        """Format module list for LLM prompts."""
        lines: List[str] = []
        for m in modules:
            name = m.get("name", m.get("module_id", "?"))
            summary = m.get("summary", "")[:150]
            file_count = m.get("file_count", len(m.get("member_files", [])))
            status = m.get("component_status", "unknown")
            deps = ", ".join(m.get("dependencies", [])[:5]) or "none"
            lines.append(
                f"- **{name}** ({file_count} files, {status}): {summary}\n"
                f"  Dependencies: {deps}"
            )
        return "\n".join(lines) if lines else "(no modules)"

    @staticmethod
    def _format_file_summaries(ctx: AuditContext, max_files: int = 100) -> str:
        """Format file summaries for the inventory prompt."""
        lines: List[str] = []
        # Sort by in-degree (most-imported first)
        file_items = sorted(
            ctx.file_nodes.items(),
            key=lambda kv: ctx.in_degree(kv[0]),
            reverse=True,
        )
        for nid, node in file_items[:max_files]:
            fp = node.get("file_path", "")
            lang = node.get("language", "?")
            size = node.get("metadata", {}).get("size", 0)
            aug = ctx.augmentations.get(nid, {})
            role = aug.get("role", "?")
            summary = aug.get("summary", "")[:100]
            in_deg = ctx.in_degree(nid)
            mod = ctx.module_for_file(fp)
            mod_name = mod.get("name", "?") if mod else "unassigned"

            lines.append(
                f"{fp} | {role} | {mod_name} | {summary} | ~{size // 40} lines | in-degree={in_deg}"
            )
        if len(ctx.file_nodes) > max_files:
            lines.append(f"... and {len(ctx.file_nodes) - max_files} more files")
        return "\n".join(lines)


def save_documents(documents: List[AuditDocument], index_dir: Path) -> List[str]:
    """Write generated documents to {index_dir}/audit/ as markdown files.

    Returns list of written file names.
    """
    audit_dir = Path(index_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    written: List[str] = []
    for doc in documents:
        filename = f"{doc.name}.md"
        path = audit_dir / filename
        path.write_text(doc.content, encoding="utf-8")
        written.append(filename)
        logger.info("Wrote %s (%d chars)", filename, doc.char_count)

    return written


def _clean_markdown(text: str) -> str:
    """Clean LLM output for markdown documents."""
    import re
    # Strip think tags
    text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>.*', '', text, flags=re.DOTALL)
    text = re.sub(r'</?output>\s*', '', text, flags=re.DOTALL)
    # Strip markdown code fences wrapping the entire output
    text = text.strip()
    if text.startswith("```markdown"):
        text = text[len("```markdown"):].strip()
    if text.startswith("```md"):
        text = text[len("```md"):].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text
