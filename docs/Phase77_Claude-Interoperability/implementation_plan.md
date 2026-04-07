# Phase 77: Claude Code Interoperability — Implementation Plan

This plan defines how CoDRAG should deeply integrate with Claude Code's native systems — `.claude/` folder, skills, hooks, rules, settings, and CLAUDE.md — to provide a zero-friction, best-in-class developer experience. Every improvement here is dogfooding: we're using Claude Code to build better Claude Code integration for CoDRAG.

---

## Critical Finding: AGENTS.md Is Invisible to Claude Code

**Claude Code reads CLAUDE.md, not AGENTS.md.** Our current `rules_generator.py` writes a rich managed section into CLAUDE.md already (good), but also generates AGENTS.md as the "universal" file. For Claude Code users specifically, AGENTS.md provides zero value unless imported via `@AGENTS.md` in CLAUDE.md.

**Current state:** CoDRAG writes to both CLAUDE.md and AGENTS.md with the same `_build_managed_content()`. The CLAUDE.md path works correctly for Claude Code. The risk is users who only have AGENTS.md (e.g., from `codrag init` without a CLAUDE.md) — they get nothing in Claude Code.

**Action:** Ensure `codrag init` always creates or updates CLAUDE.md for Claude Code users, not just AGENTS.md. Add `@AGENTS.md` import if AGENTS.md is the primary file.

---

## Critical Finding: Context Waste from One-Size-Fits-All Content

**`_build_managed_content()` returns identical ~170-line blocks for every IDE.** Claude Code users get Cursor instructions. Cursor users get Claude Code slash-command hints. Everyone gets auto-approve snippets for `.claude/settings.json` even if they don't use Claude Code.

The MCP server is similarly client-unaware: the `instructions` field and tool response preambles repeat information that Claude Code users already have in CLAUDE.md.

**Action:** Add a `target` parameter to `_build_managed_content()` and trim content per-client. See [02_Client_Aware_Delivery_Strategy.md](02_Client_Aware_Delivery_Strategy.md) for the full design — it's ~55 lines of changes, not a framework.

---

## Integration Tiers

### Tier 1: Zero-Touch Defaults (Ship Now)

Things CoDRAG should do automatically when it detects Claude Code as the client or when generating rules for a Claude Code project.

#### 1.1 — Generate `.claude/settings.json` Auto-Approve

**What:** When `codrag init` or `codrag mcp-config --ide claude` runs, also write/update `.claude/settings.json` with permission rules.

**Target output:**
```json
{
  "permissions": {
    "allow": [
      "mcp__codrag"
    ]
  }
}
```

**Why:** Currently we embed this as a code block in CLAUDE.md and ask the user to copy it. That's friction. We should write it directly, with a confirmation prompt.

**Where to implement:** `src/codrag/mcp_config.py` — extend `write_config()` to handle settings.json alongside mcp.json.

**Claude Code docs confirm:** `permissions.allow` with `mcp__codrag` matches ALL tools from the server. Deny rules take precedence, so this is safe.

#### 1.2 — Ensure `.claude/mcp.json` Is Always Generated

**What:** `codrag init` should always produce `.claude/mcp.json` for project-scope MCP registration.

**Current state:** We already do this via `mcp_config.py`. Verify it uses the committable project scope (`.mcp.json` at project root OR `.claude/mcp.json`).

**Claude Code docs confirm:** Project-scope `.mcp.json` requires one-time user approval, then works for all collaborators. Environment variable expansion (`${VAR}`) is supported.

#### 1.3 — Tool Annotations Audit

**What:** Verify all 6 tool definitions in `mcp_tools.py` have correct annotations.

**Current state (from codebase read):**
| Tool | `readOnlyHint` | Correct? |
|------|---------------|----------|
| `codrag` | `True` | Yes |
| `codrag_search` | `True` | Yes |
| `codrag_impact` | `True` | Yes |
| `codrag_audit` | `True` | Yes |
| `codrag_observe` | `False` | Yes (has writes) |
| `codrag_concepts` | `False` | Yes (has writes) |

**Why it matters:** `readOnlyHint: true` lets Claude Code batch read-only tools for parallel execution. This is already correct.

**Additional annotation:** Consider adding `title` fields with user-friendly names (some tools already have this).

#### 1.4 — MCP Server Instructions Optimization

**What:** Review and tighten the `instructions` field returned in MCP server info.

**Current:** "CoDRAG maps how your codebase is connected -- modules, dependencies, hub files, and architectural patterns. All tools are read-only. Call `codrag` at the start of every task..."

**Claude Code docs confirm:** Server instructions appear as `system-reminder` messages. They're always in context. Keep them concise — every token competes with conversation context.

**Action:** Trim to essential routing info only. The detailed instructions in CLAUDE.md handle the rest. Server instructions should be <200 chars.

---

### Tier 2: Native Claude Code Skills (High Value, Medium Effort)

CoDRAG can generate `.claude/skills/` that give users instant `/slash-command` access to CoDRAG workflows.

#### 2.1 — Skill: `/codrag-onboard`

**Location:** `.claude/skills/codrag-onboard/SKILL.md`

```markdown
---
name: codrag-onboard
description: Get oriented in this codebase using CoDRAG structural intelligence. Use when starting work on an unfamiliar project or returning after time away.
allowed-tools:
  - mcp__codrag__codrag
  - mcp__codrag__codrag_search
  - mcp__codrag__codrag_audit
---

Call `codrag` to get the structural overview of this project. Then:

1. Read the atlas section to understand project identity, stack, and architecture
2. Review the module map to understand how code is organized
3. Check hub files — these are the most-connected files and the best starting points
4. If focus areas are listed, those are the user's current areas of interest
5. Call `codrag_audit(action="scan")` to surface any health issues

Summarize what you learned in 3-5 bullet points. Ask the user what they'd like to work on.
```

**Why:** This wraps the MCP prompt `codrag-onboard` as a native skill. Skills are more discoverable in Claude Code (show in `/` menu) and can specify `allowed-tools` for frictionless execution.

#### 2.2 — Skill: `/codrag-impact`

**Location:** `.claude/skills/codrag-impact/SKILL.md`

```markdown
---
name: codrag-impact
description: Analyze blast radius before making changes to a file. Use before editing hub files or files with many dependents.
allowed-tools:
  - mcp__codrag__codrag_impact
  - mcp__codrag__codrag_search
---

The user wants to understand the impact of changing: $ARGUMENTS

Call `codrag_impact` with the file path and `direction="all"` to see both dependencies and dependents. If the file has >5 dependents, warn the user about the blast radius and suggest which dependents to check. If $ARGUMENTS is empty, ask for the file path.
```

#### 2.3 — Skill: `/codrag-health`

**Location:** `.claude/skills/codrag-health/SKILL.md`

```markdown
---
name: codrag-health
description: Run a codebase health audit and get actionable findings about architecture, quality, and tech debt.
allowed-tools:
  - mcp__codrag__codrag_audit
---

Run `codrag_audit(action="scan")` to get health findings. Then:

1. Group findings by severity (critical, warning, info)
2. For any critical findings, call `codrag_audit(action="refactor", finding_ids=[...])` to get code context
3. Present a prioritized list of improvements

If the user asks to fix something, call `codrag_audit(action="refactor")` with the finding IDs and follow the suggested changes.
```

#### 2.4 — Skill Generation Pipeline

**Where to implement:** New function in `src/codrag/core/rules_generator.py`:

```python
def _write_claude_skills(project_root: Path, project_id: str) -> List[str]:
    """Generate .claude/skills/ for CoDRAG workflows. Returns list of skill names written."""
```

**Key design decisions:**
- Skills are generated, not hand-maintained — they embed the `project_id` for routing
- Use `<!-- codrag-managed -->` markers so we can update without clobbering user edits
- Only generate if `.claude/` directory exists (user has Claude Code)
- Skills have `allowed-tools` frontmatter so CoDRAG tools auto-approve when the skill is active
- Skill descriptions stay under 250 chars (Claude Code caps description budget)

**Claude Code docs confirm:**
- Skill descriptions are always in context (budget: 1% of context window)
- Full skill content loads only on invocation — no token waste
- `allowed-tools` bypasses permission prompts for listed tools
- `$ARGUMENTS` placeholder passes user input through
- Skills support `context: fork` for isolated execution (useful for `/codrag-onboard`)

---

### Tier 3: Hooks Integration (Power User, High Value)

Claude Code hooks enable automated CoDRAG integration without any user action.

#### 3.1 — Hook: Auto-Context on Session Start

**What:** A `SessionStart` hook that calls `codrag` to inject structural context at the beginning of every session.

**Implementation approach:** CoDRAG generates a hook entry in `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'CoDRAG structural context loaded via SessionStart hook'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Reality check:** SessionStart hooks run shell commands, not MCP tools. The hook can't directly call `codrag`. What it CAN do:
- Set environment variables that the MCP server reads
- Trigger a daemon-side pre-warm
- Print a reminder that gets injected into context

**Better approach:** Use the CLAUDE.md instruction "ALWAYS call `codrag` at the START of every task" (which we already have) combined with the `SessionStart` hook printing a brief reminder. The CLAUDE.md instruction has ~70% compliance; the hook makes it more visible.

**Alternative — `InstructionsLoaded` hook:** Fires when CLAUDE.md is loaded. Could trigger a CoDRAG index freshness check.

#### 3.2 — Hook: Auto-Impact Before File Edits

**What:** A `PreToolUse` hook on `Edit` and `Write` tools that reminds about blast radius.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "prompt",
            "command": "Before editing this file, consider: have you checked codrag_impact for this file's dependents? If this is a hub file with many connections, call codrag_impact first."
          }
        ]
      }
    ]
  }
}
```

**Claude Code docs confirm:** `PreToolUse` hooks can use `type: "prompt"` for LLM-evaluated checks. This is non-blocking guidance, not a hard gate.

**Caution:** This fires on EVERY edit. Could be noisy. Consider:
- Only fire for files in CoDRAG's hub list (requires a shell script that queries the daemon)
- Use a `type: "command"` hook that checks hub status and only returns a warning for high-connectivity files

#### 3.3 — Hook: Dogfood Quality Tracking

**What:** A `PostToolUse` hook on `mcp__codrag__.*` that logs tool usage for quality analysis.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp__codrag__.*",
        "hooks": [
          {
            "type": "command",
            "command": "codrag telemetry log-usage --tool $TOOL_NAME --chars $RESULT_SIZE",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Why:** Since we're dogfooding, tracking which tools get called, how large the results are, and whether they're useful feeds directly into product improvement.

#### 3.4 — Hook Generation Pipeline

**Where to implement:** New function in `src/codrag/core/rules_generator.py` or `src/codrag/mcp_config.py`:

```python
def _write_claude_hooks(project_root: Path, project_id: str, level: str = "minimal") -> None:
    """Generate Claude Code hooks for CoDRAG integration.
    
    Levels:
    - minimal: SessionStart reminder only
    - standard: + impact check on edits
    - full: + dogfood telemetry
    """
```

**Merge strategy:** Must merge into existing `settings.json` / `settings.local.json` without clobbering user hooks. Read existing, deep-merge CoDRAG entries, write back.

---

### Tier 4: Path-Scoped Rules (Advanced, Future)

Claude Code supports `.claude/rules/<name>.md` with `paths` frontmatter for conditional loading.

#### 4.1 — Per-Module Rules Generation

**What:** CoDRAG could generate a rule file per module that loads when Claude reads files in that module.

**Example:** `.claude/rules/codrag-module-pipeline.md`
```markdown
---
paths:
  - src/codrag/services/pipeline/**
  - src/codrag/core/scheduler.py
---

This is the Pipeline Orchestration module. Key architectural notes:
- 11-stage pipeline with fast-sync boundary after stage 5
- State machine for lifecycle management in pipeline_state.py
- Thread-safe resource scheduling with compute slot allocation
- Hub files: scheduler.py (156 edges), pipeline_orchestrator.py (89 edges)

Before modifying these files, call `codrag_impact` to check blast radius.
```

**Why:** This is surgically precise context injection. Instead of loading the entire atlas every time, Claude gets module-specific context only when touching relevant files.

**Where to implement:** Extend `rules_generator.py` to iterate over CoDRAG modules and write one rule file per module.

**Claude Code docs confirm:**
- Path-scoped rules trigger when Claude reads matching files
- Rules without `paths` load at startup (avoid for per-module rules)
- Max depth: 5 hops of recursive `@path` imports

**Defer to Phase 78+:** This requires stable module boundaries and is a premium feature. Implement after Tiers 1-3 prove out.

---

## CLAUDE.md Content Optimization

Based on research into what makes effective CLAUDE.md instructions:

### Current Issues

1. **Too long.** The managed section is ~170 lines. Claude Code compliance drops with length. Target <100 lines for managed content.
2. **Redundant instructions.** Tool calling rules are stated 3 times (quick reference table, prose, reinforcement rules). Once is enough with emphasis.
3. **Generic IDE references.** "In Cursor: add to MCP settings" doesn't belong in CLAUDE.md. AGENTS.md is the universal file.
4. **Missing `@AGENTS.md` import.** If AGENTS.md exists, CLAUDE.md should import it so Claude Code sees both.

### Proposed CLAUDE.md Structure (Managed Section)

```markdown
<!-- codrag-managed-start -->
# CoDRAG Integration

codrag_project_id: {project_id}

**IMPORTANT: Route ALL CoDRAG tool calls with `project_id: "{project_id}"`.**

## Tools
| Tool | When to Use |
|------|-------------|
| `codrag` | START of every task — structural overview, modules, hub files |
| `codrag_search` | Find code by meaning, not just string match |
| `codrag_impact` | BEFORE editing — check what depends on a file |
| `codrag_audit` | Codebase health, tech debt, refactoring guidance |
| `codrag_observe` | Save/retrieve cross-session notes |
| `codrag_concepts` | Record/query business rationale and design decisions |

Call `codrag` first. Call `codrag_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

## Codebase Atlas
{atlas_content}

## Focus Areas
{focus_areas}
<!-- codrag-managed-end -->
```

**Target: ~60 lines.** Front-load the project_id routing (critical), provide a scannable tool table, embed atlas, done. Move verbose instructions to skills and AGENTS.md.

### Implementation

**Where:** Refactor `_build_managed_content()` in `rules_generator.py` (lines 328-496).

**Strategy:**
- Claude Code gets the compact version above
- AGENTS.md keeps the verbose version (other IDEs need it — no skills/hooks system)
- Add a `target_ide` parameter to `_build_managed_content()` to select format
- Or: split into `_build_claude_content()` and `_build_universal_content()`

---

## Context Budget Optimization

### Current State (from `server.py:124-207`)

| Client | Budget | First-Call Boost |
|--------|--------|-----------------|
| Claude Code | 50,000 chars | 75,000 (1.5x) |
| Cursor/Windsurf | 30,000 chars | 45,000 |
| Copilot/Qwen | 24,000 chars | 36,000 |
| Cline/Roo | 20,000 chars | 30,000 |

### Optimization Opportunities

1. **Claude Code gets 1M context** — we could push Tier 1 budget higher (60-80K) since Opus/Sonnet models handle it well. But diminishing returns: more context != better understanding. Keep 50K base, consider raising first-call to 2x.

2. **Token warning threshold** — Claude Code warns at 10,000 tokens (~40,000 chars). Our 50K base exceeds this. Options:
   - Document `MAX_MCP_OUTPUT_TOKENS` env var in setup instructions
   - Or: keep results under 10K tokens and use progressive disclosure (summary → detail on follow-up)

3. **Progressive disclosure pattern** — First `codrag` call returns atlas + modules + hubs (orientation). Follow-up calls could return deeper detail on specific modules. This is more token-efficient than dumping everything.

---

## MCP Resources & Prompts Parity

### Resources (browse with `@`)

CoDRAG exposes 5 resources. **Claude Code supports these.** Verify they work:
- `codrag://{project_id}/atlas`
- `codrag://{project_id}/structure`
- `codrag://{project_id}/modules`
- `codrag://{project_id}/audit`
- `codrag://{project_id}/concepts`

### Prompts (invoke with `/`)

CoDRAG provides 5 MCP prompts. These overlap with the proposed skills in Tier 2. **Strategy:** Skills supersede prompts for Claude Code users (better UX, `allowed-tools`, description in `/` menu). Keep prompts for non-Claude-Code clients.

---

## Implementation Sequence

### Sprint 1: Foundation (Tier 1)
1. Audit and tighten MCP server `instructions` field (<200 chars)
2. Refactor `_build_managed_content()` to produce compact Claude Code format
3. Ensure `codrag init` writes `.claude/settings.json` with auto-approve
4. Ensure `.claude/mcp.json` is always generated
5. Add `@AGENTS.md` import to CLAUDE.md if AGENTS.md exists

### Sprint 2: Skills (Tier 2)
6. Implement `_write_claude_skills()` in rules_generator.py
7. Generate `/codrag-onboard`, `/codrag-impact`, `/codrag-health` skills
8. Add skill generation to `codrag init` and `codrag rules --update` flows
9. Test skills in live Claude Code sessions (dogfood)

### Sprint 3: Hooks (Tier 3)
10. Implement `_write_claude_hooks()` with merge-safe settings.json updates
11. Ship `SessionStart` reminder hook (minimal level)
12. Ship `PreToolUse` impact check hook (standard level)
13. Evaluate dogfood telemetry hook feasibility

### Sprint 4: Polish & Advanced (Tier 4 prep)
14. Prototype per-module path-scoped rules generation
15. Optimize context budgets based on Sprint 1-3 telemetry
16. Update marketing copy for "Native Claude Code Support"
17. Document the integration in user-facing docs

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `src/codrag/core/rules_generator.py` | Compact CLAUDE.md format, skill generation, hook generation |
| `src/codrag/mcp_config.py` | Settings.json generation, mcp.json improvements |
| `src/codrag/mcp_tools.py` | Tool annotation audit, description tightening |
| `src/codrag/mcp/server.py` | Server instructions optimization, context budget tuning |
| `src/codrag/core/atlas/generator.py` | Atlas content optimization for compact format |
| `src/codrag/core/atlas/prompts.py` | Atlas prompt tuning for conciseness |

---

## Verification Strategy

- **Tier 1:** Run `codrag init` on a test project, verify `.claude/settings.json`, `.claude/mcp.json`, and CLAUDE.md are all correct. Open Claude Code and confirm tools auto-approve.
- **Tier 2:** Generate skills, open Claude Code, verify `/codrag-onboard` appears in menu and executes correctly.
- **Tier 3:** Generate hooks, restart Claude Code session, verify SessionStart hook fires.
- **Dogfooding:** Every change is tested in THIS repo first. CoDRAG is its own best test case.

---

## Research Sources

- [Claude Code Memory/CLAUDE.md](https://code.claude.com/docs/en/memory) — Loading order, `@path` imports, compliance rates (~70%)
- [Claude Code MCP Integration](https://code.claude.com/docs/en/mcp) — Tool naming `mcp__server__tool`, project-scope `.mcp.json`, annotations
- [Claude Code Hooks](https://code.claude.com/docs/en/hooks) — Full lifecycle events, handler types (command/http/prompt/agent)
- [Claude Code Skills](https://code.claude.com/docs/en/skills) — Frontmatter fields, `allowed-tools`, description budget (250 chars)
- [Claude Code Settings](https://code.claude.com/docs/en/settings) — Precedence order, permission rules, JSON schema
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices) — Keep CLAUDE.md <200 lines, use emphasis for critical rules
- [arXiv:2602.14878](https://arxiv.org/abs/2602.14878) — Purpose + Guidelines pattern for tool descriptions (already used in mcp_tools.py)
