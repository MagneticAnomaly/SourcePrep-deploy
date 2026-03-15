# Roo Code Integration Research

> How Roo Code consumes MCP, its custom modes architecture, and CoDRAG optimization.

**Status:** UPDATED with confirmed docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | VS Code extension (autonomous coding agent) |
| **Vendor** | Roo Code, Inc. (open source, Apache 2.0) |
| **Model** | Any (Claude, GPT, Gemini, local -- user-configurable) |
| **MCP Spec** | Full (tools, resources) |
| **Transport** | stdio |
| **MCP Config** | `mcp_settings.json` (via VS Code settings) |
| **Rules File** | `.roo/rules/*.md` (preferred) OR `.roorules` (fallback) |
| **Mode Rules** | `.roo/rules-{modeSlug}/*.md` OR `.roorules-{modeSlug}` |
| **AGENTS.md** | YES -- loaded by default, disableable via `roo-cline.useAgentRules: false` |
| **Origin** | Fork of Cline |

---

## 2. Key Differentiator: Custom Modes

Roo Code's unique feature is **Custom Modes** -- specialized AI personas with different instructions and tool access:

- **Code Mode**: Full coding capabilities
- **Architect Mode**: Planning and design (no file writes)
- **Ask Mode**: Question answering (read-only)
- **Debug Mode**: Debugging focused
- **Custom**: User-defined roles

### CoDRAG Implications
- **Architect Mode** is a natural fit for CoDRAG -- structural context is exactly what an architect needs
- CoDRAG rules can be mode-specific: "In Architect mode, call `codrag` for structural overview. In Code mode, call `codrag_impact` before changes."
- `.roo/rules/` directory supports mode-specific rule files

---

## 3. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support across all modes
- **Resources**: Supported
- **Prompts**: Not documented

### Architecture
Forked from Cline, so the MCP implementation is very similar:
- Same agentic loop (plan, implement, verify, fix)
- Same tool execution model
- Same confirmation/approval UX

### Auto-Approve
- Per-server auto-approve available
- CoDRAG recommendation: enable auto-approve for codrag server

---

## 4. Rules File System (CONFIRMED FROM DOCS)

### Loading Order (exact injection into system prompt)
Roo Code's system prompt injects rules in this order:
1. Language preference (if set)
2. Global instructions (from Prompts tab)
3. Mode-specific instructions (from Prompts tab)
4. **Mode-specific rules**: `.roo/rules-{modeSlug}/` files (recursive, alphabetical)
5. Fallback: `.roorules-{modeSlug}` if no mode-specific directory
6. `.rooignore` instructions
7. **AGENTS.md** (from workspace root)
8. **General rules**: `.roo/rules/` files (recursive, alphabetical)
9. Fallback: `.roorules` if no general rules directory

Both global (`~/.roo/rules/`) and workspace (`.roo/rules/`) directories are aggregated.

### Key Rules Behavior
- Recursive directory reading (including subdirectories)
- Files sorted by basename, case-insensitive
- Symlink support (max depth 5)
- Empty files silently skipped
- System excludes `.DS_Store`, `*.bak`, `*.cache`, `*.log`, `*.tmp`, `Thumbs.db`
- Mode-specific rules complement general rules (not replace)
- 12,000 char limit not documented but assumed similar to Cline

### CoDRAG Template: `.roo/rules/codrag.md` (general, all modes)
```markdown
# CoDRAG Structural Intelligence

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for natural language code queries.
Use `codrag_impact` before making changes to understand blast radius.

When asked about code structure, architecture, dependencies, modules,
hub files, or blast radius, use the CoDRAG MCP tools.

## Codebase Atlas
[auto-generated]

## Focus Areas
[auto-generated]
```

### CoDRAG Template: `.roo/rules-architect/codrag.md` (Architect mode)
```markdown
# CoDRAG for Architecture Analysis

In Architect mode, CoDRAG is your primary structural intelligence tool.
ALWAYS call `codrag` first for comprehensive module overview.
Use `codrag_audit` for codebase health assessment.
Use `codrag_search` to explore specific module relationships.
```

### CoDRAG Template: `.roo/rules-code/codrag.md` (Code mode)
```markdown
# CoDRAG for Coding

Before making changes, call `codrag_impact` to understand blast radius.
Call `codrag` for module context when entering an unfamiliar area.
```

---

## 5. Special Considerations

### Model Agnostic (Same as Cline)
Same concerns as Cline -- Roo Code works with any model, so tool descriptions must be universal. Local LLM users are a significant demographic.

### AGENTS.md + .roo/rules/ Coexistence (CONFIRMED)
Roo Code loads AGENTS.md by default:
- Setting: `roo-cline.useAgentRules` (default: `true`)
- Location: workspace root only (not subdirectories)
- Priority: after mode-specific rules, before general rules
- Header in system prompt: `# Agent Rules Standard (AGENTS.md):`
- If both `AGENTS.md` and `AGENT.md` exist, `AGENTS.md` is preferred
- Empty/whitespace-only AGENTS.md is ignored

CoDRAG should generate both:
1. `AGENTS.md` section (universal, read by many tools)
2. `.roo/rules/codrag.md` (general, all modes)
3. `.roo/rules-architect/codrag.md` (Architect mode specific)

---

## 6. CoDRAG Optimization Checklist

- [x] Rules loading order confirmed (exact system prompt injection sequence)
- [x] AGENTS.md loading confirmed (default on, disableable, root-only)
- [x] Mode-specific rules directories confirmed (`.roo/rules-{modeSlug}/`)
- [x] Recursive directory reading confirmed (alphabetical, symlink-safe)
- [ ] Test CoDRAG MCP integration in Roo Code
- [ ] Test mode-specific behavior (Architect mode + CoDRAG)
- [ ] Test auto-approve for CoDRAG tools
- [ ] Verify `.roo/rules/codrag.md` + `.roo/rules-architect/codrag.md` injection
- [ ] Empirically test: what is `clientInfo.name` in Roo Code's initialize request?

---

## 7. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Roo Code diverges from Cline's MCP impl | LOW | Fork, so shared base. Monitor. |
| Mode-specific rules add complexity | LOW | Worth it for Architect mode differentiation. |
| Local LLM tool-calling quality | HIGH | Same as Cline -- rules file critical. |
